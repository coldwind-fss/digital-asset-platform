"""Quiesced local DB + file backup for explicitly named server instances.

Contains no decryption keys. Keep matching /etc configuration separately.
"""
import argparse,fcntl,hashlib,json,os,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.platform.db.target import verify_database_identity

def fingerprint(connection):
    from sqlalchemy import inspect
    result={}
    for table in sorted(inspect(connection).get_table_names()):
        assert table.replace('_','').isalnum()
        result[table]=connection.exec_driver_sql('SELECT md5(COALESCE(string_agg(row_data::text,chr(10) ORDER BY row_data::text),\'\')) FROM (SELECT to_jsonb(t) AS row_data FROM "'+table+'" t) q').scalar_one()
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--instance',choices=['main','demo','rehearsal'],required=True);parser.add_argument('--quiesce',action='store_true');args=parser.parse_args()
    assert os.geteuid()==0
    label=args.instance;configuration=Path('/etc/digital-asset-platform')/label
    app=json.loads((configuration/'app.json').read_text());migration=json.loads((configuration/'migration.json').read_text())
    assert app['EXPECTED_DATABASE']=='digital_asset_platform_'+label
    lock=Path('/var/lib/digital-asset-platform')/(label+'.backup.lock')
    with lock.open('w') as lockfile:
        fcntl.flock(lockfile,fcntl.LOCK_EX|fcntl.LOCK_NB)
        services=['digital-asset-platform-api@'+label,'digital-asset-platform-jobs@'+label]
        active=[name for name in services if subprocess.run(['systemctl','is-active','--quiet',name]).returncode==0]
        assert args.quiesce or not active,'Pause API/worker first or use --quiesce'
        if args.quiesce:
            for name in active:subprocess.run(['systemctl','stop',name],check=True)
        try:
            destination=Path('/var/backups/digital-asset-platform')/label/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');destination.mkdir(parents=True,mode=0o700,exist_ok=False);destination.parent.chmod(0o700)
            engine=create_engine(migration['MIGRATOR_DATABASE_URL'],hide_parameters=True)
            with engine.connect() as conn:
                verify_database_identity(conn,expected_database=app['EXPECTED_DATABASE'],expected_instance_id=app['INSTANCE_ID'],expected_environment=app['APP_ENV'])
                rows=fingerprint(conn);head=conn.exec_driver_sql('select version_num from alembic_version').scalar_one()
            engine.dispose()
            url=make_url(migration['MIGRATOR_DATABASE_URL'])
            env={**os.environ,'PGHOST':url.host,'PGPORT':str(url.port or 5432),'PGDATABASE':url.database,'PGUSER':url.username,'PGPASSWORD':url.password}
            dumped=subprocess.run(['pg_dump','--format=custom','--no-owner','--no-acl','--file',str(destination/'database.dump')],env=env,capture_output=True)
            assert dumped.returncode==0,'Database backup failed; values suppressed'
            assert subprocess.run(['pg_restore','--list',str(destination/'database.dump')],capture_output=True).returncode==0
            storage=Path(app['PRIVATE_FILE_ROOT']).resolve();file_hashes={}
            with zipfile.ZipFile(destination/'private-files.zip','w',zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(storage.rglob('*')):
                    assert not path.is_symlink(),'Private file symlink rejected'
                    if path.is_file():
                        relative=path.relative_to(storage).as_posix();archive.write(path,relative);file_hashes[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
            metadata={'format':'dap-complete-backup-v1','instance':label,'database':app['EXPECTED_DATABASE'],'instance_id':app['INSTANCE_ID'],'environment':app['APP_ENV'],'head':head,'release_id':app['RELEASE_ID'],'key_version':app['CREDENTIAL_KEY_VERSION'],'keys_included':False,'table_fingerprints':rows,'file_sha256':file_hashes,'artifacts':{name:hashlib.sha256((destination/name).read_bytes()).hexdigest() for name in ['database.dump','private-files.zip']}}
            (destination/'manifest.json').write_text(json.dumps(metadata,indent=2));os.chmod(destination/'manifest.json',0o600)
            print(json.dumps({'backup':str(destination),'head':head,'tables':len(rows),'files':len(file_hashes),'keys_included':False}))
        finally:
            if args.quiesce:
                for name in active:subprocess.run(['systemctl','start',name],check=True)

if __name__=='__main__':main()
