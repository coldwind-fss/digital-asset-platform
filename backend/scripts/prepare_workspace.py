"""Provision only the named, isolated local workspace targets; never resets data."""
from pathlib import Path
import argparse
import base64
import json
import os
import secrets
import subprocess

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / ".local" / "workspace"
CONFIG = PRIVATE / "environment.json"
NAMES = {"dev": "digital_asset_platform_workspace_dev", "test": "digital_asset_platform_workspace_test", "restore": "digital_asset_platform_workspace_restore"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-user", default="digital_asset_platform_cluster_admin")
    parser.add_argument("--port", type=int, default=55433)
    parser.add_argument("--target", choices=["dev", "test", "restore", "all"], default="all")
    args = parser.parse_args()
    PRIVATE.mkdir(parents=True, exist_ok=True)
    if not CONFIG.exists():
        targets = {}
        for label, database in NAMES.items():
            suffix = "test" if label == "test" else "dev"
            migrator, runtime = f"dap_workspace_{label}_migrator", f"dap_workspace_{label}_runtime"
            migration_password, runtime_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            targets[label] = {
                "APP_ENV": "test" if label == "test" else "development", "EXPECTED_DATABASE": database,
                "INSTANCE_ID": f"digital-asset-platform-workspace-{suffix}", "RUNTIME_DATABASE_USER": runtime,
                "MIGRATOR_DATABASE_URL": f"postgresql+psycopg://{migrator}:{migration_password}@127.0.0.1:{args.port}/{database}",
                "DATABASE_URL": f"postgresql+psycopg://{runtime}:{runtime_password}@127.0.0.1:{args.port}/{database}",
                "migrator": migrator, "runtime": runtime, "migration_password": migration_password, "runtime_password": runtime_password,
            }
        config = {"format": 1, "port": args.port, "targets": targets,
            "shared": {"AUTH_PROVIDER": "local", "AUTH_BOOTSTRAP_TOKEN": secrets.token_urlsafe(32),
                "CREDENTIAL_MASTER_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                "ALLOWED_ORIGINS": json.dumps(["http://127.0.0.1:5175", "http://localhost:5175"]),
                "TRUSTED_HOSTS": json.dumps(["127.0.0.1", "localhost", "testserver"]),
                "APP_PORT": "8305", "VITE_API_PROXY_TARGET": "http://127.0.0.1:8305"}}
        CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    for label,target in config['targets'].items():
        target.setdefault('PRIVATE_FILE_ROOT',str((PRIVATE/'private-files'/label).resolve()))
        Path(target['PRIVATE_FILE_ROOT']).mkdir(parents=True,exist_ok=True)
    CONFIG.write_text(json.dumps(config,indent=2),encoding='utf-8')
    if config["port"] != args.port:
        raise SystemExit("Workspace port differs from its existing protected configuration")
    labels = list(NAMES) if args.target == "all" else [args.target]
    with psycopg.connect(host="127.0.0.1", port=args.port, user=args.admin_user, dbname="postgres", autocommit=True) as admin:
        if not admin.execute("select rolsuper from pg_roles where rolname=current_user").fetchone()[0]:
            raise SystemExit("Provisioning requires an explicitly selected local cluster administrator")
        for label in labels:
            target = config["targets"][label]
            database = target["EXPECTED_DATABASE"]
            if database != NAMES[label]:
                raise SystemExit("Refusing a database outside the workspace allowlist")
            for name, password in [(target["migrator"], target["migration_password"]), (target["runtime"], target["runtime_password"])]:
                existing = admin.execute("select rolsuper,rolcreatedb,rolcreaterole,rolbypassrls from pg_roles where rolname=%s", (name,)).fetchone()
                if existing and any(existing):
                    raise SystemExit("Existing workspace role has unexpected administrative privileges")
                if not existing:
                    admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS").format(sql.Identifier(name), sql.Literal(password)))
            owner = admin.execute("select pg_get_userbyid(datdba) from pg_database where datname=%s", (database,)).fetchone()
            if owner and owner[0] != target["migrator"]:
                raise SystemExit("Existing workspace database has an unexpected owner")
            if not owner:
                admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database), sql.Identifier(target["migrator"])))
            admin.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
            admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(target["runtime"])))
            with psycopg.connect(host="127.0.0.1", port=args.port, user=args.admin_user, dbname=database, autocommit=True) as connection:
                connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
                connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(target["runtime"])))
                connection.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(sql.Identifier(target["migrator"]), sql.Identifier(target["runtime"])))
                connection.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(target["runtime"])))
    print(json.dumps({"prepared": [NAMES[label] for label in labels], "configuration": ".local/workspace/environment.json", "existing_data_reset": False}))


if __name__ == "__main__":
    main()
