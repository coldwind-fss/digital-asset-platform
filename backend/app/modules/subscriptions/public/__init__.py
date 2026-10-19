from app.modules.subscriptions.api.routes import router


def refresh_reminders(*args,**kwargs):
    from app.modules.subscriptions.application.service import refresh_due
    return refresh_due(*args,**kwargs)


def resource_subscription_summary(session,resource_id):
    # The resource port has already checked row visibility. Select only basic
    # non-financial columns; member finance filters must not hide plan/seats.
    from sqlalchemy import select
    from app.platform.db.models import SubscriptionLedger,SubscriptionPeriod
    from app.modules.subscriptions.application.service import workspace_today
    table=SubscriptionLedger.__table__;period=SubscriptionPeriod.__table__
    row=session.connection().execute(select(table.c.id,table.c.plan,table.c.seats_total,table.c.seats_assigned,table.c.billing_cycle).where(table.c.resource_id==resource_id)).mappings().first()
    if not row:return None
    today=workspace_today()
    current=session.connection().execute(select(period.c.starts_on,period.c.ends_on).where(period.c.ledger_id==row['id'],period.c.void_reason.is_(None),period.c.starts_on<=today,period.c.ends_on>=today)).mappings().first()
    return {**row,'starts_on':current['starts_on'].isoformat() if current else None,'ends_on':current['ends_on'].isoformat() if current else None}
