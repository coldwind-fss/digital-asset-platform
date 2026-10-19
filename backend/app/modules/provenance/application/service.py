import csv
import io
import hashlib
import re
from datetime import timedelta
from uuid import UUID
from pydantic import ValidationError
from sqlalchemy import select,func
from app.modules.resources.public import validate_import_payload,import_resource
from app.platform.db.models import ImportBatch,Resource,Platform,Department,ProvenanceEntry
from app.platform.db.commands import now,record_event
from app.platform.http.errors import ApiException

FIELDS={'name','provider_name','purpose','platform_id','owning_department_id','source_note','domain_name','expires_on','endpoint','external_instance_id'}
SECRET=re.compile(r'password|secret|token|credential|api.?key|密码|密钥|凭据|sk-[A-Za-z0-9_-]{20,}',re.I)


def batch(session,batch_id,lock=False):
    stmt=select(ImportBatch).where(ImportBatch.id==batch_id)
    if lock:stmt=stmt.with_for_update().execution_options(populate_existing=True)
    row=session.scalar(stmt)
    if not row:raise ApiException(404,'RESOURCE_NOT_FOUND','导入批次不存在或不可见')
    return row


def references(session,data):
    versions={}
    for key,model in [('platform_id',Platform),('owning_department_id',Department)]:
        if data.get(key):
            target=session.get(model,UUID(data[key]))
            if not target or target.status=='inactive':raise ApiException(404,'REFERENCE_NOT_FOUND','引用对象不存在、不可见或已停用')
            versions[key]=target.version
    return versions


def candidates(session,data):
    stmt=select(Resource.id).where(func.lower(Resource.name)==data['name'].lower(),Resource.type_code==data['type_code'],Resource.archived_at.is_(None))
    if data.get('platform_id'):stmt=stmt.where(Resource.platform_id==UUID(data['platform_id']))
    return list(map(str,session.scalars(stmt.limit(25))))


def preview(session,payload,actor_id,request_id):
    raw=payload.csv_content.encode('utf-8')
    if len(raw)>5*1024*1024:raise ApiException(422,'IMPORT_TOO_LARGE','CSV不得超过5MiB')
    reader=csv.DictReader(io.StringIO(payload.csv_content.lstrip('\ufeff')),strict=True)
    headers=reader.fieldnames
    if not headers or len(set(headers))!=len(headers) or len(headers)>30:raise ApiException(422,'INVALID_CSV','CSV表头缺失、重复或过多')
    if any(SECRET.search(x) for x in headers):raise ApiException(422,'SECRET_IMPORT_FORBIDDEN','普通导入不得包含秘密列')
    if set(payload.mapping)-set(headers) or len(set(payload.mapping.values()))!=len(payload.mapping):raise ApiException(422,'INVALID_MAPPING','映射来源或目标无效')
    mapping={h:payload.mapping.get(h,h) for h in headers}
    if set(mapping.values())-FIELDS or len(set(mapping.values()))!=len(mapping):raise ApiException(422,'INVALID_MAPPING','映射只允许当前类型的公开字段，且不能重复')
    rows=[];results=[];seen=set()
    try:
        for number,row in enumerate(reader,start=2):
            if len(rows)>=1000:raise ApiException(422,'IMPORT_TOO_LARGE','单批最多1000行')
            if None in row or None in row.values():raise ApiException(422,'INVALID_CSV','CSV列数不一致')
            data={mapping[k]:v.strip() for k,v in row.items() if v.strip()}
            if any(SECRET.search(v) for v in data.values()):raise ApiException(422,'SECRET_IMPORT_FORBIDDEN','CSV包含疑似秘密，请使用凭据功能')
            attrs={k:data.pop(k) for k in list(data) if k in {'domain_name','expires_on','endpoint','external_instance_id'}}
            data.update(type_code=payload.type_code,attributes=attrs,source_note=data.get('source_note') or payload.label)
            result={'row_number':number,'status':'ready','message':None,'candidate_ids':[],'resource_id':None};reference_versions={}
            try:
                data=validate_import_payload(data);reference_versions=references(session,data)
                ids=candidates(session,data);identity=(data['type_code'],data['name'].lower(),data.get('platform_id'))
                if ids or identity in seen:result.update(status='duplicate_candidate',message='发现同名候选；本批不合并，请跳过或重新预览',candidate_ids=ids)
                seen.add(identity)
            except (ValidationError,ApiException,ValueError) as error:
                result.update(status='error',message=error.message if isinstance(error,ApiException) else '字段格式或类型不符合模板')
                data={} # Never persist malformed or unknown data.
            rows.append({'row_number':number,'payload':data,'reference_versions':reference_versions});results.append(result)
    except csv.Error:raise ApiException(422,'INVALID_CSV','CSV格式无效') from None
    if not rows:raise ApiException(422,'INVALID_CSV','CSV没有数据行')
    record=ImportBatch(created_by_person_id=actor_id,type_code=payload.type_code,label=payload.label,mapping=mapping,content_digest=hashlib.sha256(raw).hexdigest(),rows=rows,results=results,expires_at=now()+timedelta(hours=24))
    session.add(record);session.flush();record_event(session,'import.previewed',actor_id,request_id,data={'batch_id':str(record.id),'row_count':len(rows)})
    session.commit();return record


