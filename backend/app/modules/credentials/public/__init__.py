"""Public HTTP ports exposed by the credentials context."""

from app.modules.credentials.api.routes import router

__all__ = ["router"]


def protect_identifier(settings, value: str, associated_data: str):
    from app.modules.credentials.application.crypto import encrypt_secret
    return encrypt_secret(settings,value,associated_data=associated_data.encode())


def apply_credential_operation(*args,**kwargs):
    from app.modules.credentials.application.operations import apply_operation
    return apply_operation(*args,**kwargs)


def get_operations_router():
    from app.modules.credentials.api.operations import router
    return router


def cleanup_ephemeral_credentials(*args,**kwargs):
    from app.modules.credentials.application.key_rotation import cleanup_ephemeral
    return cleanup_ephemeral(*args,**kwargs)


def read_connection_secret(session,settings,resource_id,credential_id,expected_version):
    # A persisted active connection is the explicit server-use authorization;
    # workers never receive an arbitrary URL or an interactive reveal grant.
    from app.platform.db.models import CredentialRef
    from app.platform.http.errors import ApiException
    from app.modules.credentials.application.crypto import decrypt_secret
    row=session.get(CredentialRef,credential_id)
    if not row or row.resource_id!=resource_id or row.status!="saved" or row.kind!="api_key" or row.version!=expected_version:
        raise ApiException(409,"CONNECTION_CREDENTIAL_CHANGED","连接凭据已变化，需要重新授权和测试")
    return decrypt_secret(settings,ciphertext=row.ciphertext,nonce=row.nonce,key_version=row.key_version,associated_data=f"credential:{row.id}".encode())


def protected_mailbox_identifier(session,settings,contact_id,resource_id):
    from app.platform.db.models import ContactIdentity
    from app.modules.credentials.application.crypto import decrypt_secret,encrypt_secret
    from app.platform.http.errors import ApiException
    contact=session.get(ContactIdentity,contact_id)
    if not contact or contact.kind!='email':raise ApiException(404,'REFERENCE_NOT_FOUND','邮箱身份不存在或不可见')
    value=decrypt_secret(settings,ciphertext=contact.protected_value,nonce=contact.nonce,key_version=contact.key_version,associated_data=f'contact-identity:{contact.id}'.encode())
    return encrypt_secret(settings,value,associated_data=f'account-identifier:{resource_id}'.encode()),contact.masked_value


def resource_credential_status(session,resource_id):
    from sqlalchemy import select
    from app.platform.db.models import CredentialRef
    result=session.scalar(select(CredentialRef.status).where(CredentialRef.resource_id==resource_id).order_by((CredentialRef.status=='saved').desc(),CredentialRef.created_at.desc()).limit(1))
    return result or 'not_saved'


def credential_operation_snapshot(session,operation_id,resource_id,action,credential_id=None,grant_id=None):
    from app.modules.credentials.application.operations import validate_operation_snapshot
    return validate_operation_snapshot(session,operation_id,resource_id,action,credential_id,grant_id)
