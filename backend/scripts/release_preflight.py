"""Fail closed on configuration, instance, schema, permissions or storage."""
import argparse,json,os,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import Settings
from app.platform.db.target import create_database_engine,verify_database_identity,verify_runtime_schema

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check-database',action='store_true');args=parser.parse_args()
    settings=Settings.from_environment()
    assert settings.app_env in {'staging','production'},'Release environment must be staging or production'
    assert settings.auth_provider=='local' and settings.auth_cookie_secure
    assert settings.auth_cookie_name not in {'digital_asset_platform_session'} or not settings.read_only,'Experience requires a separate cookie name'
    assert all(origin.startswith('https://') for origin in settings.allowed_origins),'Release origins require HTTPS'
    assert settings.instance_id and not settings.instance_id.startswith('digital-asset-platform-workspace')
    assert settings.release_id not in {'','local'}
    directory=Path(settings.private_file_root or '').resolve();assert directory.is_dir()
    probe=directory/('.release-probe-'+uuid4().hex)
    try:probe.write_bytes(b'probe');assert probe.read_bytes()==b'probe'
    finally:probe.unlink(missing_ok=True)
    if args.check_database:
        engine=create_database_engine(settings)
        with engine.connect() as conn:
            verify_database_identity(conn,expected_database=settings.expected_database,expected_instance_id=settings.instance_id,expected_environment=settings.app_env)
            verify_runtime_schema(conn)
            assert conn.exec_driver_sql("select rolsuper or rolcreatedb or rolcreaterole or rolbypassrls from pg_roles where rolname=current_user").scalar_one() is False
            assert conn.exec_driver_sql("select has_schema_privilege(current_user,'public','CREATE')").scalar_one() is False
        engine.dispose()
    print(json.dumps({'configuration':'passed','database_checked':args.check_database,'read_only':settings.read_only,'release_id':settings.release_id}))

if __name__=='__main__':main()
