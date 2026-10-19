"""Presentation hints derived from the same scope, actor and state rules as commands.

Commands still recheck version, facts and evidence transactionally.
"""
from sqlalchemy import select
from app.platform.db.models import ChangeCase, ChangeItem

def writable(session,case,resource_id=None):
    principal=session.info.get('local_principal')
    if principal is None:return True
    if 'governance.write' not in principal.capabilities:return False
    if principal.role!='admin' and case.id not in session.info.get('writable_case_ids',set()):return False
    return resource_id is None or principal.role=='admin' or resource_id in session.info.get('writable_resource_ids',set())

def case_actions(session,case):
    if not writable(session,case):return []
    items=session.scalars(select(ChangeItem).where(ChangeItem.case_id==case.id)).all()
    if case.status=='draft':return ['edit','add-item']+(['submit'] if items else [])
    if case.status=='active' and items and all(i.status in {'completed','cancelled'} for i in items):return ['close']
    return []

def item_actions(session,item):
    case=session.get(ChangeCase,item.case_id)
    if not case or not writable(session,case,item.resource_id):return []
    principal=session.info.get('local_principal')
    actor=principal.person_id if principal else None
    executor=not item.assignee_person_id or item.assignee_person_id==actor or principal is None
    reviewer=principal is None or ('governance.confirm' in principal.capabilities and actor!=item.executed_by_person_id)
    actions=[]
    if case.status=='draft' and item.status=='pending':actions.append('edit')
    if case.status=='active':
        if item.status in {'pending','failed'} and executor:actions.append('start')
        if item.status=='in_progress' and executor:actions.append('record-execution')
        if item.status=='awaiting_confirmation' and reviewer:actions+=['confirm','return-for-rework']
        if item.status=='cancellation_requested' and reviewer and actor!=item.cancellation_requested_by:actions.append('confirm-cancellation')
    if case.status in {'draft','active'} and item.status not in {'completed','cancelled','cancellation_requested'}:actions.append('request-cancellation')
    return actions
