"""Execute one explicit server configuration, without shell eval or dotenv.

Runtime and migration JSON files are separate, private deployment artifacts.
The runtime process never receives the migration role's DSN.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import Settings, MigrationSettings


def configured_environment(path, mode):
    values=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(values,dict) or not all(isinstance(k,str) and k.isupper() and isinstance(v,(str,bool,int,float)) for k,v in values.items()):
        raise ValueError('Configuration must be a flat environment map')
    env={k:v for k,v in os.environ.items() if k not in {'DATABASE_URL','MIGRATOR_DATABASE_URL','INSTANCE_ID','EXPECTED_DATABASE','APP_READ_ONLY','AUTH_BOOTSTRAP_TOKEN','CREDENTIAL_MASTER_KEY','CREDENTIAL_READ_KEYS','AUTH_PROVIDER','DAP_POSTGRES_TESTS','DAP_STAGE1_POSTGRES_TESTS'}}
    env.update({k:str(v).lower() if isinstance(v,bool) else str(v) for k,v in values.items()})
    if mode=='runtime':
        if 'MIGRATOR_DATABASE_URL' in values:
            raise ValueError('Runtime configuration must not contain migration credentials')
        Settings.from_environment(env)
        env.pop('MIGRATOR_DATABASE_URL',None)
    else:
        MigrationSettings.from_environment(env)
    return env


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--mode',choices=['runtime','migration'],default='runtime')
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if not args.command:parser.error('An explicit command is required')
    try:env=configured_environment(args.config,args.mode)
    except Exception:raise SystemExit('Invalid or unavailable private configuration; values were not logged') from None
    command=args.command
    if command[0]=='python':command[0]=sys.executable
    os.chdir(ROOT)
    os.execvpe(command[0],command,env)

if __name__=='__main__':main()
