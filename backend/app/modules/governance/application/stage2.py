"""Typed proposals, immutable execution history and independent confirmation."""
from uuid import UUID
from pydantic import TypeAdapter
from sqlalchemy import select,text
from app.modules.governance.api.schemas import ChangeItemProposal,ChangeOwnerProposal
from app.modules.resources.public import governed_snapshot,validate_governed_change,apply_governed_change,current_owner_assignment,refresh_mailbox_identifier
from app.modules.bindings.public import binding_snapshot,apply_binding_change
from app.modules.credentials.public import apply_credential_operation,credential_operation_snapshot
from app.modules.materials.public import execution_evidence
from app.modules.integrations.public import stop_resource_connections
from app.modules.subscriptions.public import refresh_reminders
from app.platform.db.models import ChangeCase,ChangeItem
from app.platform.db.commands import now,write_resource,record_event
from app.platform.http.errors import ApiException


def locked(session,model,identifier):
    row=session.scalar(select(model).where(model.id==identifier).with_for_update().execution_options(populate_existing=True))
    if not row:raise ApiException(404,'RESOURCE_NOT_FOUND','事项不存在或不可见')
    return row


def item_and_case(session,item_id):
    session.execute(text('SELECT pg_advisory_xact_lock(731004211)'))
    # All case/item commands use case -> resource -> item ordering.
    item=session.get(ChangeItem,item_id)
    if not item:raise ApiException(404,'RESOURCE_NOT_FOUND','事项不存在或不可见')
    case=locked(session,ChangeCase,item.case_id)
    write_resource(session,item.resource_id)
    return locked(session,ChangeItem,item_id),case


def proposal_for_item(session,item):
    if item.proposal_json:return TypeAdapter(ChangeItemProposal).validate_python(item.proposal_json['proposal'])
    if item.action=='change_owner' and item.to_person_id:return ChangeOwnerProposal(action='change_owner',assignment_id=item.resource_person_id,to_person_id=item.to_person_id)
    raise ApiException(409,'STATE_CONFLICT','历史事项需要重新建立类型化提案')


def snapshot(session,resource_id,proposal):
    validate_governed_change(session,resource_id,proposal)
    data=governed_snapshot(session,resource_id)
    if proposal.action in {'change_binding','change_mailbox_address'}:data.update(binding_snapshot(session,resource_id,proposal))
    if proposal.action in {'rotate_credential','revoke_credential','revoke_credential_grant'}:
        expected={'rotate_credential':'replace','revoke_credential':'revoke','revoke_credential_grant':'revoke_grant'}[proposal.action]
        data.update(credential_operation_snapshot(session,proposal.operation_id,resource_id,expected,getattr(proposal,'credential_id',None),getattr(proposal,'credential_grant_id',None)))
    return data


def create_change_item(session,case_id,payload,*,actor_id,request_id):
    session.execute(text('SELECT pg_advisory_xact_lock(731004211)'))
    case=locked(session,ChangeCase,case_id)
    if case.status!='draft':raise ApiException(409,'STATE_CONFLICT','只有草稿可以添加事项')
    resource=write_resource(session,payload.resource_id)
    from app.modules.governance.application.service import _person
    if payload.assignee_person_id:_person(session,payload.assignee_person_id,active=True)
    facts=snapshot(session,resource.id,payload.proposal)
    owner=current_owner_assignment(session,resource.id) if payload.proposal.action=='change_owner' else None
    item=ChangeItem(case_id=case.id,resource_id=resource.id,action=payload.proposal.action,assignee_person_id=payload.assignee_person_id,expected_resource_version=resource.version,resource_person_id=owner.id if owner else None,from_person_id=owner.person_id if owner else None,to_person_id=getattr(payload.proposal,'to_person_id',None),proposal_json={'proposal':payload.proposal.model_dump(mode='json'),'facts':facts},status='pending')
    session.add(item);case.version+=1;case.updated_at=now();session.flush()
    item.new_contact_identity_id=getattr(payload.proposal,'new_contact_identity_id',None)
    if payload.proposal.action=='grant_use':item.to_person_id=payload.proposal.person_id
    record_event(session,'governance.item_created',actor_id,request_id,resource.id,{'item_id':str(item.id),'action':item.action})
    session.commit();return item


