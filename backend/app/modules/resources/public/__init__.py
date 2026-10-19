"""Public HTTP/application ports exposed by the resources context."""

from app.modules.resources.application.service import apply_owner_transfer, current_owner_assignment, get_resource
from app.modules.resources.api.routes import router

__all__ = ["apply_owner_transfer", "current_owner_assignment", "get_resource", "router"]


def get_facts_router():
    from app.modules.resources.api.facts import router
    return router


def get_graph_router():
    from app.modules.resources.api.graph import router
    return router


def governed_snapshot(*args,**kwargs):
    from app.modules.resources.application.governed import snapshot
    return snapshot(*args,**kwargs)

def validate_governed_change(*args,**kwargs):
    from app.modules.resources.application.governed import validate
    return validate(*args,**kwargs)

def apply_governed_change(*args,**kwargs):
    from app.modules.resources.application.governed import apply
    return apply(*args,**kwargs)

def import_resource(session,payload):
    from app.modules.resources.application.service import create_resource
    from app.modules.resources.api.schemas import ResourceCreateRequest
    return create_resource(session,ResourceCreateRequest.model_validate(payload))

def validate_import_payload(payload):
    from app.modules.resources.api.schemas import ResourceCreateRequest
    from app.modules.resources.domain.rules import validate_attributes
    value=ResourceCreateRequest.model_validate(payload)
    validate_attributes(value.type_code.value,value.attributes)
    return value.model_dump(mode='json')


def refresh_mailbox_identifier(session,resource_id,contact_id):
    from app.modules.credentials.public import protected_mailbox_identifier
    from app.platform.db.models import Account
    protected,masked=protected_mailbox_identifier(session,session.info['settings'],contact_id,resource_id)
    account=session.get(Account,resource_id)
    account.identifier_ciphertext,account.identifier_nonce,account.key_version=protected.ciphertext,protected.nonce,protected.key_version
    account.identifier_masked=masked


def directory_reference_in_use(session,kind,identifier):
    from sqlalchemy import select
    from app.platform.db.models import Resource,ResourceCompany
    table=Resource.__table__ if kind=='platform' else ResourceCompany.__table__
    condition=table.c.platform_id==identifier if kind=='platform' else (table.c.company_id==identifier)&table.c.valid_to.is_(None)
    return session.connection().execute(select(table.c.id).where(condition).limit(1)).first() is not None


def person_has_current_roles(session,person_id):
    from sqlalchemy import select,or_
    from app.platform.db.models import ResourcePerson
    from app.platform.db.commands import now
    return session.scalar(select(ResourcePerson.id).where(ResourcePerson.person_id==person_id,ResourcePerson.confirmation=='confirmed',ResourcePerson.valid_from<=now(),or_(ResourcePerson.valid_to.is_(None),ResourcePerson.valid_to>now())).limit(1)) is not None


def resource_label(session,resource_id):
    from app.platform.db.models import Resource
    row=session.get(Resource,resource_id)
    return row.name if row else '不可见资源'
