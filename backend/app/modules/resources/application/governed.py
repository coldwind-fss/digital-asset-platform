"""Resource-owned commands used only by the governance application port."""
from uuid import UUID
from sqlalchemy import select
from app.platform.db.models import ResourcePerson,ResourceCompany,ResourceRelation,Resource,Company,Department,Person
from app.platform.db.commands import write_resource,now
from app.platform.http.errors import ApiException
from app.modules.resources.application.service import apply_owner_transfer,create_resource_relation
from app.modules.resources.api.schemas import ResourceRelationCreateRequest


def snapshot(session,resource_id):
    resource=write_resource(session,resource_id)
    facts={'lifecycle':resource.lifecycle,'department':str(resource.owning_department_id),'archived':str(resource.archived_at)}
    for model,column,name in [(ResourcePerson,ResourcePerson.resource_id,'people'),(ResourceCompany,ResourceCompany.resource_id,'companies'),(ResourceRelation,ResourceRelation.source_resource_id,'relations')]:
        facts[name]=sorted((str(r.id),r.version) for r in session.scalars(select(model).where(column==resource_id,model.valid_to.is_(None))))
    # JSON round trip shape is deliberate: persisted snapshots use lists, not tuples.
    return {k:[list(x) for x in v] if isinstance(v,list) else v for k,v in facts.items()}


def validate(session,resource_id,proposal):
    resource=write_resource(session,resource_id)
    action=proposal.action
    if action in {'change_owner','transfer_controller','grant_use'}:
        person=session.get(Person,getattr(proposal,'to_person_id',None) or getattr(proposal,'person_id',None))
        if not person or person.status!='active':raise ApiException(422,'VALIDATION_FAILED','目标人员不存在或未启用')
    if action in {'remove_use','transfer_controller'}:
        assignment=session.get(ResourcePerson,proposal.assignment_id)
        if not assignment or assignment.resource_id!=resource_id or assignment.valid_to or assignment.role!=('use' if action=='remove_use' else 'controller'):raise ApiException(409,'STATE_CONFLICT','当前人员关系已变化')
    if action=='change_owner':
        owner=session.scalar(select(ResourcePerson).where(ResourcePerson.resource_id==resource_id,ResourcePerson.role=='owner',ResourcePerson.confirmation=='confirmed',ResourcePerson.valid_to.is_(None)))
        if proposal.assignment_id and (not owner or owner.id!=proposal.assignment_id):raise ApiException(409,'STATE_CONFLICT','负责人事实已变化')
        if owner and owner.person_id==proposal.to_person_id:raise ApiException(422,'VALIDATION_FAILED','目标已经是负责人')
    if action=='grant_use' and session.scalar(select(ResourcePerson.id).where(ResourcePerson.resource_id==resource_id,ResourcePerson.person_id==proposal.person_id,ResourcePerson.role=='use',ResourcePerson.valid_to.is_(None))):raise ApiException(409,'STATE_CONFLICT','使用关系已存在')
    if action=='change_organization':
        for model,value in [(Company,proposal.company_id),(Department,proposal.owning_department_id)]:
            if value and not session.get(model,value):raise ApiException(404,'REFERENCE_NOT_FOUND','归属对象不存在或不可见')
    if action=='change_management_relation':
        relation=session.get(ResourceRelation,proposal.relation_id)
        if not relation or relation.source_resource_id!=resource_id or relation.valid_to:raise ApiException(409,'STATE_CONFLICT','管理关系已变化')
        if not session.get(Resource,proposal.proposed_target_id):raise ApiException(404,'REFERENCE_NOT_FOUND','关联对象不存在或不可见')
    if action=='replace_key':
        replacement=write_resource(session,proposal.replacement_resource_id)
        if resource.type_code!='api_key' or replacement.type_code!='api_key' or replacement.id==resource.id or replacement.lifecycle in {'disabled','retired'}:raise ApiException(422,'VALIDATION_FAILED','替换必须是另一个可用的 API Key 资源')
    if action in {'disable_resource','retire_resource','reactivate_resource'}:
        allowed={'disable_resource':{'unknown','in_use'},'retire_resource':{'disabled'},'reactivate_resource':{'disabled'}}
        if resource.lifecycle not in allowed[action]:raise ApiException(409,'STATE_CONFLICT','当前生命周期不允许此操作')
    return resource


def apply(session,resource_id,proposal,expected_version):
    resource=write_resource(session,resource_id,expected_version)
    validate(session,resource_id,proposal)
    action=proposal.action
    if action=='change_owner':
        owner=session.scalar(select(ResourcePerson).where(ResourcePerson.resource_id==resource_id,ResourcePerson.role=='owner',ResourcePerson.confirmation=='confirmed',ResourcePerson.valid_to.is_(None)))
        return apply_owner_transfer(session,resource_id,expected_resource_version=expected_version,expected_assignment_id=owner.id if owner else None,to_person_id=proposal.to_person_id)[0]
    if action in {'remove_use','transfer_controller'}:
        previous=session.get(ResourcePerson,proposal.assignment_id);previous.valid_to=now();previous.version+=1
        if action=='transfer_controller':session.add(ResourcePerson(resource_id=resource_id,person_id=proposal.to_person_id,role='controller',confirmation='confirmed'))
    elif action=='grant_use':session.add(ResourcePerson(resource_id=resource_id,person_id=proposal.person_id,role='use',confirmation='confirmed'))
    elif action=='change_organization':
        for link in session.scalars(select(ResourceCompany).where(ResourceCompany.resource_id==resource_id,ResourceCompany.role=='owner',ResourceCompany.valid_to.is_(None))):link.valid_to=now();link.version+=1
        session.flush()
        if proposal.company_id:session.add(ResourceCompany(resource_id=resource_id,company_id=proposal.company_id,role='owner',confirmation='confirmed'))
        resource.owning_department_id=proposal.owning_department_id
    elif action=='change_visibility':resource.visibility_scope=proposal.visibility_scope
    elif action=='change_management_relation':
        old=session.get(ResourceRelation,proposal.relation_id);old.valid_to=now();old.version+=1;session.flush()
        new=create_resource_relation(session,resource_id,ResourceRelationCreateRequest(expected_version=resource.version,target_id=proposal.proposed_target_id,relation_type=old.relation_type,note='治理确认替换'))
        new.confirmation='confirmed'
        return resource
    elif action in {'disable_resource','retire_resource','reactivate_resource','replace_key'}:
        resource.lifecycle={'disable_resource':'disabled','retire_resource':'retired','reactivate_resource':'in_use','replace_key':'disabled'}[action]
        if action=='replace_key':session.add(ResourceRelation(source_resource_id=resource_id,target_resource_id=proposal.replacement_resource_id,relation_type='depends_on',confirmation='confirmed',note='替代 Key 资源；不表示外部平台已自动更换'))
        if resource.lifecycle in {'disabled','retired'}:
            for assignment in session.scalars(select(ResourcePerson).where(ResourcePerson.resource_id==resource_id,ResourcePerson.role=='use',ResourcePerson.valid_to.is_(None))):assignment.valid_to=now();assignment.version+=1
    resource.version+=1;resource.updated_at=now();session.flush();return resource
