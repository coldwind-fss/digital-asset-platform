"""Private immutable binaries with database-owned availability and compensation."""
from hashlib import sha256
from pathlib import Path
from uuid import UUID,uuid4
import re
from sqlalchemy import select
from app.platform.db.models import PrivateFile
from app.platform.db.commands import now,write_resource,record_event
from app.platform.http.errors import ApiException

MAX_SIZE=10*1024*1024


def private_root(settings):
    if not settings.private_file_root:raise ApiException(503,'DEPENDENCY_UNAVAILABLE','私有附件目录未配置')
    root=Path(settings.private_file_root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    return root


def binary_path(settings,key):
    root=private_root(settings)
    if not re.fullmatch(r'[0-9a-f]{32}\.bin',key):raise ApiException(503,'DEPENDENCY_UNAVAILABLE','附件存储标识无效')
    path=(root/key).resolve()
    if path.parent!=root:raise ApiException(503,'DEPENDENCY_UNAVAILABLE','附件路径无效')
    return path


def check_content(filename,body):
    if not body or len(body)>MAX_SIZE:raise ApiException(422,'INVALID_FILE','附件大小必须在1字节到10MiB之间')
    if len(filename)>200 or any(c in filename for c in '/\\\r\n\x00') or any(ord(c)<32 for c in filename):raise ApiException(422,'INVALID_FILE','文件名无效')
    suffix=Path(filename).suffix.lower()
    if suffix=='.txt':
        try:value=body.decode('utf-8-sig')
        except UnicodeDecodeError:raise ApiException(422,'INVALID_FILE','文本必须是UTF-8') from None
        if '\x00' in value or re.search(r'<\s*(?:html|script|svg|iframe)|sk-[A-Za-z0-9_-]{20,}',value,re.I):raise ApiException(422,'INVALID_FILE','附件包含不允许的内容')
        return 'text/plain'
    if suffix=='.png' and body.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in body[-16:]:return 'image/png'
    if suffix in {'.jpg','.jpeg'} and body.startswith(b'\xff\xd8\xff') and body.endswith(b'\xff\xd9'):return 'image/jpeg'
    if suffix=='.pdf' and body.startswith(b'%PDF-') and b'%%EOF' in body[-1024:]:return 'application/pdf'
    raise ApiException(422,'INVALID_FILE','仅接受内容与扩展名一致的TXT、PNG、JPEG或PDF')


def upload(session,settings,resource_id,filename,body,classification,actor_id,request_id,replaces_file_id=None,expected_version=None):
    write_resource(session,resource_id)
    if classification!='normal':
        principal=session.info.get('local_principal')
        if principal and 'materials.restricted' not in principal.capabilities:raise ApiException(403,'PERMISSION_DENIED','受限附件需要独立权限')
    if settings.attachment_scan_required:raise ApiException(503,'DEPENDENCY_UNAVAILABLE','配置要求外部扫描，但扫描器尚未接入')
    media_type=check_content(filename,body)
    previous=None
    if replaces_file_id:
        previous=session.scalar(select(PrivateFile).where(PrivateFile.id==replaces_file_id).with_for_update())
        if not previous or previous.resource_id!=resource_id:raise ApiException(404,'RESOURCE_NOT_FOUND','被替换的附件不存在或不可见')
        if previous.status!='available' or previous.version!=expected_version:raise ApiException(409,'STATE_CONFLICT','附件版本或状态已变化')
    key=uuid4().hex+'.bin';path=binary_path(settings,key)
    try:
        with path.open('xb') as output:output.write(body);output.flush()
    except OSError:
        path.unlink(missing_ok=True)
        raise ApiException(503,'DEPENDENCY_UNAVAILABLE','附件未能写入私有存储') from None
    session.info.setdefault('rollback_callbacks',[]).append(lambda:path.unlink(missing_ok=True))
    row=PrivateFile(resource_id=resource_id,filename=filename,storage_key=key,media_type=media_type,size_bytes=len(body),sha256=sha256(body).hexdigest(),classification=classification,check_policy='type-and-signature-v1-no-antivirus',created_by_person_id=actor_id,replaces_file_id=replaces_file_id)
    if previous:previous.status='replaced';previous.ended_at=now();previous.version+=1
    session.add(row);session.flush()
    record_event(session,'file.uploaded',actor_id,request_id,resource_id,{'file_id':str(row.id),'size_bytes':len(body),'replaces_file_id':str(replaces_file_id) if replaces_file_id else None})
    session.commit();return row


def available_file(session,file_id,resource_id=None):
    row=session.get(PrivateFile,file_id)
    if not row or (resource_id and row.resource_id!=resource_id) or row.status!='available':raise ApiException(404,'RESOURCE_NOT_FOUND','附件不存在、已结束或不可见')
    return row


def end_file(session,file_id,payload,actor_id,request_id):
    row=available_file(session,file_id);write_resource(session,row.resource_id)
    row=session.scalar(select(PrivateFile).where(PrivateFile.id==file_id).with_for_update().execution_options(populate_existing=True))
    if row.version!=payload.expected_version or row.status!='available':raise ApiException(409,'STATE_CONFLICT','附件版本或状态已变化')
    row.status='ended';row.ended_at=now();row.version+=1
    record_event(session,'file.ended',actor_id,request_id,row.resource_id,{'file_id':str(row.id),'reason':payload.reason})
    session.commit();return row
