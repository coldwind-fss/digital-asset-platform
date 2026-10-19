"""Build a portable, allowlisted release. Never packages local configs or data."""
import argparse,hashlib,json,subprocess,tarfile,io,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release-id',required=True);parser.add_argument('--output',default='.local/releases');args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}',args.release_id):parser.error('Invalid release ID')
    build=ROOT/'frontend/dist';assert (build/'index.html').is_file(),'Build the frontend first'
    selected=[]
    for prefix in ['backend/app','backend/alembic','backend/openapi','backend/scripts','deploy']:
        selected.extend(path for path in (ROOT/prefix).rglob('*') if path.is_file() and not any(part in {'.venv','__pycache__','.pytest_cache'} for part in path.parts) and not path.name.startswith('.env') and path.suffix not in {'.pyc','.log','.dump','.pem','.key'})
    selected.extend(ROOT/path for path in ['backend/pyproject.toml','backend/uv.lock','backend/alembic.ini'])
    selected.extend(path for path in build.rglob('*') if path.is_file())
    files={path.relative_to(ROOT).as_posix():path.read_bytes() for path in sorted(set(selected))}
    assert not any(name.startswith(('.local/','legacy-v1/')) for name in files)
    manifest={name:hashlib.sha256(body).hexdigest() for name,body in files.items()}
    metadata={'release_id':args.release_id,'built_at':datetime.now(timezone.utc).isoformat(),'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'uncommitted':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),'schema_head':'0017_notification_preferences','files':manifest}
    files['release.json']=(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n').encode()
    output=(ROOT/args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    destination=output/(args.release_id+'.tar.gz');assert not destination.exists(),'Release IDs are immutable'
    with tarfile.open(destination,'w:gz') as archive:
        for name,body in files.items():
            entry=tarfile.TarInfo(name);entry.size=len(body);entry.mode=0o644;archive.addfile(entry,io.BytesIO(body))
    with tarfile.open(destination) as archive:
        for name,digest in manifest.items():assert hashlib.sha256(archive.extractfile(name).read()).hexdigest()==digest
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix+'.sha256').write_bytes((digest+'  '+destination.name+'\n').encode())
    print(json.dumps({'release_id':args.release_id,'files':len(manifest),'artifact':str(destination),'sha256':digest}))

if __name__=='__main__':main()
