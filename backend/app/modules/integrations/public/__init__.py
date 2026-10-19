from app.modules.integrations.api.routes import router


def run_worker_once(*args,**kwargs):
    from app.modules.integrations.application.service import run_once
    return run_once(*args,**kwargs)


def stop_resource_connections(*args,**kwargs):
    from app.modules.integrations.application.service import deactivate_resource_connections
    return deactivate_resource_connections(*args,**kwargs)
