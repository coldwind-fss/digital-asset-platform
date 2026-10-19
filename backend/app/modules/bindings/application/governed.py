from sqlalchemy import select
from app.platform.db.models import AccountBinding,ContactIdentity,MailboxContactAssociation,Resource
from app.platform.db.commands import now
from app.platform.http.errors import ApiException


def binding_snapshot(session,resource_id,proposal):
    target=session.get(ContactIdentity,proposal.new_contact_identity_id)
    if not target:raise ApiException(404,'REFERENCE_NOT_FOUND','注册身份不存在或不可见')
    if proposal.action=='change_mailbox_address' and (target.kind!='email' or session.get(Resource,resource_id).type_code!='mailbox_account'):raise ApiException(422,'VALIDATION_FAILED','邮箱地址变更仅接受邮箱资源与邮箱身份')
    rows=session.scalars(select(AccountBinding).where(AccountBinding.account_resource_id==resource_id,AccountBinding.valid_to.is_(None))).all()
    if proposal.binding_id and not any(x.id==proposal.binding_id for x in rows):raise ApiException(409,'STATE_CONFLICT','绑定事实已变化')
    return {'bindings':sorted([[str(x.id),x.version] for x in rows]),'target_version':target.version}


def apply_binding_change(session,resource_id,proposal):
    binding_snapshot(session,resource_id,proposal)
    if proposal.binding_id:
        old=session.get(AccountBinding,proposal.binding_id);old.valid_to=now();old.version+=1
        purpose=getattr(proposal,'purpose',None) or old.purpose
    else:purpose='login'
    session.flush()
    session.add(AccountBinding(account_resource_id=resource_id,contact_identity_id=proposal.new_contact_identity_id,purpose=purpose,confirmation='confirmed'))
    if proposal.action=='change_mailbox_address':
        for old in session.scalars(select(MailboxContactAssociation).where(MailboxContactAssociation.mailbox_account_id==resource_id,MailboxContactAssociation.role=='primary',MailboxContactAssociation.valid_to.is_(None))):old.valid_to=now();old.version+=1
        session.flush()
        session.add(MailboxContactAssociation(mailbox_account_id=resource_id,contact_identity_id=proposal.new_contact_identity_id,role='primary',confirmation='confirmed'))
