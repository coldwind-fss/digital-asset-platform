from datetime import date,datetime,UTC,timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select,func,or_,text
from app.modules.resources.public import get_resource
from app.modules.subscriptions.api.schemas import LedgerView,PeriodView
from app.platform.db.models import SubscriptionLedger,SubscriptionPeriod,ExpenseEntry,ReminderItem,ReminderRead,Resource,ResourcePerson
from app.platform.db.commands import now,write_resource,record_event
from app.platform.http.errors import ApiException


def workspace_today(instant=None):return (instant or now()).astimezone(ZoneInfo("Asia/Shanghai")).date()


def ledger_view(session,row,today=None):
    today=today or workspace_today()
    current=session.scalar(select(SubscriptionPeriod).where(SubscriptionPeriod.ledger_id==row.id,SubscriptionPeriod.void_reason.is_(None),SubscriptionPeriod.starts_on<=today,SubscriptionPeriod.ends_on>=today))
    users=session.scalar(select(func.count(func.distinct(ResourcePerson.person_id))).where(ResourcePerson.resource_id==row.resource_id,ResourcePerson.role=="use",ResourcePerson.confirmation=="confirmed",ResourcePerson.valid_from<=now(),or_(ResourcePerson.valid_to.is_(None),ResourcePerson.valid_to>now())))
    return LedgerView(id=row.id,resource_id=row.resource_id,plan=row.plan,seats_total=row.seats_total,seats_assigned=row.seats_assigned,billing_cycle=row.billing_cycle,reminder_days=row.reminder_days,version=row.version,current_period=PeriodView.model_validate(current,from_attributes=True) if current else None,active_users=users or 0)


def get_ledger(session,ledger_id,version=None,writing=False):
    row=session.get(SubscriptionLedger,ledger_id)
    if not row:raise ApiException(404,"RESOURCE_NOT_FOUND","订阅不存在或不可见")
    if writing:
        write_resource(session,row.resource_id)
        row=session.scalar(select(SubscriptionLedger).where(SubscriptionLedger.id==ledger_id).with_for_update().execution_options(populate_existing=True))
    if version is not None and row.version!=version:raise ApiException(409,"STATE_CONFLICT","订阅版本已变化")
    return row


def changed(session,ledger,actor,request_id,event,data):
    ledger.version+=1;ledger.updated_at=now()
    resource=write_resource(session,ledger.resource_id)
    resource.version+=1;resource.updated_at=now()
    record_event(session,event,actor,request_id,ledger.resource_id,data)
    session.flush()


def create_ledger(session,payload,actor,request_id):
    resource=write_resource(session,payload.resource_id)
    if session.scalar(select(SubscriptionLedger.id).where(SubscriptionLedger.resource_id==resource.id)):raise ApiException(409,"SUBSCRIPTION_EXISTS","该资源已有订阅账本")
    row=SubscriptionLedger(**payload.model_dump())
    session.add(row);session.flush()
    record_event(session,"subscription.created",actor,request_id,resource.id,{"ledger_id":str(row.id)})
    resource.version+=1;resource.updated_at=now();session.commit();return row


def patch_ledger(session,ledger_id,payload,actor,request_id):
    row=get_ledger(session,ledger_id,payload.expected_version,True)
    data={k:v for k,v in payload.model_dump().items() if k in payload.model_fields_set and k not in {"expected_version","reason"}}
    if not data:raise ApiException(422,"VALIDATION_FAILED","至少修改一项订阅资料")
    total=data.get("seats_total",row.seats_total);assigned=data.get("seats_assigned",row.seats_assigned)
    if total is not None and assigned is not None and assigned>total:raise ApiException(422,"VALIDATION_FAILED","已分配席位不能超过总席位")
    for k,v in data.items():setattr(row,k,v)
    changed(session,row,actor,request_id,"subscription.updated",{"reason":payload.reason,"fields":sorted(data)})
    session.commit();return row


def add_period(session,ledger_id,payload,actor,request_id):
    row=get_ledger(session,ledger_id,payload.expected_version,True)
    overlap=session.scalar(select(SubscriptionPeriod.id).where(SubscriptionPeriod.ledger_id==row.id,SubscriptionPeriod.void_reason.is_(None),SubscriptionPeriod.starts_on<=payload.ends_on,SubscriptionPeriod.ends_on>=payload.starts_on))
    if overlap:raise ApiException(409,"PERIOD_OVERLAP","有效订阅周期不能重叠，请先明确作废错误记录")
    period=SubscriptionPeriod(**payload.model_dump(exclude={"expected_version"}),ledger_id=row.id,resource_id=row.resource_id,created_by_person_id=actor)
    session.add(period);session.flush()
    changed(session,row,actor,request_id,"subscription.period_added",{"period_id":str(period.id)})
    refresh_due(session)
    session.commit();return period


