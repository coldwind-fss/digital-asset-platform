"""Offline envelope re-encryption; never changes an external platform secret."""
from uuid import uuid4
from sqlalchemy import select,delete
from app.modules.credentials.application.crypto import decrypt_secret,encrypt_secret
from app.platform.db.models import CredentialRef,CredentialStage,CredentialOperation,Account,ContactIdentity,AuditEvent
from app.platform.db.commands import now
from app.platform.http.errors import ApiException


def rotate_material(session,settings):
    targets=[(CredentialRef,"ciphertext","nonce","credential","id"),(CredentialStage,"ciphertext","nonce","credential-stage","id"),(CredentialOperation,"ciphertext","nonce","credential-operation","id"),(Account,"identifier_ciphertext","identifier_nonce","account-identifier","resource_id"),(ContactIdentity,"protected_value","nonce","contact-identity","id")]
    count=0;versions=set()
    for model,column,nonce,prefix,id_field in targets:
        rows=session.scalars(select(model).where(getattr(model,column).is_not(None)).with_for_update()).all()
        for row in rows:
            if row.key_version==settings.credential_key_version:continue
            if not getattr(row,nonce):raise ApiException(409,"KEY_ROTATION_UNSUPPORTED","存在缺少认证nonce的历史材料，不能跳过后声称完成")
            versions.add(row.key_version)
            associated_data=f"{prefix}:{getattr(row,id_field)}".encode()
            value=decrypt_secret(settings,ciphertext=getattr(row,column),nonce=getattr(row,nonce),key_version=row.key_version,associated_data=associated_data)
            replacement=encrypt_secret(settings,value,associated_data=associated_data)
            setattr(row,column,replacement.ciphertext);setattr(row,nonce,replacement.nonce);row.key_version=replacement.key_version
            if isinstance(row,CredentialRef):row.version+=1;row.updated_at=now()
            count+=1
    session.add(AuditEvent(actor_kind="system",event_type="credential.master_key_reencrypted",request_id=uuid4(),safe_after={"rows":count,"from_versions":sorted(versions),"to_version":settings.credential_key_version}))
    session.flush();return {"rows_reencrypted":count,"from_versions":sorted(versions),"to_version":settings.credential_key_version}


def cleanup_ephemeral(session,instant=None):
    instant=instant or now()
    for operation in session.scalars(select(CredentialOperation).where(CredentialOperation.status=="prepared",CredentialOperation.expires_at<=instant).with_for_update()):
        operation.status="cancelled";operation.ciphertext=operation.nonce=operation.key_version=None;operation.stage_id=None
    session.flush()
    referenced=select(CredentialOperation.stage_id).where(CredentialOperation.stage_id.is_not(None))
    result=session.execute(delete(CredentialStage).where(CredentialStage.expires_at<=instant,CredentialStage.id.not_in(referenced)))
    return result.rowcount
