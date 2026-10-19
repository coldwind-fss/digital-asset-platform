"""Merge Stage 2 runtime operations and retain closed, compatible public DTOs."""
from copy import deepcopy
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.main import create_app
from app.config import Settings
from app.modules.resources.domain.rules import ATTRIBUTE_FIELDS


def main():
    path=ROOT/'openapi/v1.openapi.json';contract=json.loads(path.read_text(encoding='utf-8'))
    contract['paths'].pop('/change-items/{item_id}/actions/return',None)
    contract['paths'].pop('/files/{file_id}/download',None)
    schemas=contract['components']['schemas'];runtime=create_app(Settings(auth_provider='local')).openapi();source=runtime['components']['schemas'];copied={}
    stable={'ResourceCreateRequest':'ResourceCreate','ResourcePatchRequest':'ResourcePatch','ResourceView':'ResourceView','ResourceSummary':'ResourceSummary','MyResourceSummary':'MyResourceSummary'}
    def rewrite(value):
        if isinstance(value,list):return [rewrite(x) for x in value]
        if not isinstance(value,dict):return value
        result={k:rewrite(v) for k,v in value.items() if k!='$ref'}
        if '$ref' in value:
            name=value['$ref'].rsplit('/',1)[-1];target=stable.get(name,'Stage2'+name)
            if name not in stable and target not in copied:
                copied[target]={};copied[target]=rewrite(source[name])
            result['$ref']='#/components/schemas/'+target
        # Discriminator mapping contains plain reference strings, not $ref nodes.
        if 'mapping' in result and isinstance(result['mapping'],dict) and result['mapping'] and all(isinstance(v,str) and v.startswith('#/components/schemas/') for v in result['mapping'].values()):result['mapping']={k:'#/components/schemas/'+stable.get(v.rsplit('/',1)[-1],'Stage2'+v.rsplit('/',1)[-1]) for k,v in result['mapping'].items()}
        return result
    schemas['ResourceType']['enum']=list(ATTRIBUTE_FIELDS)
    for name in ('PersonAssignmentView','CompanyLinkView'):
        schemas[name]['properties']['assignment_id']={'type':'string','format':'uuid'}
        if 'assignment_id' not in schemas[name]['required']:schemas[name]['required'].append('assignment_id')
    common=schemas['ResourceCreateCommon']['properties']
    common.update(platform_id={'type':['string','null'],'format':'uuid'},source_note={'type':'string','minLength':1,'maxLength':500},lifecycle={'type':'string','enum':['unknown','in_use'],'default':'unknown'})
    names={'api_service':'ApiServiceCreate','cloud_resource':'CloudResourceCreate','domain':'DomainCreate'}
    for code,name in names.items():
        properties={k:{'type':['string','null'],'maxLength':2000} for k in ATTRIBUTE_FIELDS[code]}
        for k in ('registered_on','expires_on'):
            if k in properties:properties[k]={'type':['string','null'],'format':'date'}
        attrs={'type':'object','additionalProperties':False,'properties':properties}
        schemas[name]={'allOf':[{'$ref':'#/components/schemas/ResourceCreateCommon'},{'type':'object','properties':{'type_code':{'const':code},'attributes':attrs}}],'unevaluatedProperties':False}
        ref='#/components/schemas/'+name
        if {'$ref':ref} not in schemas['ResourceCreate']['oneOf']:schemas['ResourceCreate']['oneOf'].append({'$ref':ref})
        schemas['ResourceCreate']['discriminator']['mapping'][code]=ref
        if attrs not in schemas['ResourceAttributes']['anyOf']:schemas['ResourceAttributes']['anyOf'].append(attrs)
    schemas['RelationType']['enum']=['uses','managed_by','part_of','contains','depends_on']
    for target in [schemas['ApplicationCreate']['allOf'][1]['properties']['attributes'],schemas['ResourceAttributes']['anyOf'][-4]]:
        if 'tech_stack' in target.get('properties',{}):target['properties'].update(endpoint={'type':['string','null'],'maxLength':2000},environment={'type':['string','null'],'maxLength':2000})
    subscription=schemas['SubscriptionCreate']['allOf'][1]['properties']['attributes']
    extra={'seats':{'type':['integer','null'],'minimum':0},'billing_cycle':{'type':['string','null'],'enum':['month','year','custom',None]}}
    subscription['properties'].update(extra)
    for attrs in schemas['ResourceAttributes']['anyOf']:
        if 'plan' in attrs.get('properties',{}):attrs['properties'].update(extra)
    view=schemas['ResourceView']['allOf'][1]['properties']
    view['platform_id']={'type':['string','null'],'format':'uuid'}
    view['subscription_summary']={'anyOf':[{'$ref':'#/components/schemas/Stage2BasicSubscriptionSummary'},{'type':'null'}]}
    view['credential_status']['enum']=['not_saved','pending','saved','failed','superseded','revoked']
    # Runtime proposal union is authoritative; retain inlined closed branches for consumers.
    proposal=source['ChangeItemCreate']['properties']['proposal']
    branches=[deepcopy(source[x['$ref'].rsplit('/',1)[-1]]) for x in proposal['oneOf']]
    schemas['ChangeItemProposal']={'oneOf':branches,'discriminator':{'propertyName':'action'}}
    schemas['ChangeAction']['enum']=[b['properties']['action']['const'] for b in branches]
    schemas['ChangeItemView']['properties']['status']['enum']=['pending','in_progress','awaiting_confirmation','completed','cancelled','failed','cancellation_requested']
    count=0
    secret_ids=set();bodyless=set();binary_ids=set()
    for path_item,item in runtime['paths'].items():
        relative=path_item.removeprefix('/api/v1')
        if relative.startswith(('/auth/','/admin/','/health/')):continue
        for method,raw in item.items():
            if method not in {'get','post','patch','delete','put'}:continue
            old=contract['paths'].get(relative,{}).get(method,{})
            operation=rewrite(deepcopy(raw));operation['operationId']=old.get('operationId',raw['operationId']);operation['summary']=old.get('summary',raw.get('summary',operation['operationId']))
            identifier=operation['operationId'];writing=method!='get'
            operation['x-implementation-status']='implemented-v3-stage3' if relative in {'/asset-graph','/resource-roles','/me/notification-preferences'} else 'implemented-v3-stage2'
            operation['security']=[{'SessionCookie':[],**({'CsrfToken':[]} if writing else {})}]
            params=operation.setdefault('parameters',[])
            secret=any(s in relative for s in ['/credentials','/secret-stages','/credential-operations']) and writing
            if writing and secret:
                secret_ids.add(identifier);operation['x-retry-policy']='Secrets are never replay-cached; inspect safe state before retry. Stage token is single-use; expected_version rejects stale updates.'
            elif writing and not any(p.get('in')=='header' and p.get('name')=='Idempotency-Key' for p in params):
                params.append({'in':'header','name':'Idempotency-Key','required':True,'schema':{'type':'string','format':'uuid'},'description':'24-hour scoped transaction receipt. V2 compatibility writes also accept a missing key and then use version conflict checks.'})
            if writing and not operation.get('requestBody'):bodyless.add(identifier);operation['x-bodyless']=True
            for status in ('401','403','404','409','410','422','429','503'):
                operation['responses'][status]={'description':'Common API error','content':{'application/json':{'schema':{'$ref':'#/components/schemas/ErrorEnvelope'}}}}
            if raw['operationId'] in {'downloadPrivateFile','getImportTemplate','getResourceImportErrors','exportResourceCsv'}:
                mime='application/octet-stream' if raw['operationId']=='downloadPrivateFile' else 'text/csv'
                operation['responses']['200']={'description':'Authorized file response','content':{mime:{'schema':{'type':'string','format':'binary'}}}};binary_ids.add(identifier)
            if secret:
                for code,response in operation['responses'].items():
                    if code.startswith('2'):response.setdefault('headers',{})['Cache-Control']={'schema':{'type':'string','const':'no-store'},'description':'Sensitive operation responses are never cached'}
            contract['paths'].setdefault(relative,{})[method]=operation;count+=1
    schemas={k:v for k,v in schemas.items() if not k.startswith('Stage2')};schemas.update(copied)
    schemas['Stage2BasicSubscriptionSummary']=deepcopy(source['BasicSubscriptionSummary'])
    contract['components']['schemas']=schemas
    tags={t['name'] for t in contract['tags']}
    for item in runtime['paths'].values():
        for op in item.values():
            for tag in op.get('tags',[]):
                if tag not in tags:contract['tags'].append({'name':tag});tags.add(tag)
    contract['x-stage2-secret-operations']=sorted(secret_ids);contract['x-stage2-bodyless-operations']=sorted(bodyless);contract['x-stage2-file-operations']=sorted(binary_ids)
    path.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Merged {count} implemented business operations with closed nine-type resource DTOs.')

if __name__=='__main__':main()
