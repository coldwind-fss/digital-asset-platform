from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import Field
from app.platform.http.schemas import StrictModel


class ConnectionCreate(StrictModel):
    resource_id:UUID
    credential_id:UUID
    provider:Literal['deepseek']='deepseek'
    label:str=Field(min_length=1,max_length=200)
    scheduled:bool=False
    interval_seconds:int=Field(default=21600,ge=3600,le=604800)


class ConnectionPatch(StrictModel):
    expected_version:int=Field(ge=1)
    credential_id:UUID|None=None
    status:Literal['active','inactive']|None=None
    scheduled:bool|None=None
    interval_seconds:int|None=Field(default=None,ge=3600,le=604800)


class ConnectionView(StrictModel):
    id:UUID
    resource_id:UUID
    provider:str
    label:str
    credential_id:UUID
    credential_version:int
    status:str
    scheduled:bool
    interval_seconds:int
    last_attempt_at:datetime|None
    last_success_at:datetime|None
    last_error_code:str|None
    version:int
    stale:bool


class JobView(StrictModel):
    id:UUID
    resource_id:UUID
    connection_id:UUID
    status:str
    attempts:int
    available_at:datetime
    lease_until:datetime|None
    last_error_code:str|None
    finished_at:datetime|None


class SnapshotView(StrictModel):
    id:UUID
    resource_id:UUID
    connection_id:UUID
    currency:str
    total_balance:Decimal
    granted_balance:Decimal
    topped_up_balance:Decimal
    is_available:bool
    collected_at:datetime
    meaning:Literal['account_balance']='account_balance'


class ConnectionPage(StrictModel):
    items:list[ConnectionView]
    pagination:dict[str,int|bool]


class JobPage(StrictModel):
    items:list[JobView]
    pagination:dict[str,int|bool]


class SnapshotPage(StrictModel):
    items:list[SnapshotView]
    pagination:dict[str,int|bool]


class ProviderCapability(StrictModel):
    provider:Literal['deepseek']='deepseek'
    metric:Literal['account_balance']='account_balance'
    endpoint:Literal['https://api.deepseek.com/user/balance']='https://api.deepseek.com/user/balance'
    unit:Literal['money']='money'
    currencies:list[str]=['CNY','USD']
    official_documentation:str='https://api-docs.deepseek.com/api/get-user-balance/'
    checked_on:str='2026-10-17'
    per_key_usage:Literal[False]=False


class ProviderPage(StrictModel):
    items:list[ProviderCapability]


class WorkerStatus(StrictModel):
    counts:dict[str,int]
    recent_heartbeat:bool
    last_seen_at:datetime|None
