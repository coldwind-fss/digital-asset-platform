import { ref, onBeforeUnmount } from 'vue';
import { onBeforeRouteLeave, type Router, type RouteLocationRaw } from 'vue-router';
let savedNavigation=false;
export async function goSaved(router:Router,to:RouteLocationRaw){savedNavigation=true;try{return await router.push(to);}finally{savedNavigation=false;}}
import { api, ApiClientError, request } from '../../shared/api/client';
import { authSession } from '../identity/session';
import type { components } from '../../shared/api/generated';
export type DTO<K extends keyof components['schemas']> = components['schemas'][K];
export type Page<T> = { items:T[]; pagination:{page:number;page_size:number;total:number;has_next:boolean} };
export type Option = {value:string;label:string};
export const types: Record<string,string> = { platform_account:'平台账号',mailbox_account:'邮箱账号',api_key:'API 密钥',service_subscription:'订阅服务',business_space:'业务空间',application:'应用系统',api_service:'API 服务',cloud_resource:'云资源',domain:'域名' };
export const labels: Record<string,string> = { ...types,company:'公司主体',identity:'注册身份',platform:'平台',person:'人员',resource:'资源',owner:'负责人',maintainer:'维护人',use:'使用人',controller:'控制人',unknown:'待了解',in_use:'使用中',disabled:'已停用',retired:'已退役',active:'有效',inactive:'停用',needs_review:'待复查',open:'待处理',resolved:'已解决',replaced:'已替换',draft:'草稿',verified:'已核实',unverified:'待核实',confirmed:'已确认',proposed:'待确认',rejected:'已否决',pending:'待执行',in_progress:'执行中',awaiting_confirmation:'待复核',completed:'已完成',completed_with_exceptions:'带例外关闭',cancelled:'已取消',failed:'失败',cancellation_requested:'待确认取消',not_saved:'未保存',saved:'已保存',revoked:'已撤销',superseded:'已替换',change:'变更',transfer:'交接',offboard:'离职回收',restricted:'指定范围',department:'部门',normal:'普通',uses:'使用',managed_by:'受其管理',part_of:'属于',contains:'包含',depends_on:'依赖',registration:'注册',login:'登录',recovery:'找回',mfa:'多因素认证',not_applicable:'不适用',verified_absent:'核实后无此关系',password:'密码',api_token:'API Token',certificate_pin:'证书 PIN',other:'其他',view:'查看',rotate:'轮换',replace:'替换',revoke:'撤销凭据',revoke_grant:'撤销授权',entry:'访问入口',note:'说明',attachment:'附件',month:'月',year:'年',custom:'自定义',actual:'实际支出',budget:'预算',voided:'已作废',available:'可下载',ended:'已结束',succeeded:'成功',running:'运行中',queued:'排队中',stale:'已过期',due:'待到期',overdue:'已到期',member:'成员',resource_manager:'资源管理员',admin:'系统管理员',phone:'手机号',email:'邮箱',third_party:'第三方身份',personal:'个人',shared:'共享',dedicated:'专用',department_shared:'部门共享',company_shared:'公司共享',otp:'验证码',qr:'扫码',sso:'单点登录',master:'主账号',administrator:'管理员',service:'服务账号',change_owner:'调整负责人',change_organization:'调整归属',change_visibility:'调整可见范围',grant_use:'授予使用',remove_use:'收回使用',transfer_controller:'交接控制权',change_binding:'变更身份绑定',change_mailbox_address:'变更邮箱地址',change_management_relation:'变更管理关系',rotate_credential:'轮换凭据',revoke_credential:'撤销凭据',revoke_credential_grant:'撤销凭据授权',replace_key:'替换 API 密钥',disable_resource:'停用资源',retire_resource:'退役资源',reactivate_resource:'恢复使用',start:'开始执行','record-execution':'记录实际执行',confirm:'独立复核','return-for-rework':'退回重做','request-cancellation':'申请取消','confirm-cancellation':'独立确认取消',edit:'修订',submit:'提交事项',close:'关闭流程','add-item':'添加事项',deepseek:'DeepSeek',account_balance:'账号余额',new:'新建',committed:'已导入',ready:'可导入',error:'错误',duplicate_candidate:'可能重复',preview:'已预览',created:'已创建',previewed:'已预览',expired:'已过期' };
export const text = (v:unknown):string => v===null||v===undefined||v===''?'—':typeof v==='boolean'?(v?'是':'否'):Array.isArray(v)?v.map(text).join('、'):typeof v==='object'?Object.entries(v).map(([k,x])=>`${labels[k]??k}：${text(x)}`).join('；'):labels[String(v)]??String(v);
export const date = (v?:string|null) => v ? /^\d{4}-\d{2}-\d{2}$/.test(v)?v:new Date(v).toLocaleString('zh-CN',{hour12:false}) : '—';
export const can = (cap:string) => Boolean(authSession.value?.capabilities.includes(cap));
export const opts = (values:string[]) => values.map(value=>({value,label:text(value)}));
export function relationEndpoint(relation:string){const allowed=relation==='managed_by'?['platform_account','mailbox_account']:relation==='part_of'?['business_space']:Object.keys(types).filter(t=>!['platform_account','mailbox_account'].includes(t));return '/resources?'+allowed.map(t=>'type_code='+t).join('&');}
export function errorText(e:unknown) {
  if (e instanceof ApiClientError) return `${e.message}${e.details?.length?' · '+e.details.map(d=>`${d.field}: ${d.message}`).join('；'):''}${e.status===409?'。输入已保留，请先刷新核对最新事实再提交。':''}${e.requestId?'（请求 '+e.requestId+'）':''}`;
  return e instanceof Error ? e.message : '操作失败，请重试';
}
export function useTask() {
  const busy=ref(false),error=ref(''),notice=ref('');
  let running=0;
  async function run<T>(fn:()=>Promise<T>) { running++;busy.value=true;error.value='';notice.value='';try{return await fn();}catch(e){if(!(e instanceof DOMException&&e.name==='AbortError'))error.value=errorText(e);}finally{running--;busy.value=running>0;} }
  return {busy,error,notice,run};
}
// Receipts retain only a SHA-256 fingerprint and key in memory, never the body.
const receipts=new Map<string,string>();
export async function mutate<T>(path:string,body:unknown=undefined,method:'POST'|'PATCH'='POST'):Promise<T> {
  const secret=/credentials|secret-stages|contact-identities|\/auth\/|\/admin\//.test(path);
  let fingerprint='';let key:string=crypto.randomUUID();
  if(!secret) { const bytes=new TextEncoder().encode(method+path+JSON.stringify(body));fingerprint=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(n=>n.toString(16).padStart(2,'0')).join('');key=receipts.get(fingerprint)??key;receipts.set(fingerprint,key);if(receipts.size>100)receipts.delete(receipts.keys().next().value!); }
  try { const data=await request<T>(path,{method,body,headers:{'Idempotency-Key':key}});if(fingerprint)receipts.delete(fingerprint);return data; }
  catch(e) { if(e instanceof ApiClientError && e.status>=400 && e.status<500 && fingerprint)receipts.delete(fingerprint);throw e; }
}
export function useDirty(dirty:()=>boolean,busy:()=>boolean=()=>false) {
  const guard=(event:BeforeUnloadEvent)=>{if(dirty()||busy()){event.preventDefault();event.returnValue='';}};
  window.addEventListener('beforeunload',guard);
  onBeforeUnmount(()=>window.removeEventListener('beforeunload',guard));
  onBeforeRouteLeave(()=>savedNavigation||(!busy()&&(!dirty()||window.confirm('尚有未保存的输入，确认离开并丢弃？'))));
}
export const query = (values:Record<string,unknown>) => '?'+new URLSearchParams(Object.entries(values).filter(([,v])=>v!==''&&v!==undefined&&v!==null).map(([k,v])=>[k,String(v)])).toString();
export { api };

export const copyText=(value:string)=>navigator.clipboard.writeText(value);
export const changedEvent=()=>window.dispatchEvent(new Event('v3:changed'));
export const newKey=()=>crypto.randomUUID();
