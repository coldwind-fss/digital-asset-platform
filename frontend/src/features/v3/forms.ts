import { shallowRef } from 'vue';
import type { Field } from './TaskForm.vue';
import { mutate, type DTO } from './shared';
export type FormSpec={title:string;description?:string;fields:Field[];initial?:Record<string,string>;submitLabel?:string;onRefresh?:()=>Promise<string>;onSubmit:(v:Record<string,string>)=>Promise<void>};
export function useForm(){const form=shallowRef<FormSpec>();return {form,open:(spec:FormSpec)=>form.value=spec};}
export function catalogForm(kind:string,done:(row:DTO<'Stage2CatalogView'>)=>Promise<void>|void):FormSpec {
 const identity=kind==='identity';return { title:'登记'+({company:'公司主体',identity:'注册身份',platform:'平台'}[kind]??''),description:identity?'身份内容加密保存，登记完成后仅显示脱敏值。':'目录对象独立保存，不会自动生成账号或资源。',fields:identity?[
 {key:'kind',label:'身份类型',required:true,options:[{value:'phone',label:'手机号'},{value:'email',label:'邮箱'},{value:'third_party',label:'第三方身份'}],initial:'phone'},
 {key:'value',label:'身份内容',required:true,max:320,type:'password'}, {key:'label',label:'辨识名称'}, {key:'provider',label:'第三方身份提供方',hint:'第三方身份必填'},
 {key:'ownership',label:'身份归属',initial:'unknown',options:[{value:'unknown',label:'待了解'},{value:'company',label:'公司'},{value:'personal',label:'个人'}]}, {key:'company_id',label:'所属公司（可选）',endpoint:'/companies'},
 ]:[{key:'name',label:'名称',required:true},...(kind==='platform'?[{key:'website',label:'官方网站',type:'url'}]:[{key:'registration_identifier',label:'主体登记标识（可选）'},{key:'description',label:'说明',type:'textarea'}])],onSubmit:async v=>{
 const body=Object.fromEntries(Object.entries(v).filter(([,value])=>value!==''));const row=await mutate<DTO<'Stage2CatalogView'>>(identity?'/contact-identities':kind==='company'?'/companies':'/platforms',body);v.value='';await done(row);
 }};
}
