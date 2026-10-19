from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.modules.governance.api.schemas import (
    ChangeCaseCreate,
    ChangeCasePage,
    ChangeCasePatch,
    ChangeCaseView,
    ChangeItemCreate,
    ChangeItemPatch,
    ChangeItemPage,
    ChangeItemView,
    ConfirmChangeRequest,
    ExpectedVersionRequest,
    RecordExecutionRequest,
    VersionReasonRequest,
)
from app.modules.governance.application.service import (
    cancel_change_item,
    patch_change_item, confirm_cancellation, return_for_rework,
    close_change_case,
    confirm_change_item,
    create_change_case,
    create_change_item,
    get_change_case,
    get_change_item,
    list_change_cases,
    list_change_items,
    patch_change_case,
    proposal_for_item,
    record_execution,
    start_change_item,
    submit_change_case,
)
from app.modules.identity_access.public import PolicySubject, require_capability
from app.platform.db.session import database_session
from app.platform.http.errors import ApiException
from app.platform.http.pagination import PageSize
from app.platform.http.schemas import ResponseMeta, SuccessEnvelope

router = APIRouter(tags=["governance"])
SessionDependency = Annotated[Session, Depends(database_session)]
ReadSubject = Annotated[PolicySubject, Depends(require_capability("governance.read"))]
WriteSubject = Annotated[PolicySubject, Depends(require_capability("governance.write"))]
ConfirmSubject = Annotated[PolicySubject, Depends(require_capability("governance.confirm"))]
def _actor(subject: PolicySubject) -> UUID:
    if not subject.subject_id:
        raise ApiException(401, "AUTHENTICATION_REQUIRED", "请先登录")
    try:
        return UUID(subject.subject_id)
    except ValueError:
        raise ApiException(401, "AUTHENTICATION_REQUIRED", "当前主体 ID 无效") from None


def _request_id(request: Request) -> UUID:
    return UUID(str(request.state.request_id))


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(request_id=request.state.request_id)


def _case_view(session, case) -> ChangeCaseView:
    from app.modules.governance.application.actions import case_actions
    return ChangeCaseView(
        available_actions=case_actions(session,case),
        id=case.id,
        case_type=case.case_type,
        subject_person_id=case.subject_person_id,
        coordinator_person_id=case.coordinator_person_id,
        reason=case.reason or "",
        status=case.status,
        version=case.version,
        created_at=case.created_at,
        closed_at=case.closed_at,
    )


def _item_view(session: Session, item) -> ChangeItemView:
    from app.modules.governance.application.actions import item_actions
    return ChangeItemView(
        available_actions=item_actions(session,item),
        id=item.id,
        case_id=item.case_id,
        resource_id=item.resource_id,
        action=item.action,
        assignee_person_id=item.assignee_person_id,
        proposal=proposal_for_item(session, item),
        status=item.status,
        version=item.version,
        non_secret_result=item.non_secret_result if isinstance(item.non_secret_result, str) else None,
        executed_by_person_id=item.executed_by_person_id,
        confirmed_by_person_id=item.confirmed_by_person_id,
        executed_at=item.executed_at,
        confirmed_at=item.confirmed_at,
        execution_history=item.execution_history,
    )