def patch_change_item(session,item_id,payload,*,actor_id,request_id):
    item,case=item_and_case(session,item_id)
    if case.status!='draft' or item.status!='pending' or item.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','只有未提交的事项可以修订')
    if 'assignee_person_id' in payload.model_fields_set:
        from app.modules.governance.application.service import _person
        if payload.assignee_person_id:_person(session,payload.assignee_person_id,active=True)
        item.assignee_person_id=payload.assignee_person_id
    if payload.proposal:
        item.proposal_json={'proposal':payload.proposal.model_dump(mode='json'),'facts':snapshot(session,item.resource_id,payload.proposal)};item.action=payload.proposal.action
        item.expected_resource_version=write_resource(session,item.resource_id).version
        item.to_person_id=getattr(payload.proposal,'to_person_id',None) or getattr(payload.proposal,'person_id',None)
        item.new_contact_identity_id=getattr(payload.proposal,'new_contact_identity_id',None)
    item.version+=1;case.version+=1;case.updated_at=item.updated_at=now()
    record_event(session,'governance.item_updated',actor_id,request_id,item.resource_id,{'item_id':str(item.id)})
    session.commit();return item


def execution_actor(item,actor_id):
    if item.assignee_person_id and item.assignee_person_id!=actor_id:raise ApiException(403,'PERMISSION_DENIED','仅指定执行人可以记录执行')


def start_change_item(session,item_id,payload,*,actor_id,request_id):
    item,case=item_and_case(session,item_id);execution_actor(item,actor_id)
    if case.status!='active' or item.status not in {'pending','failed'} or item.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','事项状态或版本已变化')
    if item.proposal_json and snapshot(session,item.resource_id,proposal_for_item(session,item))!=item.proposal_json['facts']:raise ApiException(409,'STATE_CONFLICT','权威事实已变化，请重新建立事项')
    item.status='in_progress';item.version+=1;item.updated_at=now()
    record_event(session,'governance.item_started',actor_id,request_id,item.resource_id,{'item_id':str(item.id)})
    session.commit();return item


def record_execution(session,item_id,payload,*,actor_id,request_id):
    item,case=item_and_case(session,item_id);execution_actor(item,actor_id)
    if case.status!='active' or item.status!='in_progress' or item.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','事项状态或版本已变化')
    evidence=execution_evidence(session,item.resource_id,payload.evidence_ids)
    facts=snapshot(session,item.resource_id,proposal_for_item(session,item))
    if item.proposal_json and facts!=item.proposal_json['facts']:raise ApiException(409,'STATE_CONFLICT','权威事实已变化，不能重置提案基线')
    item.expected_resource_version=write_resource(session,item.resource_id).version
    item.execution_history=[*item.execution_history,{'actor_id':str(actor_id),'at':now().isoformat(),'outcome':payload.outcome,'evidence_ids':list(map(str,payload.evidence_ids)),'evidence_versions':evidence,'non_secret_result':payload.non_secret_result}]
    item.status='awaiting_confirmation' if payload.outcome=='succeeded' else 'failed'
    item.executed_by_person_id=actor_id;item.executed_at=now();item.evidence_material_id=UUID(evidence[0]['id']);item.non_secret_result=payload.non_secret_result;item.version+=1;item.updated_at=now()
    record_event(session,'governance.execution_recorded',actor_id,request_id,item.resource_id,{'item_id':str(item.id),'outcome':payload.outcome,'evidence_count':len(evidence)})
    session.commit();return item


