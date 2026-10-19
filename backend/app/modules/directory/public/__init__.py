"""Public HTTP ports exposed by the directory context."""

from app.modules.directory.api.routes import router

__all__ = ["router"]


def get_catalog_router():
    from app.modules.directory.api.management import router
    from app.modules.directory.api.people_management import router as people_router
    from fastapi import APIRouter
    catalog=APIRouter();catalog.include_router(router);catalog.include_router(people_router)
    return catalog

def graph_directory_node(session,kind,identifier):
    from app.platform.db.models import Company,Platform,Person,ContactIdentity
    models={'company':Company,'platform':Platform,'person':Person,'identity':ContactIdentity}
    model=models.get(kind)
    row=session.get(model,identifier) if model else None
    if not row:return None
    if kind=='person':label=row.display_name
    elif kind=='identity':label=row.label or row.masked_value or '受保护身份'
    else:label=row.name
    return dict(id=str(row.id),kind=kind,label=label,type_code=kind,verification=row.verification if kind=='identity' else row.status,lifecycle=None)