@router.get("/change-cases", response_model=SuccessEnvelope[ChangeCasePage])
def list_change_cases_route(
    request: Request,
    subject: ReadSubject,
    session: SessionDependency,
    status: str | None = Query(default=None),
    assigned_to_me: bool | None = None,
    awaiting_my_confirmation: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[ChangeCasePage]:
    rows, total = list_change_cases(
        session,
        subject_id=_actor(subject),
        status=status,
        assigned_to_me=assigned_to_me,
        awaiting_my_confirmation=awaiting_my_confirmation,
        page=page,
        page_size=page_size,
    )
    data = ChangeCasePage(
        items=[_case_view(session, row) for row in rows],
        pagination={"page": page, "page_size": page_size, "total": total, "has_next": page * page_size < total},
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.post("/change-cases", response_model=SuccessEnvelope[ChangeCaseView], status_code=201)
def create_change_case_route(
    request: Request,
    payload: ChangeCaseCreate,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeCaseView]:
    case = create_change_case(session, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_case_view(session, case), error=None, meta=_meta(request))


@router.get("/change-cases/{case_id}", response_model=SuccessEnvelope[ChangeCaseView])
def get_change_case_route(
    request: Request,
    case_id: UUID,
    _subject: ReadSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeCaseView]:
    return SuccessEnvelope(data=_case_view(session, get_change_case(session, case_id)), error=None, meta=_meta(request))


@router.patch("/change-cases/{case_id}", response_model=SuccessEnvelope[ChangeCaseView])
def patch_change_case_route(
    request: Request,
    case_id: UUID,
    payload: ChangeCasePatch,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeCaseView]:
    case = patch_change_case(session, case_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_case_view(session, case), error=None, meta=_meta(request))


@router.get("/change-cases/{case_id}/items", response_model=SuccessEnvelope[ChangeItemPage])
def list_change_items_route(
    request: Request,
    case_id: UUID,
    _subject: ReadSubject,
    session: SessionDependency,
    page: int = Query(default=1, ge=1),
    page_size: PageSize = Query(default=25),
) -> SuccessEnvelope[ChangeItemPage]:
    rows, total = list_change_items(session, case_id, page=page, page_size=page_size)
    data = ChangeItemPage(
        items=[_item_view(session, row) for row in rows],
        pagination={"page": page, "page_size": page_size, "total": total, "has_next": page * page_size < total},
    )
    return SuccessEnvelope(data=data, error=None, meta=_meta(request))


@router.post("/change-cases/{case_id}/items", response_model=SuccessEnvelope[ChangeItemView], status_code=201)
def create_change_item_route(
    request: Request,
    case_id: UUID,
    payload: ChangeItemCreate,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeItemView]:
    item = create_change_item(session, case_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_item_view(session, item), error=None, meta=_meta(request))


@router.post("/change-cases/{case_id}/actions/submit", response_model=SuccessEnvelope[ChangeCaseView])
def submit_change_case_route(
    request: Request,
    case_id: UUID,
    payload: ExpectedVersionRequest,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeCaseView]:
    case = submit_change_case(session, case_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_case_view(session, case), error=None, meta=_meta(request))


@router.post("/change-items/{item_id}/actions/start", response_model=SuccessEnvelope[ChangeItemView])
def start_change_item_route(
    request: Request,
    item_id: UUID,
    payload: ExpectedVersionRequest,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeItemView]:
    item = start_change_item(session, item_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_item_view(session, item), error=None, meta=_meta(request))


@router.post("/change-items/{item_id}/actions/record-execution", response_model=SuccessEnvelope[ChangeItemView])
def record_execution_route(
    request: Request,
    item_id: UUID,
    payload: RecordExecutionRequest,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeItemView]:
    item = record_execution(session, item_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_item_view(session, item), error=None, meta=_meta(request))


@router.post("/change-items/{item_id}/actions/confirm", response_model=SuccessEnvelope[ChangeItemView])
def confirm_change_item_route(
    request: Request,
    item_id: UUID,
    payload: ConfirmChangeRequest,
    subject: ConfirmSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeItemView]:
    item = confirm_change_item(session, item_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_item_view(session, item), error=None, meta=_meta(request))


@router.post("/change-items/{item_id}/actions/request-cancellation", response_model=SuccessEnvelope[ChangeItemView])
def cancel_change_item_route(
    request: Request,
    item_id: UUID,
    payload: VersionReasonRequest,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeItemView]:
    item = cancel_change_item(session, item_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_item_view(session, item), error=None, meta=_meta(request))


@router.post("/change-cases/{case_id}/actions/close", response_model=SuccessEnvelope[ChangeCaseView])
def close_change_case_route(
    request: Request,
    case_id: UUID,
    payload: ExpectedVersionRequest,
    subject: WriteSubject,
    session: SessionDependency,
) -> SuccessEnvelope[ChangeCaseView]:
    case = close_change_case(session, case_id, payload, actor_id=_actor(subject), request_id=_request_id(request))
    return SuccessEnvelope(data=_case_view(session, case), error=None, meta=_meta(request))


@router.patch("/change-items/{item_id}",response_model=SuccessEnvelope[ChangeItemView])
def patch_item_route(item_id:UUID,payload:ChangeItemPatch,request:Request,subject:WriteSubject,session:SessionDependency):
    return SuccessEnvelope(data=_item_view(session,patch_change_item(session,item_id,payload,actor_id=_actor(subject),request_id=_request_id(request))),error=None,meta=_meta(request))


@router.get('/change-items/{item_id}',response_model=SuccessEnvelope[ChangeItemView],operation_id='getChangeItem')
def get_item_route(item_id:UUID,request:Request,_:ReadSubject,session:SessionDependency):
    return SuccessEnvelope(data=_item_view(session,get_change_item(session,item_id)),error=None,meta=_meta(request))

@router.post("/change-items/{item_id}/actions/confirm-cancellation",response_model=SuccessEnvelope[ChangeItemView])
def confirm_cancel_route(item_id:UUID,payload:VersionReasonRequest,request:Request,subject:ConfirmSubject,session:SessionDependency):
    return SuccessEnvelope(data=_item_view(session,confirm_cancellation(session,item_id,payload,actor_id=_actor(subject),request_id=_request_id(request))),error=None,meta=_meta(request))

@router.post("/change-items/{item_id}/actions/return-for-rework",response_model=SuccessEnvelope[ChangeItemView])
def return_route(item_id:UUID,payload:VersionReasonRequest,request:Request,subject:ConfirmSubject,session:SessionDependency):
    return SuccessEnvelope(data=_item_view(session,return_for_rework(session,item_id,payload,actor_id=_actor(subject),request_id=_request_id(request))),error=None,meta=_meta(request))
