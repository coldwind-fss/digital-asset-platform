from sqlalchemy import select
from app.platform.db.models import Resource,ResourcePerson,ResourceCompany,ResourceRelation,RelationDeclaration,ProvenanceEntry,Person,Company,AccountBinding
from app.platform.db.commands import now,write_resource,record_event
from app.platform.http.errors import ApiException


def _finish(session,resource,actor,request_id,event,source):
    resource.version+=1;resource.updated_at=now()
    record_event(session,event,actor,request_id,resource.id,{"version":resource.version,"source":source})
    session.add(ProvenanceEntry(resource_id=resource.id,source_kind=event,label=source,created_by_person_id=actor))
    session.commit();return resource


def supersede_declaration(session,resource_id,kind,reason):
    rows=session.scalars(select(RelationDeclaration).where(RelationDeclaration.resource_id==resource_id,RelationDeclaration.relation_kind==kind,RelationDeclaration.ended_at.is_(None))).all()
    for row in rows:
        if row.state!="unknown" and not reason:
            raise ApiException(409,"DECLARATION_CONFLICT","已有明确的关系声明，补充事实需要说明原因")
        row.ended_at=now()


def initial_facts(session,resource_id,payload,actor,request_id):
    resource=write_resource(session,resource_id,payload.expected_version)
    if not payload.people and not payload.company_links:raise ApiException(422,"VALIDATION_FAILED","至少补录一项事实")
    for model,items,key,target_model,kind in ((ResourcePerson,payload.people,"person_id",Person,"owner"),(ResourceCompany,payload.company_links,"company_id",Company,"company")):
        seen=set()
        for item in items:
            target_id=getattr(item,key)
            if (target_id,item.role) in seen:raise ApiException(409,"DUPLICATE_RELATION","同一关系不能重复补录")
            seen.add((target_id,item.role))
            target=session.get(target_model,target_id)
            if not target or target.status!="active":raise ApiException(404,"REFERENCE_NOT_FOUND","关联对象不存在、不可见或未启用")
            if item.role=="owner" and session.scalar(select(model.id).where(model.resource_id==resource_id,model.role=="owner",model.confirmation=="confirmed",model.valid_to.is_(None))):
                raise ApiException(409,"GOVERNANCE_REQUIRED","已有确认归属或负责人，变更必须通过治理")
            existing=session.scalar(select(model).where(model.resource_id==resource_id,getattr(model,key)==target_id,model.role==item.role,model.valid_to.is_(None)))
            if existing and existing.confirmation=="confirmed":raise ApiException(409,"DUPLICATE_RELATION","事实已存在")
            if existing:
                existing.confirmation="confirmed";existing.version+=1
            else:session.add(model(resource_id=resource_id,**{key:target_id},role=item.role,confirmation="confirmed"))
            if item.role=="owner":supersede_declaration(session,resource_id,kind,payload.source_note)
            session.flush()
    return _finish(session,resource,actor,request_id,"facts.initialized",payload.source_note)


def declare_relation(session,resource_id,payload,actor,request_id):
    resource=write_resource(session,resource_id,payload.expected_version)
    kind=payload.relation_kind
    if kind=="platform":exists=resource.platform_id is not None
    elif kind in {"company","owner"}:
        model=ResourceCompany if kind=="company" else ResourcePerson
        exists=session.scalar(select(model.id).where(model.resource_id==resource_id,model.role=="owner",model.confirmation!="rejected",model.valid_to.is_(None))) is not None
    elif kind in {"registration","login","recovery","mfa"}:
        exists=session.scalar(select(AccountBinding.id).where(AccountBinding.account_resource_id==resource_id,AccountBinding.purpose==kind,AccountBinding.confirmation!="rejected",AccountBinding.valid_to.is_(None))) is not None
    else:
        exists=session.scalar(select(ResourceRelation.id).where(ResourceRelation.source_resource_id==resource_id,ResourceRelation.relation_type==kind,ResourceRelation.confirmation!="rejected",ResourceRelation.valid_to.is_(None))) is not None
    if exists:raise ApiException(409,"RELATION_EXISTS","已有关系事实，不能同时声明不存在或未知")
    supersede_declaration(session,resource_id,kind,payload.reason)
    row=RelationDeclaration(resource_id=resource_id,relation_kind=kind,state=payload.state,reason=payload.reason,source=payload.source,created_by_person_id=actor)
    session.add(row);_finish(session,resource,actor,request_id,"relation.declared",payload.source)
    return row


def verify_fact(session,resource_id,payload,actor,request_id,initial_lifecycle=False):
    resource=write_resource(session,resource_id,payload.expected_version)
    if initial_lifecycle:
        if resource.lifecycle!="unknown" or payload.lifecycle!="in_use":raise ApiException(409,"GOVERNANCE_REQUIRED","已有使用状态的改变必须通过治理")
        resource.lifecycle="in_use"
    else:resource.verification="verified"
    return _finish(session,resource,actor,request_id,"resource.verified" if not initial_lifecycle else "resource.initial_lifecycle",payload.reason)


def archive_fact(session,resource_id,payload,actor,request_id,archiving):
    resource=session.scalar(select(Resource).where(Resource.id==resource_id).with_for_update())
    if resource is None:raise ApiException(404,"RESOURCE_NOT_FOUND","资源不存在或不可见")
    principal=session.info.get("local_principal")
    if principal and principal.role!="admin" and resource_id not in session.info["writable_resource_ids"]:raise ApiException(403,"PERMISSION_DENIED","无维护权限")
    if resource.version!=payload.expected_version:raise ApiException(409,"STATE_CONFLICT","资源已更新")
    if archiving and resource.lifecycle not in {"disabled","retired"}:raise ApiException(409,"GOVERNANCE_REQUIRED","先确认实际停用或退役，再归档")
    resource.archived_at=now() if archiving else None
    return _finish(session,resource,actor,request_id,"resource.archived" if archiving else "resource.unarchived",payload.reason)