def add_expense(session,ledger_id,payload,actor,request_id):
    row=get_ledger(session,ledger_id,payload.expected_version,True)
    if payload.period_id:
        period=session.get(SubscriptionPeriod,payload.period_id)
        if not period or period.ledger_id!=row.id or period.void_reason:raise ApiException(404,"REFERENCE_NOT_FOUND","有效周期不存在或不属于当前订阅")
    if payload.corrects_entry_id:
        old=session.get(ExpenseEntry,payload.corrects_entry_id)
        if not old or old.ledger_id!=row.id or not old.void_reason:raise ApiException(409,"CORRECTION_CONFLICT","更正必须引用本订阅已明确作废的费用记录")
    entry=ExpenseEntry(**payload.model_dump(exclude={"expected_version"}),ledger_id=row.id,resource_id=row.resource_id,created_by_person_id=actor)
    session.add(entry);session.flush()
    changed(session,row,actor,request_id,"subscription.expense_added",{"entry_id":str(entry.id),"kind":entry.kind,"currency":entry.currency})
    session.commit();return entry


def void_entry(session,model,entry_id,payload,actor,request_id):
    entry=session.get(model,entry_id)
    if not entry:raise ApiException(404,"RESOURCE_NOT_FOUND","记录不存在或不可见")
    ledger=get_ledger(session,entry.ledger_id,writing=True)
    entry=session.scalar(select(model).where(model.id==entry_id).with_for_update().execution_options(populate_existing=True))
    if entry.version!=payload.expected_version or entry.void_reason:raise ApiException(409,"STATE_CONFLICT","记录已更新或已作废")
    entry.void_reason=payload.reason;entry.version+=1
    changed(session,ledger,actor,request_id,"subscription.record_voided",{"entry_id":str(entry.id),"reason":payload.reason})
    refresh_due(session);session.commit();return entry


def refresh_due(session,instant=None):
    # Shared by worker and write use cases; callers own the transaction.
    session.execute(text("SELECT pg_advisory_xact_lock(731004212)"))
    today=workspace_today(instant)
    principal=session.info.get("local_principal")
    writable=session.info.get("writable_resource_ids",set())
    def allowed(resource_id):return principal is None or principal.role=="admin" or resource_id in writable
    periods=session.scalars(select(SubscriptionPeriod).where(SubscriptionPeriod.void_reason.is_(None))).all()
    candidates=[]
    by_resource={}
    for period in periods:by_resource.setdefault(period.resource_id,[]).append(period)
    for period in periods:
        resource=session.get(Resource,period.resource_id)
        ledger=session.get(SubscriptionLedger,period.ledger_id)
        if not resource or not allowed(resource.id) or resource.archived_at or resource.lifecycle in {"disabled","retired"}:continue
        renewed=any(other.starts_on<=period.ends_on+timedelta(days=1) and other.ends_on>period.ends_on for other in by_resource[period.resource_id])
        if not renewed:candidates.append((resource.id,period.id,period.ends_on,ledger.reminder_days))
    for resource in session.scalars(select(Resource).where(Resource.type_code=="domain",Resource.archived_at.is_(None),Resource.lifecycle.not_in(["disabled","retired"]))):
        if not allowed(resource.id) or resource.id in by_resource or not (resource.attributes or {}).get("expires_on"):continue
        candidates.append((resource.id,None,date.fromisoformat(resource.attributes["expires_on"]),[30,7,1]))
    active=set()
    for resource_id,period_id,due,windows in candidates:
        days=(due-today).days
        eligible=[window for window in windows if days<=window]
        for window in ([min(eligible)] if eligible else []):
            key=(resource_id,period_id,due,window);active.add(key)
            row=session.scalar(select(ReminderItem).where(ReminderItem.resource_id==resource_id,ReminderItem.period_id==period_id,ReminderItem.due_on==due,ReminderItem.window_days==window))
            if not row:session.add(ReminderItem(resource_id=resource_id,period_id=period_id,due_on=due,window_days=window,status="open"))
            elif row.status!="open":row.status="open";row.resolved_at=None
    session.flush()
    for item in session.scalars(select(ReminderItem).where(ReminderItem.status=="open")):
        if not allowed(item.resource_id):continue
        if (item.resource_id,item.period_id,item.due_on,item.window_days) not in active:item.status="resolved";item.resolved_at=instant or now()
    session.flush();return len(active)
