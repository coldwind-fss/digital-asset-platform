"""Bounded, scope-filtered projection; no graph-owned facts or hidden counts."""
from collections import deque
from uuid import UUID
from sqlalchemy import select,or_
from app.platform.db.models import Resource,ResourceRelation,ResourceCompany,ResourcePerson,RelationDeclaration
from app.modules.bindings.public import graph_contacts,graph_identity_resources
from app.platform.db.commands import now
from app.platform.http.errors import ApiException


def local_graph(session,kind,identifier,depth=1):
    from app.modules.directory.public import graph_directory_node
    nodes={};edges={};pending=deque([(kind,identifier,0)]);visited=set();truncated=False
    def add_node(k,i):
        nonlocal truncated
        key=f'{k}:{i}'
        if key in nodes:return key
        if len(nodes)>=100:truncated=True;return None
        if k=='resource':
            row=session.get(Resource,i)
            if not row or row.archived_at:return None
            declarations=session.scalars(select(RelationDeclaration).where(RelationDeclaration.resource_id==row.id,RelationDeclaration.ended_at.is_(None)).order_by(RelationDeclaration.id)).all()
            node=dict(id=str(row.id),key=key,kind=k,label=row.name,type_code=row.type_code,verification=row.verification,lifecycle=row.lifecycle,declarations=[{'relation_kind':r.relation_kind,'state':r.state} for r in declarations])
        else:
            node=graph_directory_node(session,k,i)
            if node is None:return None
            node.update(key=key)
        nodes[key]=node;return key
    def edge(source,target,relation,status,identity):
        nonlocal truncated
        if source and target:
            if len(edges)>=200:truncated=True;return
            edges[str(identity)]=dict(id=str(identity),source=source,target=target,relation=relation,confirmation=status)
    if not add_node(kind,identifier):raise ApiException(404,'RESOURCE_NOT_FOUND','地图中心对象不存在或不可见')
    while pending:
        k,i,level=pending.popleft()
        if (k,i) in visited:continue
        visited.add((k,i));center=f'{k}:{i}'
        if level>=depth:continue
        candidates=[]
        if k=='resource':
            resource=session.get(Resource,i)
            if resource.platform_id:candidates.append(('platform',resource.platform_id,'platform','proposed',f'platform:{i}',False))
            stmt=select(ResourceRelation).where(or_(ResourceRelation.source_resource_id==i,ResourceRelation.target_resource_id==i),ResourceRelation.confirmation!='rejected',ResourceRelation.valid_from<=now(),or_(ResourceRelation.valid_to.is_(None),ResourceRelation.valid_to>now()))
            rows=session.scalars(stmt.order_by(ResourceRelation.id).limit(201)).all()
            if len(rows)>200:truncated=True
            for r in rows[:200]:
                incoming=r.target_resource_id==i;candidates.append(('resource',r.source_resource_id if incoming else r.target_resource_id,r.relation_type,r.confirmation,r.id,incoming))
            for model,field,target,relation in [(ResourceCompany,'company_id','company','owner'),(ResourcePerson,'person_id','person','role')]:
                rows=session.scalars(select(model).where(model.resource_id==i,model.confirmation!='rejected',model.valid_from<=now(),or_(model.valid_to.is_(None),model.valid_to>now())).order_by(model.id).limit(101)).all()
                if len(rows)>100:truncated=True
                for row in rows[:100]:
                    candidates.append((target,getattr(row,field),row.role,row.confirmation,row.id,False))
            contacts=graph_contacts(session,i)
            if len(contacts)>100:truncated=True
            candidates.extend(contacts[:100])
        elif k in {'platform','company','person','identity'}:
            if k=='platform':stmt=select(Resource.id).where(Resource.platform_id==i,Resource.archived_at.is_(None))
            elif k!='identity':
                model=ResourceCompany if k=='company' else ResourcePerson;field=model.company_id if k=='company' else model.person_id
                stmt=select(model.resource_id).join(Resource,Resource.id==model.resource_id).where(field==i,Resource.archived_at.is_(None),model.confirmation!='rejected',model.valid_from<=now(),or_(model.valid_to.is_(None),model.valid_to>now())).distinct()
            ids=graph_identity_resources(session,i) if k=='identity' else session.scalars(stmt.order_by(Resource.id if k=='platform' else model.resource_id).limit(101)).all()
            if len(ids)>100:truncated=True
            # Expand the resource through its authoritative outgoing links.
            for rid in ids[:100]:
                if add_node('resource',rid):pending.append(('resource',rid,max(0,level)))
            continue
        for tk,tid,rel,status,eid,incoming in candidates:
            node=add_node(tk,tid)
            edge(node if incoming else center,center if incoming else node,rel,status,eid)
            if node:pending.append((tk,tid,level+1))
    return dict(center=f'{kind}:{identifier}',nodes=list(nodes.values()),edges=list(edges.values()),truncated=truncated,coverage='visible_known_relations')
