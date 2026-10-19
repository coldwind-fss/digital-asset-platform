from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from app.modules.credentials.application.crypto import encrypt_secret,decrypt_secret,hash_stage_token
from app.platform.db.models import CredentialRef,CredentialStage,CredentialGrant,CredentialOperation
from app.platform.db.commands import now,write_resource,record_event
from app.platform.http.errors import ApiException


def prepare_operation(session,settings,credential_id,payload,actor_id,request_id):
    ref=session.get(CredentialRef,credential_id)
    if not ref:raise ApiException(404,"RESOURCE_NOT_FOUND","凭据不存在或不可见")
    write_resource(session,ref.resource_id)
    ref=session.scalar(select(CredentialRef).where(CredentialRef.id==credential_id).with_for_update().execution_options(populate_existing=True))
    if ref.version!=payload.expected_version or ref.status!="saved":raise ApiException(409,"STATE_CONFLICT","凭据版本或状态已变化")
    operation=CredentialOperation(id=uuid4(),resource_id=ref.resource_id,credential_id=ref.id,action=payload.action,expected_credential_version=ref.version,created_by_person_id=actor_id,expires_at=now()+timedelta(hours=24))
    if payload.action=="replace":
        stage=session.scalar(select(CredentialStage).where(CredentialStage.token_hash==hash_stage_token(payload.stage_token or "")).with_for_update().execution_options(populate_existing=True))
        if not stage or stage.created_by_person_id!=actor_id or stage.consumed_at or stage.expires_at<=now() or stage.resource_id!=ref.resource_id or stage.purpose!="replace" or stage.kind!=ref.kind:
            raise ApiException(410,"STAGE_EXPIRED","替换暂存无效、过期或不属于此主体/资源")
        plaintext=decrypt_secret(settings,ciphertext=stage.ciphertext,nonce=stage.nonce,key_version=stage.key_version,associated_data=f"credential-stage:{stage.id}".encode())
        encrypted=encrypt_secret(settings,plaintext,associated_data=f"credential-operation:{operation.id}".encode())
        operation.ciphertext,operation.nonce,operation.key_version=encrypted.ciphertext,encrypted.nonce,encrypted.key_version
        stage.consumed_at=now()
    elif payload.action=="revoke_grant":
        grant=session.get(CredentialGrant,payload.grant_id)
        if not grant or grant.credential_id!=ref.id or (grant.valid_to and grant.valid_to<=now()):raise ApiException(404,"RESOURCE_NOT_FOUND","有效授权不存在")
        operation.grant_id=grant.id
    session.add(operation);session.flush()
    record_event(session,"credential.operation_prepared",actor_id,request_id,ref.resource_id,{"operation_id":str(operation.id),"action":operation.action,"reason":payload.reason})
    session.commit();return operation


def apply_operation(session,settings,operation_id,resource_id,actor_id,request_id):
    operation=session.scalar(select(CredentialOperation).where(CredentialOperation.id==operation_id).with_for_update())
    if not operation or operation.resource_id!=resource_id:raise ApiException(404,"RESOURCE_NOT_FOUND","凭据操作不存在或不可见")
    if operation.status!="prepared" or operation.expires_at<=now():raise ApiException(409,"OPERATION_EXPIRED","凭据操作已使用或过期")
    ref=session.scalar(select(CredentialRef).where(CredentialRef.id==operation.credential_id).with_for_update())
    if ref.status!="saved" or ref.version!=operation.expected_credential_version:raise ApiException(409,"STATE_CONFLICT","凭据已变化，需要重新准备操作")
    if operation.action=="replace":
        value=decrypt_secret(settings,ciphertext=operation.ciphertext,nonce=operation.nonce,key_version=operation.key_version,associated_data=f"credential-operation:{operation.id}".encode())
        replacement=CredentialRef(id=uuid4(),resource_id=resource_id,kind=ref.kind,status="saved")
        encrypted=encrypt_secret(settings,value,associated_data=f"credential:{replacement.id}".encode())
        replacement.ciphertext,replacement.nonce,replacement.key_version=encrypted.ciphertext,encrypted.nonce,encrypted.key_version
        ref.status="superseded"
        session.flush()
        session.add(replacement);session.flush()
        operation.result_credential_id=replacement.id
    elif operation.action=="revoke":ref.status="revoked"
    elif operation.action=="revoke_grant":
        grant=session.scalar(select(CredentialGrant).where(CredentialGrant.id==operation.grant_id).with_for_update())
        if not grant or (grant.valid_to and grant.valid_to<=now()):raise ApiException(409,"STATE_CONFLICT","授权已结束")
        grant.valid_to=now();grant.version+=1
    if operation.action in {"replace","revoke"}:
        for grant in session.scalars(select(CredentialGrant).where(CredentialGrant.credential_id==ref.id,((CredentialGrant.valid_to.is_(None))|(CredentialGrant.valid_to>now())))):
            grant.valid_to=now();grant.version+=1
    ref.version+=1;ref.updated_at=now();operation.status="applied"
    operation.ciphertext=operation.nonce=operation.key_version=None
    record_event(session,"credential.operation_applied",actor_id,request_id,resource_id,{"operation_id":str(operation.id),"action":operation.action})
    session.flush();return operation


def validate_operation_snapshot(session,operation_id,resource_id,action,credential_id=None,grant_id=None):
    operation=session.get(CredentialOperation,operation_id)
    if not operation or operation.resource_id!=resource_id or operation.action!=action or operation.status!='prepared' or operation.expires_at<=now():raise ApiException(409,'STATE_CONFLICT','需要此资源下尚未过期的对应凭据操作')
    if (credential_id and operation.credential_id!=credential_id) or (grant_id and operation.grant_id!=grant_id):raise ApiException(422,'VALIDATION_FAILED','提案与凭据操作不匹配')
    ref=session.get(CredentialRef,operation.credential_id)
    if not ref or ref.status!='saved' or ref.version!=operation.expected_credential_version:raise ApiException(409,'STATE_CONFLICT','凭据版本已变化')
    return {'credential_version':ref.version}
