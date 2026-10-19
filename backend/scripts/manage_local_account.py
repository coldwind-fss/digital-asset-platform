"""Offline operator recovery for an existing active administrator only.

Run through workspace_command.py so the target is explicit. This command does
not set a password, reactivate a disabled account, or promote a member.
"""
from pathlib import Path
import argparse
import json
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import Settings
from app.modules.identity_access.application import service
from app.platform.db.models import AuthAccount
from app.platform.db.target import create_database_engine, verify_database_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    if not args.reason.strip():
        parser.error("A recovery reason is required")
    settings = Settings.from_environment()
    if settings.auth_provider != "local":
        raise SystemExit("Recovery is available only for the local authentication provider")
    engine = create_database_engine(settings)
    with engine.connect() as connection:
        verify_database_identity(connection, expected_database=settings.expected_database or "", expected_instance_id=settings.instance_id or "", expected_environment=settings.app_env)
    destination = ROOT.parent / ".local/workspace" / f"recovery-{uuid4().hex}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Session(engine) as session:
            service.identity_lock(session)
            account = session.scalar(select(AuthAccount).where(AuthAccount.username == args.username.strip().lower()).with_for_update())
            if account is None or account.role != "admin" or account.status != "active":
                raise SystemExit("Only an existing active administrator can be recovered offline")
            raw, expires = service.issue_token(session, account, "recover")
            service.revoke_sessions(session, account.id)
            service.audit(session, "auth.offline_recovery_issued", None, uuid4(), {"account_id": str(account.id), "reason": args.reason.strip()})
            # Write the private material before committing. A failed write rolls
            # back the token and leaves the administrator's session intact.
            with destination.open("x", encoding="utf-8") as output:
                json.dump({"username": account.username, "action_token": raw, "expires_at": expires.isoformat(), "expected_database": settings.expected_database}, output, indent=2)
            session.commit()
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        engine.dispose()
    print(json.dumps({"recovery_file": str(destination), "expires_at": expires.isoformat(), "password_changed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
