"""Request-bound row filtering shared by existing business modules.

Only the local authenticated adapter installs this filter. Test adapters remain
explicit and isolated. Every owning module still validates its business rules.
"""
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import event, or_, select
from sqlalchemy.orm import Session, with_loader_criteria

from app.modules.identity_access.application.service import LocalPrincipal
from app.platform.db.models import (
    Account, AccountBinding, AuditEvent, AuthScope, ChangeCase, ChangeItem,
    ChangeRelationDetail, Company, ContactIdentity, CredentialGrant,
    CredentialRef, CredentialStage, Department, MailboxContactAssociation,
    Material, Person, Resource, ResourceCompany, ResourcePerson,
    ResourceRelation, SubscriptionBudget, SubscriptionProfile,
    RelationDeclaration, ProvenanceEntry, CredentialOperation, SubscriptionLedger,
    SubscriptionPeriod, ExpenseEntry, ReminderItem, ReminderRead,
    PlatformConnection, SyncJob, MetricSnapshot, PrivateFile, ImportBatch, NotificationPreference,
)
from app.platform.http.errors import ApiException


def attach_scope(session: Session, principal: LocalPrincipal) -> None:
    instant = datetime.now(UTC)
    administrator = principal.role == "admin"
    scopes = session.scalars(select(AuthScope).where(AuthScope.account_id == principal.account_id)).all()
    read_departments = {s.target_id for s in scopes if s.kind == "department"}
    managed_departments = {s.target_id for s in scopes if s.kind == "department" and s.permission == "manage"}
    explicit_read = {s.target_id for s in scopes if s.kind == "resource"}
    explicit_manage = {s.target_id for s in scopes if s.kind == "resource" and s.permission == "manage"}
    assignments = session.execute(select(ResourcePerson.resource_id, ResourcePerson.role).where(
        ResourcePerson.person_id == principal.person_id, ResourcePerson.confirmation == "confirmed",
        ResourcePerson.valid_from <= instant, or_(ResourcePerson.valid_to.is_(None), ResourcePerson.valid_to > instant),
    )).all()
    related = {r.resource_id for r in assignments}
    managed = {r.resource_id for r in assignments if r.role in {"owner", "maintainer", "controller"}}
    rows = session.execute(select(Resource.id, Resource.owning_department_id, Resource.created_by_person_id, Resource.visibility_scope)).all()
    readable, writable = set(explicit_read), set(explicit_manage)
    for row in rows:
        mine = row.created_by_person_id == principal.person_id
        if administrator or mine or row.id in related or row.owning_department_id in read_departments or row.visibility_scope == "company" or (principal.department_id and row.owning_department_id == principal.department_id and row.visibility_scope == "department"):
            readable.add(row.id)
        if administrator or mine or row.id in managed or row.owning_department_id in managed_departments:
            writable.add(row.id)
    readable |= writable
    person_ids = {principal.person_id}
    person_ids |= set(session.scalars(select(ResourcePerson.person_id).where(ResourcePerson.resource_id.in_(readable))))
    department_ids = read_departments | ({principal.department_id} if principal.department_id else set())
    if managed_departments:
        person_ids |= set(session.scalars(select(Person.id).where(Person.department_id.in_(managed_departments))))
    company_ids = set(session.scalars(select(ResourceCompany.company_id).where(ResourceCompany.resource_id.in_(readable))))
    company_ids |= set(session.scalars(select(Company.id).where(Company.created_by_person_id==principal.person_id)))
    department_ids |= {row.owning_department_id for row in rows if row.id in readable and row.owning_department_id}
    credential_ids = set(session.scalars(select(CredentialRef.id).where(CredentialRef.resource_id.in_(readable))))
    contact_ids = set(session.scalars(select(AccountBinding.contact_identity_id).where(AccountBinding.account_resource_id.in_(readable))))
    contact_ids |= set(session.scalars(select(MailboxContactAssociation.contact_identity_id).where(MailboxContactAssociation.mailbox_account_id.in_(readable))))
    contact_ids |= set(session.scalars(select(ContactIdentity.id).where(ContactIdentity.custodian_person_id == principal.person_id)))
    contact_ids |= set(session.scalars(select(ContactIdentity.id).where(ContactIdentity.created_by_person_id == principal.person_id)))
    # A visible pending proposal must expose its non-secret reference targets to
    # the independent reviewer, without broadening resource or secret access.
    for proposed in session.scalars(select(ChangeItem).where(ChangeItem.resource_id.in_(readable))):
        if proposed.to_person_id:person_ids.add(proposed.to_person_id)
        if proposed.new_contact_identity_id:contact_ids.add(proposed.new_contact_identity_id)
        proposal=(proposed.proposal_json or {}).get('proposal',{})
        for field,targets in [('company_id',company_ids),('owning_department_id',department_ids)]:
            if proposal.get(field):targets.add(UUID(proposal[field]))
    cases = session.scalars(select(ChangeCase)).all()
    items = session.execute(select(ChangeItem.case_id, ChangeItem.resource_id)).all()
    case_ids = {c.id for c in cases if c.created_by_person_id == principal.person_id or c.coordinator_person_id == principal.person_id}
    for item in items:
        if item.resource_id in readable:
            case_ids.add(item.case_id)
    # A case-level reason can describe all its items. Do not expose mixed-scope cases.
    case_ids -= {i.case_id for i in items if i.resource_id not in readable}
    writable_case_ids = {c.id for c in cases if c.id in case_ids and (
        c.created_by_person_id == principal.person_id or c.coordinator_person_id == principal.person_id or principal.role == "resource_manager")}
    writable_case_ids -= {i.case_id for i in items if i.resource_id not in writable}
    item_ids = set(session.scalars(select(ChangeItem.id).where(ChangeItem.case_id.in_(case_ids), ChangeItem.resource_id.in_(readable))))
    writable_item_ids = set(session.scalars(select(ChangeItem.id).where(ChangeItem.case_id.in_(writable_case_ids), ChangeItem.resource_id.in_(writable))))
    session.info.update(local_principal=principal, readable_resource_ids=readable, writable_resource_ids=writable, writable_case_ids=writable_case_ids)

    resource_models = {
        Account: Account.resource_id, ResourcePerson: ResourcePerson.resource_id,
        ResourceCompany: ResourceCompany.resource_id, AccountBinding: AccountBinding.account_resource_id,
        MailboxContactAssociation: MailboxContactAssociation.mailbox_account_id,
        CredentialRef: CredentialRef.resource_id, SubscriptionProfile: SubscriptionProfile.resource_id,
        SubscriptionBudget: SubscriptionBudget.resource_id, Material: Material.resource_id,
        RelationDeclaration: RelationDeclaration.resource_id, ProvenanceEntry: ProvenanceEntry.resource_id,
        CredentialOperation: CredentialOperation.resource_id, SubscriptionLedger: SubscriptionLedger.resource_id,
        SubscriptionPeriod: SubscriptionPeriod.resource_id, ExpenseEntry: ExpenseEntry.resource_id,
        ReminderItem: ReminderItem.resource_id, PlatformConnection: PlatformConnection.resource_id,
        SyncJob: SyncJob.resource_id, MetricSnapshot: MetricSnapshot.resource_id, PrivateFile: PrivateFile.resource_id,
    }

    @event.listens_for(session, "do_orm_execute")
    def filter_rows(state):
        if not (state.is_select or state.is_update or state.is_delete):
            return
        options = []
        if not administrator:
            ids = readable if state.is_select else writable
            options.append(with_loader_criteria(Resource, Resource.id.in_(ids), include_aliases=True))
            for model, column in resource_models.items():
                options.append(with_loader_criteria(model, column.in_(ids), include_aliases=True))
            options += [
                with_loader_criteria(ResourceRelation, ResourceRelation.source_resource_id.in_(ids) & ResourceRelation.target_resource_id.in_(readable), include_aliases=True),
                with_loader_criteria(Person, Person.id.in_(person_ids), include_aliases=True),
                with_loader_criteria(Department, Department.id.in_(department_ids), include_aliases=True),
                with_loader_criteria(Company, Company.id.in_(company_ids), include_aliases=True),
                with_loader_criteria(ContactIdentity, ContactIdentity.id.in_(contact_ids), include_aliases=True),
                with_loader_criteria(CredentialGrant, CredentialGrant.credential_id.in_(credential_ids), include_aliases=True),
                with_loader_criteria(ChangeCase, ChangeCase.id.in_(case_ids if state.is_select else writable_case_ids), include_aliases=True),
                with_loader_criteria(ChangeItem, ChangeItem.id.in_(item_ids if state.is_select else writable_item_ids), include_aliases=True),
                with_loader_criteria(ChangeRelationDetail, ChangeRelationDetail.item_id.in_(item_ids if state.is_select else writable_item_ids), include_aliases=True),
                with_loader_criteria(AuditEvent, AuditEvent.resource_id.in_(ids) | ((AuditEvent.resource_id.is_(None)) & (AuditEvent.actor_person_id == principal.person_id)), include_aliases=True),
            ]
        if "materials.restricted" not in principal.capabilities:
            options.append(with_loader_criteria(Material, Material.classification == "normal", include_aliases=True))
            options.append(with_loader_criteria(PrivateFile, PrivateFile.classification == "normal", include_aliases=True))
        if "finance.read" not in principal.capabilities:
            for model in (SubscriptionLedger,SubscriptionPeriod,ExpenseEntry,MetricSnapshot):
                options.append(with_loader_criteria(model,False,include_aliases=True))
        options.append(with_loader_criteria(ImportBatch,ImportBatch.created_by_person_id==principal.person_id,include_aliases=True))
        options.append(with_loader_criteria(ReminderRead,ReminderRead.person_id==principal.person_id,include_aliases=True))
        options.append(with_loader_criteria(NotificationPreference,NotificationPreference.person_id==principal.person_id,include_aliases=True))
        options.append(with_loader_criteria(CredentialStage, CredentialStage.created_by_person_id == principal.person_id, include_aliases=True))
        state.statement = state.statement.options(*options)

    @event.listens_for(session, "before_flush")
    def protect_writes(current_session, _context, _instances):
        for row in list(current_session.new):
            if isinstance(row, Resource):
                row.id = row.id or uuid4()
                row.created_by_person_id = principal.person_id
                readable.add(row.id)
                writable.add(row.id)
            elif isinstance(row, Company):
                row.id=row.id or uuid4()
                row.created_by_person_id=principal.person_id
                company_ids.add(row.id)
            elif isinstance(row, ContactIdentity):
                row.id=row.id or uuid4()
                row.created_by_person_id=principal.person_id
                contact_ids.add(row.id)
            elif isinstance(row, CredentialStage):
                row.created_by_person_id = principal.person_id
            elif isinstance(row, ChangeCase):
                row.id = row.id or uuid4()
                row.created_by_person_id = principal.person_id
                case_ids.add(row.id)
                writable_case_ids.add(row.id)
            elif isinstance(row, ChangeItem):
                row.id = row.id or uuid4()
                item_ids.add(row.id)
                if row.case_id in writable_case_ids and row.resource_id in writable:
                    writable_item_ids.add(row.id)
        if administrator:
            return
        for row in list(current_session.new) + list(current_session.dirty) + list(current_session.deleted):
            target = None
            if isinstance(row, ChangeCase) and row.id not in writable_case_ids:
                raise ApiException(403, "PERMISSION_DENIED", "当前事项仅允许查阅，不能修改")
            if isinstance(row, ChangeItem) and row.case_id not in writable_case_ids:
                raise ApiException(403, "PERMISSION_DENIED", "当前事项仅允许查阅，不能修改")
            if isinstance(row, ChangeRelationDetail) and row.item_id not in writable_item_ids:
                raise ApiException(403, "PERMISSION_DENIED", "当前事项仅允许查阅，不能修改")
            if isinstance(row, Resource):
                target = row.id
            elif isinstance(row, ResourceRelation):
                target = row.source_resource_id
                if row.target_resource_id not in readable:
                    raise ApiException(404, "REFERENCE_NOT_FOUND", "关联对象不存在或不可见")
            elif type(row) in resource_models or isinstance(row, ChangeItem):
                target = getattr(row, "resource_id", None) or getattr(row, "account_resource_id", None) or getattr(row, "mailbox_account_id", None)
            if target is not None and target not in writable:
                # Read access to an object does not authorize its modification.
                raise ApiException(403, "PERMISSION_DENIED", "当前对象仅允许查阅，不能修改")
