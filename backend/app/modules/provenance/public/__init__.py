from app.modules.provenance.api.routes import router

def cleanup_expired_imports(*args,**kwargs):
    from app.modules.provenance.application.service import cleanup_expired_previews
    return cleanup_expired_previews(*args,**kwargs)
