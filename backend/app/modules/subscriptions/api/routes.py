from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,Query,Request
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.modules.identity_access.public import require_capability
from app.modules.subscriptions.api.schemas import *
from app.modules.subscriptions.application import service
from app.platform.db.models import SubscriptionLedger,SubscriptionPeriod,ExpenseEntry,ReminderItem,ReminderRead
from app.platform.db.session import database_session
from app.platform.db.commands import actor,require_idempotency_key
from app.platform.http.schemas import SuccessEnvelope,ResponseMeta
from app.platform.http.errors import ApiException

router=APIRouter(tags=["subscriptions"])
DB=Annotated[Session,Depends(database_session)]
Read=Annotated[object,Depends(require_capability("finance.read"))]
Write=Annotated[object,Depends(require_capability("finance.write"))]
ResourceRead=Annotated[object,Depends(require_capability("resource.read"))]
KEY=[Depends(require_idempotency_key)]


def env(request,data):return SuccessEnvelope(data=data,error=None,meta=ResponseMeta(request_id=request.state.request_id))


def paged(session,model,page,page_size,conditions=()):
    stmt=select(model).where(*conditions)
    total=session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=session.scalars(stmt.order_by(model.created_at.desc(),model.id).offset((page-1)*page_size).limit(page_size)).all()
    return rows,dict(page=page,page_size=page_size,total=total,has_next=page*page_size<total)


@router.post("/subscriptions",response_model=SuccessEnvelope[LedgerView],status_code=201,operation_id="createSubscription",dependencies=KEY)
def create(payload:LedgerCreate,request:Request,_:Write,session:DB):return env(request,service.ledger_view(session,service.create_ledger(session,payload,actor(request),request.state.request_id)))


