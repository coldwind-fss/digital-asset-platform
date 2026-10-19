"""Protected registration identities, separate from actual mailbox accounts."""
import re
from uuid import uuid4
from app.modules.credentials.public import protect_identifier
from app.platform.db.models import ContactIdentity, MailboxContactAssociation, Company, Person
from app.platform.http.errors import ApiException


def create_contact_identity(session, *, kind, value, ownership="unknown", label=None, provider=None, company_id=None, custodian_person_id=None):
    value=value.strip()
    if kind not in {"phone","email","third_party"} or not value or len(value)>320:
        raise ApiException(422,"VALIDATION_FAILED","身份类型或实际内容不正确")
    if kind=="email" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",value):
        raise ApiException(422,"VALIDATION_FAILED","邮箱格式不正确")
    if kind=="phone" and not re.fullmatch(r"\+?[0-9 ()-]{5,30}",value):
        raise ApiException(422,"VALIDATION_FAILED","手机或电话格式不正确")
    if kind=="third_party" and not provider:
        raise ApiException(422,"VALIDATION_FAILED","第三方身份需要提供身份平台")
    for model,target in ((Company,company_id),(Person,custodian_person_id)):
        if target and not session.get(model,target):
            raise ApiException(404,"REFERENCE_NOT_FOUND","身份关联对象不存在或不可见")
    settings=session.info.get("settings")
    if settings is None:
        raise ApiException(503,"DEPENDENCY_UNAVAILABLE","受保护身份存储尚未配置")
    identity=ContactIdentity(id=uuid4(),kind=kind,ownership=ownership,label=label,provider=provider,company_id=company_id,custodian_person_id=custodian_person_id)
    protected=protect_identifier(settings,value,f"contact-identity:{identity.id}")
    identity.protected_value,identity.nonce,identity.key_version=protected.ciphertext,protected.nonce,protected.key_version
    identity.masked_value=value[:2]+"***"+(value[-2:] if len(value)>4 else "")
    session.add(identity);session.flush()
    return identity


def create_mailbox_contacts(session, resource, payload):
    for role,value in [("primary",payload.get("identifier"))]+[("alias",x) for x in payload.get("aliases",[])]:
        if not value:continue
        contact=create_contact_identity(session,kind="email",value=value,ownership="unknown")
        session.add(MailboxContactAssociation(mailbox_account_id=resource.id,contact_identity_id=contact.id,role=role,confirmation="proposed"))
