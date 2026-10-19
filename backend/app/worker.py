"""Separate local/server worker. No web startup migrations or embedded scheduler."""
import argparse,json,signal,time
from uuid import uuid4
from app.config import Settings
from app.platform.db.target import create_database_engine,verify_database_identity,verify_runtime_schema
from app.modules.integrations.public import run_worker_once


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--interval',type=int,default=30)
    args=parser.parse_args()
    if not 5<=args.interval<=60:parser.error('interval must be 5—60 seconds')
    settings=Settings.from_environment();engine=create_database_engine(settings)
    if settings.read_only:
        engine.dispose()
        raise SystemExit('Read-only experience never starts an external-sync worker')
    worker_id='worker-'+uuid4().hex
    with engine.connect() as connection:
        verify_database_identity(connection,expected_database=settings.expected_database,expected_instance_id=settings.instance_id,expected_environment=settings.app_env)
        verify_runtime_schema(connection)
    running=True
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    try:
        while running:
            try:result=run_worker_once(engine,settings,worker_id=worker_id)
            except Exception:result={'processed':False,'error_code':'WORKER_DEPENDENCY_UNAVAILABLE'}
            print(json.dumps({'worker_id':worker_id,**result}),flush=True)
            if args.once:break
            if not result.get('processed'):
                for _ in range(args.interval):
                    if not running:break
                    time.sleep(1)
    finally:engine.dispose()


if __name__=='__main__':main()
