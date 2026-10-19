from sqlalchemy import select
from app.platform.db.models import Company,Platform
from app.platform.db.commands import now,record_event
from app.platform.http.errors import ApiException
from app.modules.resources.public import directory_reference_in_use
from app.modules.bindings.public import company_identity_in_use


def update_catalog(session,kind,object_id,payload,actor_id,request_id):
    model=Company if kind=='company' else Platform
    row=session.scalar(select(model).where(model.id==object_id).with_for_update())
    if not row:raise ApiException(404,'RESOURCE_NOT_FOUND','目录对象不存在或不可见')
    principal=session.info.get('local_principal')
    if kind=='company' and principal and principal.role!='admin' and row.created_by_person_id!=principal.person_id:raise ApiException(403,'PERMISSION_DENIED','公共公司档案仅创建人或管理员可修订')
    if row.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','目录对象已更新')
    fields=payload.model_fields_set-{'expected_version'}
    if not fields:raise ApiException(422,'VALIDATION_FAILED','需要提供修改内容')
    if payload.status=='inactive' and (directory_reference_in_use(session,kind,object_id) or (kind=='company' and company_identity_in_use(session,object_id))):raise ApiException(409,'CATALOG_IN_USE','仍有有效关联，不能停用目录对象')
    allowed={'name','description','status'} if kind=='company' else {'name','website','status'}
    if fields-allowed:raise ApiException(422,'VALIDATION_FAILED','该目录类型不支持此字段')
    for field in fields:
        value=getattr(payload,field)
        if field in {'name','status'} and (value is None or not str(value).strip()):raise ApiException(422,'VALIDATION_FAILED','名称和状态不能清空')
        setattr(row,field,str(value).strip() if value is not None else None)
    row.version+=1;row.updated_at=now()
    record_event(session,'catalog.updated',actor_id,request_id,data={'id':str(row.id),'version':row.version})
    session.commit();return row
