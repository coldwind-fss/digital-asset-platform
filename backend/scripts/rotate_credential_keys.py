"""Explicit offline key rotation. Supply current key and old read keys in env."""
from pathlib import Path
import argparse,json,sys,subprocess,shutil,re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sqlalchemy.orm import Session
from app.config import Settings
from app.platform.db.target import create_database_engine,verify_database_identity
from app.modules.credentials.application.key_rotation import rotate_material


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup",required=True,help="Existing custom-format PostgreSQL backup matching this target")
    parser.add_argument('--pg-restore',default=shutil.which('pg_restore') or 'D:/Middleware/Database/PostgreSQL/bin/pg_restore.exe')
    args=parser.parse_args()
    backup=Path(args.backup).resolve(strict=True)
    with backup.open('rb') as stream:
        if stream.read(5)!=b'PGDMP':raise SystemExit("A readable custom-format PostgreSQL backup is required")
    settings=Settings.from_environment()
    listing=subprocess.run([args.pg_restore,'--list',str(backup)],capture_output=True)
    if listing.returncode or not re.search(rb'^;\s+dbname:\s+'+re.escape(settings.expected_database.encode())+rb'\s*$',listing.stdout,re.M):raise SystemExit('Backup database name does not match the selected target')
    if not settings.credential_master_key or not settings.credential_read_keys:raise SystemExit("Inject a new write key/version and the old versioned read key map first")
    engine=create_database_engine(settings)
    try:
        with engine.connect() as connection:verify_database_identity(connection,expected_database=settings.expected_database,expected_instance_id=settings.instance_id,expected_environment=settings.app_env)
        with Session(engine) as session:
            result=rotate_material(session,settings)
            session.commit()
        print(json.dumps({"database":settings.expected_database,**result}))
    finally:engine.dispose()


if __name__=="__main__":main()
