"""Public HTTP ports exposed by the bindings context."""

from app.modules.bindings.api.routes import router
from app.modules.bindings.application.governed import binding_snapshot,apply_binding_change

def company_identity_in_use(session,company_id):
    from sqlalchemy import select
    from app.platform.db.models import ContactIdentity
    table=ContactIdentity.__table__
    return session.connection().execute(select(table.c.id).where(table.c.company_id==company_id).limit(1)).first() is not None

def graph_contacts(session,resource_id):
    from sqlalchemy import select,or_
    from app.platform.db.models import AccountBinding
    from app.platform.db.commands import now
    return [('identity',r.contact_identity_id,r.purpose,r.confirmation,r.id,False) for r in session.scalars(select(AccountBinding).where(AccountBinding.account_resource_id==resource_id,AccountBinding.confirmation!='rejected',AccountBinding.valid_from<=now(),or_(AccountBinding.valid_to.is_(None),AccountBinding.valid_to>now())).limit(101))]

__all__ = ["router"]

def graph_identity_resources(session,identifier):
    from sqlalchemy import select,or_
    from app.platform.db.models import AccountBinding, Resource
    from app.platform.db.commands import now
    return session.scalars(select(AccountBinding.account_resource_id).join(Resource,Resource.id==AccountBinding.account_resource_id).where(Resource.archived_at.is_(None),AccountBinding.contact_identity_id==identifier,AccountBinding.confirmation!='rejected',AccountBinding.valid_from<=now(),or_(AccountBinding.valid_to.is_(None),AccountBinding.valid_to>now())).distinct().order_by(AccountBinding.account_resource_id).limit(101)).all()


def create_contact_identity(*args, **kwargs):
    from app.modules.bindings.application.identities import create_contact_identity as create
    return create(*args, **kwargs)


def create_mailbox_contacts(*args, **kwargs):
    from app.modules.bindings.application.identities import create_mailbox_contacts as create
    return create(*args, **kwargs)
