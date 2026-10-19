from datetime import date,datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import Field,model_validator
from app.platform.http.schemas import StrictModel

Currency=Literal["CNY","USD","EUR","GBP","HKD","JPY","SGD","AUD","CAD","CHF"]


class LedgerFields(StrictModel):
    plan:str|None=Field(default=None,max_length=200)
    seats_total:int|None=Field(default=None,ge=0,le=1000000)
    seats_assigned:int|None=Field(default=None,ge=0,le=1000000)
    billing_cycle:Literal["month","year","custom"]="month"
    reminder_days:list[int]=Field(default_factory=lambda:[30,7,1],max_length=10)

    @model_validator(mode="after")
    def validate_fields(self):
        if len(set(self.reminder_days))!=len(self.reminder_days) or any(not 0<=d<=365 for d in self.reminder_days):raise ValueError("提醒窗口必须是不重复的0—365天")
        if self.seats_assigned is not None and self.seats_total is not None and self.seats_assigned>self.seats_total:raise ValueError("分配席位不能超过总席位")
        return self


class LedgerCreate(LedgerFields):
    resource_id:UUID


class LedgerPatch(LedgerFields):
    expected_version:int=Field(ge=1)
    reason:str=Field(min_length=1,max_length=1000)


class PeriodCreate(StrictModel):
    expected_version:int=Field(ge=1)
    starts_on:date
    ends_on:date
    planned_amount:Decimal|None=Field(default=None,ge=0,decimal_places=2,max_digits=18)
    currency:Currency
    source:str=Field(min_length=1,max_length=500)

    @model_validator(mode="after")
    def dates(self):
        if self.ends_on<self.starts_on:raise ValueError("周期结束不能早于开始")
        return self


class ExpenseCreate(StrictModel):
    expected_version:int=Field(ge=1)
    amount:Decimal=Field(ge=0,decimal_places=2,max_digits=18)
    currency:Currency
    kind:Literal["actual","budget"]
    recorded_on:date
    period_id:UUID|None=None
    corrects_entry_id:UUID|None=None
    source:str=Field(min_length=1,max_length=500)


class VersionReason(StrictModel):
    expected_version:int=Field(ge=1)
    reason:str=Field(min_length=1,max_length=1000)


class PeriodView(StrictModel):
    id:UUID
    resource_id:UUID
    starts_on:date
    ends_on:date
    planned_amount:Decimal|None
    currency:str
    source:str
    void_reason:str|None
    version:int


class ExpenseView(StrictModel):
    id:UUID
    resource_id:UUID
    period_id:UUID|None
    corrects_entry_id:UUID|None
    amount:Decimal
    currency:str
    kind:str
    recorded_on:date
    source:str
    void_reason:str|None
    version:int


class LedgerView(LedgerFields):
    id:UUID
    resource_id:UUID
    version:int
    current_period:PeriodView|None=None
    active_users:int


class LedgerPage(StrictModel):
    items:list[LedgerView]
    pagination:dict[str,int|bool]


class PeriodPage(StrictModel):
    items:list[PeriodView]
    pagination:dict[str,int|bool]


class ExpensePage(StrictModel):
    items:list[ExpenseView]
    pagination:dict[str,int|bool]


class ReminderView(StrictModel):
    resource_name:str
    id:UUID
    resource_id:UUID
    due_on:date
    window_days:int
    status:str
    read:bool


class ReminderPage(StrictModel):
    unread_total:int
    items:list[ReminderView]
    pagination:dict[str,int|bool]


class MoneySummary(StrictModel):
    currency:str
    kind:str
    period:str
    amount:Decimal


class SummaryView(StrictModel):
    items:list[MoneySummary]


class ReminderResult(StrictModel):
    processed:int
