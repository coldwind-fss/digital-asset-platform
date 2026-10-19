"""Explicit first-install provisioning for main/demo/rehearsal on Linux.

Run as root on the approved host only. Existing targets are never reset.
Secrets are generated on that server and never printed or sent to browsers.
"""
import base64,json,os,pwd,secrets,subprocess,sys
from pathlib import Path
from psycopg import sql

ROOT=Path('/opt/digital-asset-platform')

def psql(query, database='postgres'):
    result=subprocess.run(['runuser','-u','postgres','--','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-d',database],input=query,text=True,capture_output=True)
    if result.returncode:raise RuntimeError('PostgreSQL provisioning failed; no sensitive query was logged')
    return result.stdout.strip()

def private_json(path,data,group=None):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640 if group else 0o600)
    with os.fdopen(descriptor,'w') as stream:json.dump(data,stream,ensure_ascii=False,indent=2)
    if group:os.chown(path,0,pwd.getpwnam(group).pw_gid)

def main():
    assert os.geteuid()==0
    release=json.loads((ROOT/'current/release.json').read_text())['release_id']
    for name,port,public_port in [('main',18305,8093),('demo',18306,8094),('rehearsal',18307,0)]:
        db='digital_asset_platform_'+name
        directory=Path('/etc/digital-asset-platform')/name
        if (directory/'app.json').exists():
            print(name+': existing configuration retained');continue
        assert not psql(sql.SQL('SELECT 1 FROM pg_database WHERE datname={}').format(sql.Literal(db)).as_string()),'Existing unconfigured database; refusing takeover'
        user='dap-'+name
        try:pwd.getpwnam(user)
        except KeyError:subprocess.run(['useradd','--system','--no-create-home','--shell','/sbin/nologin',user],check=True)
        migrator='dap_'+name+'_migrator';runtime='dap_'+name+'_runtime'
        passwords={migrator:secrets.token_urlsafe(36),runtime:secrets.token_urlsafe(36)}
        for role,password in passwords.items():
            assert not psql(sql.SQL('SELECT 1 FROM pg_roles WHERE rolname={}').format(sql.Literal(role)).as_string()),'Existing role; refusing takeover'
            psql(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS').format(sql.Identifier(role),sql.Literal(password)).as_string())
        psql(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(db),sql.Identifier(migrator)).as_string())
        psql(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC; GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(db),sql.Identifier(db),sql.Identifier(runtime)).as_string())
        psql(sql.SQL('REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE,CREATE ON SCHEMA public TO {}; GRANT USAGE ON SCHEMA public TO {}; ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {}').format(sql.Identifier(migrator),sql.Identifier(runtime),sql.Identifier(migrator),sql.Identifier(runtime)).as_string(),db)
        directory.mkdir(parents=True,mode=0o750);os.chown(directory,0,pwd.getpwnam(user).pw_gid)
        storage=Path('/var/lib/digital-asset-platform')/name/'private-files';storage.mkdir(parents=True,mode=0o700);os.chown(storage,user_id:=pwd.getpwnam(user).pw_uid,pwd.getpwnam(user).pw_gid);os.chown(storage.parent,user_id,pwd.getpwnam(user).pw_gid);storage.parent.chmod(0o700)
        origin='https://114.55.146.5:'+str(public_port) if public_port else 'https://127.0.0.1:18443'
        config={'APP_ENV':'staging' if name=='rehearsal' else 'production','APP_DEBUG':False,'AUTH_PROVIDER':'local','AUTH_COOKIE_SECURE':True,'AUTH_COOKIE_NAME':'dap_'+name+'_session','APP_READ_ONLY':name=='demo','ALLOWED_ORIGINS':json.dumps([origin]),'TRUSTED_HOSTS':json.dumps(['114.55.146.5','127.0.0.1','localhost']),'RELEASE_ID':release,'APP_PORT':port,'EXPECTED_DATABASE':db,'INSTANCE_ID':'digital-asset-platform-server-'+name,'DATABASE_URL':f'postgresql+psycopg://{runtime}:{passwords[runtime]}@127.0.0.1:5432/{db}','CREDENTIAL_MASTER_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),'CREDENTIAL_KEY_VERSION':'key-1','PRIVATE_FILE_ROOT':str(storage),'ATTACHMENT_SCAN_REQUIRED':False,'DB_POOL_SIZE':3,'DB_MAX_OVERFLOW':2}
        if name!='demo':config['AUTH_BOOTSTRAP_TOKEN']=secrets.token_urlsafe(36)
        migration={'APP_ENV':config['APP_ENV'],'EXPECTED_DATABASE':db,'INSTANCE_ID':config['INSTANCE_ID'],'MIGRATOR_DATABASE_URL':f'postgresql+psycopg://{migrator}:{passwords[migrator]}@127.0.0.1:5432/{db}','RUNTIME_DATABASE_USER':runtime}
        private_json(directory/'app.json',config,user);private_json(directory/'migration.json',migration)
        (directory/'service.env').write_text('DAP_PORT='+str(port)+'\n');(directory/'service.env').chmod(0o644)
        print(name+': isolated database, roles, private key/storage and cookie prepared')

if __name__=='__main__':main()
