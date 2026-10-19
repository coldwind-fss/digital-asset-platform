<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue';
import { api, query, errorText, type Page, type Option } from './shared';
const props=defineProps<{modelValue:string;endpoint:string;label:string;selectedLabel?:string;required?:boolean;excludeId?:string;clearOnEndpointChange?:boolean}>();
const emit=defineEmits<{'update:modelValue':[value:string]}>();
const rows=ref<Option[]>([]),q=ref(''),page=ref(1),more=ref(false),busy=ref(false),error=ref('');
let abort:AbortController|undefined;let timer:ReturnType<typeof setTimeout>;
async function load(append=false) {
 abort?.abort();if(!props.endpoint){rows.value=[];return;}const current=new AbortController();abort=current;busy.value=true;error.value='';
 try { const data=await api.get<Page<Record<string,unknown>>>(props.endpoint+(props.endpoint.includes('?')?'&':'?')+query({q:q.value,page:page.value,page_size:100}).slice(1),current.signal);const next=data.items.filter(r=>r.id!==props.excludeId).map(r=>({value:String(r.id),label:String(r.name??r.display_name??r.label??r.masked_value??(r.kind?`${r.kind} · ${r.status} · ${String(r.id).slice(0,8)}`:r.id))})); rows.value=append?[...rows.value,...next]:next;more.value=data.pagination.has_next; }
 catch(e){if(!current.signal.aborted)error.value=errorText(e);}finally{if(abort===current)busy.value=false;}
}
watch(()=>props.endpoint,(value,previous)=>{if(props.clearOnEndpointChange&&previous&&value!==previous)emit('update:modelValue','');page.value=1;q.value='';void load();},{immediate:true});
watch(q,()=>{clearTimeout(timer);timer=setTimeout(()=>{page.value=1;void load();},250);});
onBeforeUnmount(()=>{abort?.abort();clearTimeout(timer);});
</script>
<template><div class="space-y-1"><input v-model="q" class="admin-field !py-1 text-xs" :aria-label="'搜索'+label" placeholder="搜索候选对象" maxlength="100"><select class="admin-field" :aria-label="label" :required="required" :value="modelValue" @change="emit('update:modelValue',($event.target as HTMLSelectElement).value)"><option value="">暂不选择</option><option v-if="modelValue&&!rows.some(r=>r.value===modelValue)" :value="modelValue">{{selectedLabel??('已选对象 · '+modelValue.slice(0,8))}}</option><option v-for="row in rows" :key="row.value" :value="row.value">{{ row.label }}</option></select><span v-if="busy" class="text-xs text-gray-500" role="status">加载候选…</span><p v-if="error" class="text-xs text-rose-600" role="alert">{{error}} <button type="button" @click="load()">重试</button></p><button v-if="more" type="button" class="text-xs text-accent-600" @click="page++;load(true)">加载更多候选</button></div></template>