def confirm_change_item(session,item_id,payload,*,actor_id,request_id):
    item,case=item_and_case(session,item_id)
    if case.status!='active' or item.status!='awaiting_confirmation' or item.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','事项状态或版本已变化')
    if item.executed_by_person_id==actor_id:raise ApiException(403,'PERMISSION_DENIED','执行人与确认人必须分离')
    execution=next((r for r in reversed(item.execution_history) if r.get('outcome')=='succeeded'),None)
    if execution:
        current=execution_evidence(session,item.resource_id,[UUID(x) for x in execution['evidence_ids']])
        if current!=execution.get('evidence_versions'):raise ApiException(409,'EVIDENCE_CHANGED','执行证据已修改，请退回重新核实')
    proposal=proposal_for_item(session,item)
    if item.proposal_json and snapshot(session,item.resource_id,proposal)!=item.proposal_json['facts']:raise ApiException(409,'STATE_CONFLICT','权威事实已变化')
    resource=write_resource(session,item.resource_id,item.expected_resource_version)
    if proposal.action in {'rotate_credential','revoke_credential','revoke_credential_grant'}:
        apply_credential_operation(session,session.info['settings'],proposal.operation_id,resource.id,actor_id,request_id);resource.version+=1
    elif proposal.action in {'change_binding','change_mailbox_address'}:
        apply_binding_change(session,resource.id,proposal);resource.version+=1
        if proposal.action=='change_mailbox_address':refresh_mailbox_identifier(session,resource.id,proposal.new_contact_identity_id)
    else:apply_governed_change(session,resource.id,proposal,item.expected_resource_version)
    if resource.lifecycle in {'disabled','retired'}:
        stop_resource_connections(session,resource.id);refresh_reminders(session,now())
    item.status='completed';item.confirmed_by_person_id=actor_id;item.confirmed_at=now();item.version+=1;item.updated_at=now();case.version+=1;case.updated_at=now()
    record_event(session,'governance.item_confirmed',actor_id,request_id,item.resource_id,{'item_id':str(item.id),'action':proposal.action,'confirmation_note':payload.confirmation_note})
    session.commit();return item


def cancel_change_item(session,item_id,payload,*,actor_id,request_id):
    item,case=item_and_case(session,item_id)
    if case.status not in {'draft','active'} or item.status in {'completed','cancelled','cancellation_requested'} or item.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','事项不能取消或版本已变化')
    item.status='cancellation_requested' if item.executed_at else 'cancelled';item.cancellation_requested_by=actor_id
    item.execution_history=[*item.execution_history,{'action':'request_cancellation','reason':payload.reason,'actor_id':str(actor_id),'at':now().isoformat()}]
    item.version+=1;case.version+=1;item.updated_at=case.updated_at=now()
    record_event(session,'governance.cancellation_requested',actor_id,request_id,item.resource_id,{'item_id':str(item.id),'reason':payload.reason})
    session.commit();return item


def confirm_cancellation(session,item_id,payload,*,actor_id,request_id):
    item,case=item_and_case(session,item_id)
    if item.status!='cancellation_requested' or item.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','取消申请已变化')
    if actor_id in {item.cancellation_requested_by,item.executed_by_person_id}:raise ApiException(403,'PERMISSION_DENIED','需要独立确认取消及外部恢复情况')
    item.status='cancelled';item.version+=1;case.version+=1;item.updated_at=case.updated_at=now()
    record_event(session,'governance.cancellation_confirmed',actor_id,request_id,item.resource_id,{'item_id':str(item.id),'reason':payload.reason})
    session.commit();return item


def return_for_rework(session,item_id,payload,*,actor_id,request_id):
    item,case=item_and_case(session,item_id)
    if item.status!='awaiting_confirmation' or item.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','事项状态已变化')
    if item.executed_by_person_id==actor_id:raise ApiException(403,'PERMISSION_DENIED','需要独立复核人')
    item.status='failed';item.version+=1;item.updated_at=now()
    item.execution_history=[*item.execution_history,{'action':'returned','reason':payload.reason,'actor_id':str(actor_id),'at':now().isoformat()}]
    record_event(session,'governance.returned',actor_id,request_id,item.resource_id,{'item_id':str(item.id),'reason':payload.reason})
    session.commit();return item