def commit(session,batch_id,payload,actor_id,request_id):
    row=batch(session,batch_id,True)
    if row.status=='committed':return row
    if row.expires_at<=now():raise ApiException(410,'IMPORT_EXPIRED','预览已过期，请重新上传')
    if row.version!=payload.expected_version:raise ApiException(409,'STATE_CONFLICT','批次版本已变化')
    numbers={x['row_number'] for x in row.rows};skips=set(payload.skip_rows)
    if skips-numbers:raise ApiException(422,'VALIDATION_FAILED','跳过行不属于当前批次')
    for result in row.results:
        if result['row_number'] not in skips and result['status']!='ready':raise ApiException(409,'IMPORT_REVIEW_REQUIRED','请明确跳过错误/重复候选行，或修复后重新预览')
    results=[]
    for source in row.rows:
        number=source['row_number']
        if number in skips:results.append({'row_number':number,'status':'skipped','candidate_ids':[]});continue
        data=validate_import_payload(source['payload'])
        if references(session,data)!=source.get('reference_versions',{}):raise ApiException(409,'IMPORT_SOURCE_CHANGED','引用对象版本已变化，请重新预览')
        if candidates(session,data):raise ApiException(409,'IMPORT_SOURCE_CHANGED','候选数据已变化，请重新预览')
        created=import_resource(session,data)
        session.add(ProvenanceEntry(resource_id=created.id,source_kind='csv_import',label=row.label,source_ref=f'{row.id}:row:{number}',created_by_person_id=actor_id))
        results.append({'row_number':number,'status':'created','resource_id':str(created.id),'candidate_ids':[]})
    row.results=results;row.status='committed';row.committed_at=now();row.version+=1;row.rows=[]
    record_event(session,'import.committed',actor_id,request_id,data={'batch_id':str(row.id),'created':sum(r['status']=='created' for r in results)})
    session.commit();return row


def safe_cell(value):
    text='' if value is None else str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r')) else text


def csv_document(headers,rows):
    output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(headers)
    for row in rows:writer.writerow([safe_cell(x) for x in row])
    return '\ufeff'+output.getvalue()


def export_resources(session):
    rows=session.scalars(select(Resource).where(Resource.archived_at.is_(None)).order_by(Resource.id)).all()
    # Public export excludes secrets, login identifiers and financial facts.
    return csv_document(['id','name','type_code','provider_name','purpose','lifecycle','verification'],[(r.id,r.name,r.type_code,r.provider_name,r.purpose,r.lifecycle,r.verification) for r in rows])


def cleanup_expired_previews(session,instant):
    rows=session.scalars(select(ImportBatch).where(ImportBatch.status=='preview',ImportBatch.expires_at<=instant).with_for_update(skip_locked=True)).all()
    for row in rows:row.status='expired';row.rows=[];row.version+=1
    return len(rows)