@router.get("/subscriptions",response_model=SuccessEnvelope[LedgerPage],operation_id="listSubscriptions")
def listing(request:Request,_:Read,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    rows,pagination=paged(session,SubscriptionLedger,page,page_size)
    return env(request,LedgerPage(items=[service.ledger_view(session,x) for x in rows],pagination=pagination))


@router.get("/subscriptions/{ledger_id}",response_model=SuccessEnvelope[LedgerView],operation_id="getSubscription")
def detail(ledger_id:UUID,request:Request,_:Read,session:DB):return env(request,service.ledger_view(session,service.get_ledger(session,ledger_id)))


@router.patch("/subscriptions/{ledger_id}",response_model=SuccessEnvelope[LedgerView],operation_id="patchSubscription",dependencies=KEY)
def patch(ledger_id:UUID,payload:LedgerPatch,request:Request,_:Write,session:DB):return env(request,service.ledger_view(session,service.patch_ledger(session,ledger_id,payload,actor(request),request.state.request_id)))


@router.post("/subscriptions/{ledger_id}/periods",response_model=SuccessEnvelope[PeriodView],status_code=201,operation_id="addSubscriptionPeriod",dependencies=KEY)
def period(ledger_id:UUID,payload:PeriodCreate,request:Request,_:Write,session:DB):return env(request,PeriodView.model_validate(service.add_period(session,ledger_id,payload,actor(request),request.state.request_id),from_attributes=True))


@router.get("/subscriptions/{ledger_id}/periods",response_model=SuccessEnvelope[PeriodPage],operation_id="listSubscriptionPeriods")
def periods(ledger_id:UUID,request:Request,_:Read,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    service.get_ledger(session,ledger_id);rows,pagination=paged(session,SubscriptionPeriod,page,page_size,[SubscriptionPeriod.ledger_id==ledger_id])
    return env(request,PeriodPage(items=[PeriodView.model_validate(x,from_attributes=True) for x in rows],pagination=pagination))


@router.post("/subscriptions/{ledger_id}/expenses",response_model=SuccessEnvelope[ExpenseView],status_code=201,operation_id="addExpense",dependencies=KEY)
def expense(ledger_id:UUID,payload:ExpenseCreate,request:Request,_:Write,session:DB):return env(request,ExpenseView.model_validate(service.add_expense(session,ledger_id,payload,actor(request),request.state.request_id),from_attributes=True))


@router.get("/subscriptions/{ledger_id}/expenses",response_model=SuccessEnvelope[ExpensePage],operation_id="listExpenses")
def expenses(ledger_id:UUID,request:Request,_:Read,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    service.get_ledger(session,ledger_id);rows,pagination=paged(session,ExpenseEntry,page,page_size,[ExpenseEntry.ledger_id==ledger_id])
    return env(request,ExpensePage(items=[ExpenseView.model_validate(x,from_attributes=True) for x in rows],pagination=pagination))


@router.post("/subscription-periods/{entry_id}/actions/void",response_model=SuccessEnvelope[PeriodView],operation_id="voidSubscriptionPeriod",dependencies=KEY)
def void_period(entry_id:UUID,payload:VersionReason,request:Request,_:Write,session:DB):return env(request,PeriodView.model_validate(service.void_entry(session,SubscriptionPeriod,entry_id,payload,actor(request),request.state.request_id),from_attributes=True))


@router.post("/expenses/{entry_id}/actions/void",response_model=SuccessEnvelope[ExpenseView],operation_id="voidExpense",dependencies=KEY)
def void_expense(entry_id:UUID,payload:VersionReason,request:Request,_:Write,session:DB):return env(request,ExpenseView.model_validate(service.void_entry(session,ExpenseEntry,entry_id,payload,actor(request),request.state.request_id),from_attributes=True))


@router.get("/expense-summary",response_model=SuccessEnvelope[SummaryView],operation_id="getExpenseSummary")
def summary(request:Request,_:Read,session:DB):
    period=func.to_char(ExpenseEntry.recorded_on,"YYYY-MM")
    rows=session.execute(select(ExpenseEntry.currency,ExpenseEntry.kind,period,func.sum(ExpenseEntry.amount)).where(ExpenseEntry.void_reason.is_(None)).group_by(ExpenseEntry.currency,ExpenseEntry.kind,period).order_by(ExpenseEntry.currency,period)).all()
    return env(request,SummaryView(items=[MoneySummary(currency=c,kind=k,period=p,amount=a) for c,k,p,a in rows]))


@router.get("/reminders",response_model=SuccessEnvelope[ReminderPage],operation_id="listReminders")
def reminders(request:Request,_:ResourceRead,session:DB,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100)):
    from app.modules.resources.public import resource_label
    rows,pagination=paged(session,ReminderItem,page,page_size)
    read_ids=set(session.scalars(select(ReminderRead.reminder_id).where(ReminderRead.person_id==actor(request),ReminderRead.reminder_id.in_([row.id for row in rows]))))
    already_read=select(ReminderRead.id).where(ReminderRead.person_id==actor(request),ReminderRead.reminder_id==ReminderItem.id).exists()
    unread=session.scalar(select(func.count()).select_from(ReminderItem).where(ReminderItem.status=='open',~already_read))
    return env(request,ReminderPage(unread_total=unread,items=[ReminderView(id=x.id,resource_id=x.resource_id,resource_name=resource_label(session,x.resource_id),due_on=x.due_on,window_days=x.window_days,status=x.status,read=x.id in read_ids) for x in rows],pagination=pagination))


@router.post("/reminders/{reminder_id}/actions/read",response_model=SuccessEnvelope[ReminderResult],operation_id="markReminderRead",dependencies=KEY)
def read_reminder(reminder_id:UUID,request:Request,_:ResourceRead,session:DB):
    if not session.get(ReminderItem,reminder_id):raise ApiException(404,"RESOURCE_NOT_FOUND","提醒不存在或不可见")
    if not session.scalar(select(ReminderRead.id).where(ReminderRead.reminder_id==reminder_id,ReminderRead.person_id==actor(request))):session.add(ReminderRead(reminder_id=reminder_id,person_id=actor(request)))
    session.commit();return env(request,ReminderResult(processed=1))


@router.post("/reminders/actions/refresh",response_model=SuccessEnvelope[ReminderResult],operation_id="refreshReminders",dependencies=KEY)
def refresh(request:Request,_:Write,session:DB):
    count=service.refresh_due(session);session.commit();return env(request,ReminderResult(processed=count))
