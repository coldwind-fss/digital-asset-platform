"""Run a command with one explicit private workspace target; do not echo secrets."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=["dev", "test", "restore"])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("A command is required")
    config = json.loads((ROOT / ".local/workspace/environment.json").read_text(encoding="utf-8"))
    target = config["targets"][args.target]
    env = {k:v for k,v in os.environ.items() if k not in {"DATABASE_URL", "MIGRATOR_DATABASE_URL", "INSTANCE_ID", "EXPECTED_DATABASE", "AUTH_PROVIDER", "VITE_TEST_SUBJECT", "VITE_TEST_CAPABILITIES"}}
    env.update(config["shared"])
    env.update({k:v for k,v in target.items() if k.isupper()})
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    if args.target == "test":
        env.update(DAP_POSTGRES_TESTS="1", DAP_STAGE1_POSTGRES_TESTS="1")
    command = args.command
    if command[0] == "python" and command[1:3] in (["-m", "uvicorn"],["-m", "app.worker"]):
        # Web workers receive only the runtime connection. Migration credentials
        # remain available solely to explicit migration/test commands.
        env.pop("MIGRATOR_DATABASE_URL", None)
    if command[0] == "python":
        command[0] = sys.executable
    return subprocess.run(command, cwd=ROOT / "backend", env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
