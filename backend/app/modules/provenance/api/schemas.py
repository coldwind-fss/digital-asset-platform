from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import Field
from app.platform.http.schemas import StrictModel

class PreviewInput(StrictModel):
    type_code:Literal['platform_account','mailbox_account','api_key','service_subscription','business_space','application','api_service','cloud_resource','domain']
    label:str=Field(min_length=1,max_length=200)
    csv_content:str=Field(min_length=1,max_length=5*1024*1024,repr=False)
    mapping:dict[str,str]=Field(default_factory=dict,max_length=30)

class CommitInput(StrictModel):
    expected_version:int=Field(ge=1)
    skip_rows:list[int]=Field(default_factory=list,max_length=1000)

class ImportRow(StrictModel):
    row_number:int
    status:Literal['ready','duplicate_candidate','error','skipped','created']
    message:str|None=None
    candidate_ids:list[UUID]=Field(default_factory=list)
    resource_id:UUID|None=None

class BatchView(StrictModel):
    id:UUID
    type_code:str
    label:str
    mapping:dict[str,str]
    status:Literal['preview','committed','expired']
    version:int
    created_at:datetime
    expires_at:datetime
    committed_at:datetime|None
    results:list[ImportRow]

class BatchPage(StrictModel):
    items:list[BatchView]
    pagination:dict[str,int|bool]
