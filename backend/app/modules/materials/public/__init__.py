"""Public HTTP ports exposed by the materials context."""

from app.modules.materials.api.routes import router
from app.modules.materials.application.service import validate_classification

def get_files_router():
    from app.modules.materials.api.files import router
    return router


def execution_evidence(session,resource_id,identifiers):
    from sqlalchemy import select
    from app.platform.db.models import Material
    from app.platform.http.errors import ApiException
    rows=session.scalars(select(Material).where(Material.id.in_(identifiers),Material.resource_id==resource_id,Material.archived_at.is_(None))).all()
    if len(rows)!=len(set(identifiers)):raise ApiException(422,'VALIDATION_FAILED','证据必须来自同一资源的可见有效资料')
    for row in rows:
        if row.kind=='attachment':
            from uuid import UUID
            from app.modules.materials.application.files import available_file,binary_path
            file=available_file(session,UUID(row.file_ref),resource_id)
            if not binary_path(session.info['settings'],file.storage_key).is_file():raise ApiException(503,'DEPENDENCY_UNAVAILABLE','证据附件暂不可读')
    return sorted([{'id':str(row.id),'version':row.version} for row in rows],key=lambda x:x['id'])

__all__ = ["router"]
