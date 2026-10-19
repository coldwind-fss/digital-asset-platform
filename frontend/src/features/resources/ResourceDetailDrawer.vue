<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { CircleAlert, FileText, LoaderCircle, Pencil, X } from "lucide-vue-next";
import type { components } from "../../shared/api/generated";

type Schemas = components["schemas"];
type ResourceType = Schemas["ResourceType"];
type ResourceView = Schemas["ResourceView"];
type MaterialView = Schemas["MaterialView"];

const props = defineProps<{
  resource: ResourceView | null;
  loading: boolean;
  error: string;
  materials: MaterialView[];
  materialError: string;
  materialSaving: boolean;
  typeLabels: Record<ResourceType, string>;
  lifecycleLabels: Record<Schemas["Lifecycle"], string>;
  verificationLabels: Record<Schemas["Verification"], string>;
  statusClass: (value: string) => string;
}>();

const panel = ref<HTMLElement | null>(null);
let returnTarget: HTMLElement | null = null;
const focusableSelector = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== "Tab") return;
  const focusable = Array.from(panel.value?.querySelectorAll<HTMLElement>(focusableSelector) ?? []);
  if (!focusable.length) {
    event.preventDefault();
    panel.value?.focus();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

watch(
  () => Boolean(props.resource || props.loading),
  async (open) => {
    if (open) {
      returnTarget = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      await nextTick();
      panel.value?.querySelector<HTMLElement>(focusableSelector)?.focus();
      return;
    }
    await nextTick();
    returnTarget?.focus();
    returnTarget = null;
  },
);

const materialDraft = defineModel<string>("materialDraft", { required: true });

const emit = defineEmits<{
  close: [];
  edit: [];
  addMaterial: [];
}>();
</script>

<template>
  <div v-if="resource || loading" class="fixed inset-0 z-50 flex justify-end bg-slate-950/30" role="presentation" @click.self="emit('close')">
    <aside ref="panel" class="flex h-full w-full max-w-xl min-w-0 flex-col overflow-hidden bg-white shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="resource-detail-title" tabindex="-1" @keydown="handleKeydown" @keydown.esc.stop="emit('close')">
      <header class="flex shrink-0 items-start justify-between gap-4 border-b border-gray-100 px-5 py-5">
        <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-500"><LoaderCircle class="h-4 w-4 animate-spin" /> 正在读取资源详情…</div>
        <div v-else-if="resource"><p class="font-mono text-[11px] text-accent-600">{{ resource.code }}</p><h2 id="resource-detail-title" class="mt-1 text-xl font-semibold text-gray-900">{{ resource.name }}</h2><p class="mt-1 text-xs text-gray-500">{{ typeLabels[resource.type_code] }} · 版本 {{ resource.version }}</p></div>
        <button class="btn-ghost !px-2" aria-label="关闭资源详情" type="button" @click="emit('close')"><X class="h-5 w-5" /></button>
      </header>
      <div v-if="error" class="m-5 admin-notice admin-notice-error" role="alert">{{ error }}</div>
      <div v-else-if="resource" class="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        <div v-if="resource.missing_fields.length" class="admin-notice admin-notice-warning mb-5 flex gap-2"><CircleAlert class="mt-0.5 h-4 w-4 shrink-0" /><span>待补充字段：{{ resource.missing_fields.join('、') }}。当前仍允许继续登记和维护。</span></div>
        <div class="mb-5 flex flex-wrap items-center gap-2"><span class="feishu-badge" :class="statusClass(resource.lifecycle)">{{ lifecycleLabels[resource.lifecycle] }}</span><span class="feishu-badge" :class="statusClass(resource.verification)">{{ verificationLabels[resource.verification] }}</span><span class="feishu-badge bg-violet-50 text-violet-700">凭据：{{ resource.credential_status === 'saved' ? '已受保护保存' : '未保存' }}</span></div>
        <section class="mb-6">
          <div class="mb-3 flex items-center justify-between"><h3 class="text-sm font-semibold text-gray-900">基本信息</h3><button class="btn-ghost !px-2.5 text-xs" :disabled="!resource.capabilities.edit" @click="emit('edit')"><Pencil class="h-3.5 w-3.5" /> 编辑</button></div>
          <dl class="grid grid-cols-2 gap-3"><div class="admin-info-card"><dt>平台 / 供应商</dt><dd>{{ resource.provider_name || '未设置' }}</dd></div><div class="admin-info-card"><dt>归属部门</dt><dd>{{ resource.owning_department?.display_name || '未设置' }}</dd></div><div class="admin-info-card"><dt>负责人</dt><dd>{{ resource.owner?.display_name || '待补充' }}</dd></div><div class="admin-info-card"><dt>使用方式</dt><dd>{{ resource.usage_mode || '未设置' }}</dd></div><div class="admin-info-card col-span-2"><dt>用途说明</dt><dd class="whitespace-pre-wrap">{{ resource.purpose || '暂无说明' }}</dd></div></dl>
        </section>
        <section class="mb-6"><h3 class="mb-3 text-sm font-semibold text-gray-900">普通属性</h3><div v-if="Object.keys(resource.attributes).length" class="grid gap-2"><div v-for="(value, key) in resource.attributes" :key="key" class="flex items-start justify-between gap-4 border-b border-gray-100 py-2 text-xs"><span class="text-gray-500">{{ key }}</span><span class="max-w-[65%] break-words text-right text-gray-800">{{ typeof value === 'object' ? JSON.stringify(value) : value }}</span></div></div><p v-else class="text-xs text-gray-400">暂无普通属性；秘密不会出现在这里。</p></section>
        <section><div class="mb-3 flex items-center justify-between"><h3 class="text-sm font-semibold text-gray-900">使用资料</h3><span class="text-[11px] text-gray-400">仅 URL / 非秘密说明</span></div><div v-if="materialError" class="admin-notice admin-notice-warning mb-3 text-xs">{{ materialError }}</div><div v-if="materials.length" class="mb-3 space-y-2"><article v-for="material in materials" :key="material.id" class="rounded-lg border border-gray-100 bg-gray-50 p-3"><div class="flex items-center gap-2"><FileText class="h-4 w-4 text-blue-600" /><strong class="text-xs text-gray-800">{{ material.title || '未命名资料' }}</strong><span class="ml-auto text-[10px] text-gray-400">{{ material.kind }}</span></div><p v-if="material.kind === 'note'" class="mt-2 whitespace-pre-wrap text-xs leading-5 text-gray-600">{{ material.body }}</p><a v-else-if="material.kind === 'entry'" class="mt-2 block truncate text-xs text-blue-600 underline" :href="material.url" target="_blank" rel="noreferrer">{{ material.url }}</a></article></div><form class="flex gap-2" @submit.prevent="emit('addMaterial')"><input v-model="materialDraft" class="admin-field min-w-0 flex-1 text-xs" placeholder="添加一条非秘密说明" /><button class="btn-secondary shrink-0 !px-3 text-xs" :disabled="materialSaving || !materialDraft.trim()">{{ materialSaving ? '保存中' : '添加' }}</button></form></section>
      </div>
    </aside>
  </div>
</template>
