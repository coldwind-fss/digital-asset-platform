"""Read-only browser fixture fingerprint before/after a local service restart."""
from pathlib import Path
import json,hashlib,sys
import httpx

def main():
    root=Path(__file__).resolve().parents[2]
    state=json.loads((root/'.local/workspace/services.json').read_text(encoding='utf-8-sig'))
    assert state['target']=='test','This probe only reads the synthetic test target'
    fixture=json.loads((root/'.local/workspace/stage3-browser-fixture.json').read_text(encoding='utf-8'))
    client=httpx.Client(base_url='http://127.0.0.1:8305/api/v1',headers={'Origin':'http://127.0.0.1:5175'})
    logged=client.post('/auth/login',json={'username':'stage-admin','password':'Stage1-Test-Password-2026!'})
    assert logged.status_code==200
    paths=['/resources?page_size=100','/change-cases/'+fixture['case_id'],f"/change-cases/{fixture['case_id']}/items",'/subscriptions/'+fixture['ledger_id'],f"/subscriptions/{fixture['ledger_id']}/periods",f"/subscriptions/{fixture['ledger_id']}/expenses",'/imports',f"/resources/{fixture['resources'][0]['id']}/files",'/me/notification-preferences','/people?page_size=100']
    values={}
    for path in paths:
        response=client.get(path);assert response.status_code==200,(path,response.status_code)
        values[path]=response.json()['data']
    content=json.dumps(values,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    report={'sha256':hashlib.sha256(content).hexdigest(),'resource_total':values[paths[0]]['pagination']['total'],'case_status':values[paths[1]]['status'],'period_total':values[paths[4]]['pagination']['total'],'import_total':values['/imports']['pagination']['total'],'file_total':values[paths[7]]['pagination']['total'],'person_total':values[paths[9]]['pagination']['total'],'show_due':values[paths[8]]['show_due']}
    path=root/'.local/workspace/stage3-persistence.json'
    if '--compare' in sys.argv:
        before=json.loads(path.read_text(encoding='utf-8'))
        assert before['before']==report,'Read-only business fingerprints changed across service restart'
        before.update(after=report,matched=True);path.write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Browser-created resource, governance, renewal, import, attachment and preference fingerprints match after restart.')
    else:
        path.write_text(json.dumps({'before':report,'matched':False},ensure_ascii=False,indent=2),encoding='utf-8');print(report)

if __name__=='__main__':main()
