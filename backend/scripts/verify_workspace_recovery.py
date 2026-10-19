"""Exercise upgrades and a custom-format backup only in the restore sandbox.

The destructive part is limited to public-schema objects in the dedicated
workspace_restore database, after checking both its exact name and marker.
Never accepts an arbitrary database URL or restore file from the caller.
"""
import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from uuid import uuid4
from alembic.config import Config
from alembic.script import ScriptDirectory

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / ".local/workspace"
DATABASE = "digital_asset_platform_workspace_restore"
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.modules.credentials.application.crypto import encrypt_secret,decrypt_secret


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-bin", default="D:/Middleware/Database/PostgreSQL/bin")
    args = parser.parse_args()
    config = json.loads((PRIVATE / "environment.json").read_text(encoding="utf-8"))
    head=ScriptDirectory.from_config(Config(str(ROOT/'backend/alembic.ini'))).get_current_head()
    target = config["targets"]["restore"]
    url = make_url(target["MIGRATOR_DATABASE_URL"])
    if url.database != DATABASE or url.host != "127.0.0.1" or url.username != "dap_workspace_restore_migrator":
        raise SystemExit("Refusing a target outside the dedicated restore sandbox")
    kwargs = dict(host=url.host, port=url.port, dbname=url.database, user=url.username, password=url.password)
    result = {"database": DATABASE, "started_at": datetime.now(UTC).isoformat(), "protected_databases_modified": False}

    def migrate(revision):
        run = subprocess.run([sys.executable, "scripts/workspace_command.py", "restore", "python", "-m", "alembic", "upgrade", revision], cwd=ROOT / "backend", capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError("Sandbox migration failed; inspect its configuration and migration tests")

    with psycopg.connect(**kwargs) as connection:
        exists = connection.execute("select to_regclass('public.instance_metadata')").fetchone()[0]
        if exists:
            marker = connection.execute("select instance_id,environment from instance_metadata").fetchone()
            if marker != (target["INSTANCE_ID"], target["APP_ENV"]):
                raise SystemExit("Restore sandbox marker differs; refusing to alter it")
        elif connection.execute("select count(*) from information_schema.tables where table_schema='public'").fetchone()[0]:
            raise SystemExit("Unmarked nonempty restore sandbox; refusing to alter it")
        # This named database is exclusively for destructive recovery exercises.
        # Verify ownership as well before dropping its schema.
        if connection.execute("select current_user=pg_get_userbyid(datdba) from pg_database where datname=current_database()").fetchone()[0] is not True:
            raise SystemExit("Restore sandbox owner differs")
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
        connection.commit()
    migrate("0004_material_version")
    row_id = uuid4()
    with psycopg.connect(**kwargs) as connection:
        connection.execute("INSERT INTO resource(id,code,name,type_code) VALUES(%s,%s,%s,%s)", (row_id, "recovery-synthetic-probe", "Synthetic recovery probe", "application"))
        connection.commit()
    migrate("head")
    migrate("head")
    with psycopg.connect(**kwargs) as connection:
        assert connection.execute("select name,created_by_person_id from resource where id=%s", (row_id,)).fetchone() == ("Synthetic recovery probe", None)
        assert connection.execute("select version_num from alembic_version").fetchone()[0] == head
    result.update(v2_start_upgrade=True, repeat_upgrade=True, v2_row_preserved=True)
    # Add one synthetic encrypted value and one private attachment before backup.
    # No credential from a user's provider configuration is used in this drill.
    key_settings=Settings(credential_master_key=config['shared']['CREDENTIAL_MASTER_KEY'],credential_key_version=config['shared'].get('CREDENTIAL_KEY_VERSION','key-1'))
    credential_id,person_id,file_id=uuid4(),uuid4(),uuid4()
    protected=encrypt_secret(key_settings,'synthetic-recovery-secret',associated_data=f'credential:{credential_id}'.encode())
    file_key=file_id.hex+'.bin';file_body=b'Synthetic private attachment recovery proof'
    file_root=PRIVATE/'restore-files';file_root.mkdir(exist_ok=True)
    (file_root/file_key).write_bytes(file_body)
    with psycopg.connect(**kwargs) as connection:
        connection.execute("INSERT INTO person(id,display_name,status) VALUES(%s,%s,'active')",(person_id,'Synthetic recovery person'))
        connection.execute("INSERT INTO credential_ref(id,resource_id,kind,status,ciphertext,nonce,key_version) VALUES(%s,%s,'password','saved',%s,%s,%s)",(credential_id,row_id,protected.ciphertext,protected.nonce,protected.key_version))
        connection.execute("INSERT INTO private_file(id,resource_id,filename,storage_key,media_type,size_bytes,sha256,check_policy,created_by_person_id) VALUES(%s,%s,'recovery.txt',%s,'text/plain',%s,%s,'type-and-signature-v1-no-antivirus',%s)",(file_id,row_id,file_key,len(file_body),hashlib.sha256(file_body).hexdigest(),person_id))
        connection.commit()
    files_backup=PRIVATE/'restore-sandbox.files.zip'
    with zipfile.ZipFile(files_backup,'w') as archive:archive.write(file_root/file_key,file_key)
    backup = PRIVATE / "restore-sandbox.dump"
    env = {**os.environ, "PGPASSWORD": url.password}
    options = ["--host", url.host, "--port", str(url.port), "--username", url.username, "--dbname", url.database]
    dump = subprocess.run([str(Path(args.pg_bin) / "pg_dump.exe"), *options, "--format=custom", "--no-owner", "--no-acl", "--file", str(backup)], env=env, capture_output=True)
    if dump.returncode:
        raise RuntimeError("Sandbox pg_dump failed")
    listing = subprocess.run([str(Path(args.pg_bin) / "pg_restore.exe"), "--list", str(backup)], capture_output=True)
    assert listing.returncode == 0 and b"resource" in listing.stdout and b"instance_metadata" in listing.stdout
    with psycopg.connect(**kwargs) as connection:
        connection.execute('DELETE FROM private_file WHERE id=%s',(file_id,))
        connection.execute('DELETE FROM credential_ref WHERE id=%s',(credential_id,))
        connection.execute("DELETE FROM resource WHERE id=%s", (row_id,))
        connection.commit()
    restored = subprocess.run([str(Path(args.pg_bin) / "pg_restore.exe"), *options, "--clean", "--if-exists", "--no-owner", "--no-acl", "--single-transaction", str(backup)], env=env, capture_output=True)
    if restored.returncode:
        raise RuntimeError("Sandbox pg_restore failed")
    with psycopg.connect(**kwargs) as connection:
        assert connection.execute("select name from resource where id=%s", (row_id,)).fetchone()[0] == "Synthetic recovery probe"
        assert connection.execute("select instance_id,environment from instance_metadata").fetchone() == (target["INSTANCE_ID"], target["APP_ENV"])
        assert connection.execute("select version_num from alembic_version").fetchone()[0] == head
        restored_secret=connection.execute('SELECT ciphertext,nonce,key_version FROM credential_ref WHERE id=%s',(credential_id,)).fetchone()
        assert decrypt_secret(key_settings,ciphertext=restored_secret[0],nonce=restored_secret[1],key_version=restored_secret[2],associated_data=f'credential:{credential_id}'.encode())=='synthetic-recovery-secret'
        restored_file=connection.execute('SELECT storage_key,sha256 FROM private_file WHERE id=%s',(file_id,)).fetchone()
        with zipfile.ZipFile(files_backup) as archive:
            assert archive.namelist()==[restored_file[0]]
            recovered=archive.read(restored_file[0])
        recovered_root=PRIVATE/'restore-files-recovered';recovered_root.mkdir(exist_ok=True)
        recovered_path=(recovered_root/restored_file[0]).resolve()
        assert recovered_path.parent==recovered_root.resolve()
        recovered_path.write_bytes(recovered)
        assert hashlib.sha256(recovered_path.read_bytes()).hexdigest()==restored_file[1]
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(target["runtime"])))
        connection.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(target["runtime"])))
        connection.commit()
    result.update(backup_readable=True, restore_row_and_marker=True,credential_decryption=True,private_file_restored=True,migration_head=head, backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(), finished_at=datetime.now(UTC).isoformat())
    (PRIVATE / "recovery-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
