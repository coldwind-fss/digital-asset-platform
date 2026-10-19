"""One transaction for an authenticated business request and its retry receipt.

Legacy application services may call commit; inside this boundary that becomes
flush. Only this middleware commits after successful response serialization.
Authentication/account administration keep their independent session lifecycle.
"""
import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import json
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.modules.identity_access.public import attach_session_scope
from app.platform.db.models import IdempotencyReceipt
from app.platform.http.errors import ApiException, _response
from app.platform.http.schemas import ApiErrorBody


class BusinessSession(Session):
    def commit(self):
        self.flush()


def policy_digest(session):
    principal = session.info.get("local_principal")
    data = {"read": sorted(map(str, session.info.get("readable_resource_ids", []))),
            "write": sorted(map(str, session.info.get("writable_resource_ids", []))),
            "capabilities": sorted(principal.capabilities) if principal else []}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class BusinessUnitOfWorkMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        subject = getattr(request.state, "policy_subject", None)
        engine = getattr(request.app.state, "database_engine", None)
        path = request.url.path
        if request.method in {"GET", "HEAD", "OPTIONS"} or path.startswith(("/api/v1/auth/", "/api/v1/admin/", "/api/v1/health/")) or not engine or not subject or not subject.authenticated:
            return await self.app(scope, receive, send)
        session = BusinessSession(engine)
        session.info["settings"] = request.app.state.settings
        session.info["request_id"] = request.state.request_id
        session.info["actor_id"] = UUID(subject.subject_id)
        scope.setdefault("state", {})["business_session"] = session
        messages = []
        try:
            await asyncio.to_thread(attach_session_scope, session, request)
            # Bound the entire body before buffering it for retry comparison.
            body_parts, length = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                part = message.get("body", b"")
                length += len(part)
                if length > 20 * 1024 * 1024:
                    raise ApiException(413, "PAYLOAD_TOO_LARGE", "请求内容超过允许上限")
                body_parts.append(part)
                if not message.get("more_body", False):
                    break
            body = b"".join(body_parts)
            consumed = False
            async def replay_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()
            key = request.headers.get("idempotency-key")
            # Secret bodies/responses never enter replay storage.
            cacheable = key and "/credentials" not in path and "/secret-stages" not in path and "/credential-operations" not in path
            route_key = f"{request.method} {path}"
            person_id = UUID(subject.subject_id)
            digest = hashlib.sha256(body).hexdigest()
            if cacheable:
                try:
                    UUID(key)
                except (ValueError, TypeError):
                    raise ApiException(422, "INVALID_IDEMPOTENCY_KEY", "幂等键必须是UUID") from None
                lock_key = int.from_bytes(hashlib.sha256(f"{person_id}:{route_key}:{key}".encode()).digest()[:8], "big", signed=True)
                def get_receipt():
                    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
                    return session.scalar(select(IdempotencyReceipt).where(IdempotencyReceipt.person_id==person_id, IdempotencyReceipt.route_key==route_key, IdempotencyReceipt.key==key))
                receipt = await asyncio.to_thread(get_receipt)
                if receipt:
                    if receipt.expires_at <= datetime.now(UTC):
                        raise ApiException(409, "IDEMPOTENCY_EXPIRED", "幂等结果已过期，请核对业务结果后使用新键")
                    if receipt.request_digest != digest:
                        raise ApiException(409, "IDEMPOTENCY_CONFLICT", "同一幂等键不能提交不同内容")
                    def fresh_policy_digest():
                        with Session(engine) as checker:
                            attach_session_scope(checker,request)
                            return policy_digest(checker)
                    if receipt.policy_digest != await asyncio.to_thread(fresh_policy_digest):
                        raise ApiException(409, "IDEMPOTENCY_SCOPE_CHANGED", "访问范围已变化，请核对业务结果")
                    result = dict(receipt.response)
                    result["meta"] = {"request_id": str(request.state.request_id)}
                    await JSONResponse(result,status_code=receipt.status_code,headers={"Idempotency-Replayed":"true"})(scope,replay_receive,send)
                    return
            async def capture(message):
                messages.append(message)
            await self.app(scope, replay_receive, capture)
            start = next(m for m in messages if m["type"]=="http.response.start")
            if start["status"] >= 400:
                await asyncio.to_thread(session.rollback)
                for callback in session.info.get("rollback_callbacks", []):
                    await asyncio.to_thread(callback)
            else:
                if cacheable:
                    response_body = b"".join(m.get("body",b"") for m in messages if m["type"]=="http.response.body")
                    session.add(IdempotencyReceipt(person_id=person_id,route_key=route_key,key=key,request_digest=digest,policy_digest=policy_digest(session),status_code=start["status"],response=json.loads(response_body),expires_at=datetime.now(UTC)+timedelta(hours=24)))
                await asyncio.to_thread(Session.commit, session)
            for message in messages:
                await send(message)
        except (ApiException, SQLAlchemyError) as error:
            await asyncio.to_thread(session.rollback)
            for callback in session.info.get("rollback_callbacks", []):
                await asyncio.to_thread(callback)
            if isinstance(error, ApiException):
                status, code, message = error.status_code, error.code, error.message
            elif isinstance(error, IntegrityError):
                status, code, message = 409, "STATE_CONFLICT", "数据与已有记录冲突，请刷新后重试"
            else:
                status, code, message = 503, "DEPENDENCY_UNAVAILABLE", "数据库操作未完成，请核对结果后重试"
            response = _response(request,status,ApiErrorBody(code=code,message=message,details=[],retryable=status==503))
            await response(scope, receive, send)
        except BaseException:
            await asyncio.to_thread(session.rollback)
            for callback in session.info.get("rollback_callbacks", []):
                await asyncio.to_thread(callback)
            raise
        finally:
            await asyncio.to_thread(session.close)
