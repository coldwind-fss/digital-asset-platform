<script setup lang="ts">
import {
  Archive,
  ArrowRight,
  Boxes,
  CircleAlert,
  ClipboardList,
  KeyRound,
  LayoutDashboard,
  LoaderCircle,
  Mail,
  PackageOpen,
  Search,
  Store,
  UsersRound,
} from "lucide-vue-next";
import type { Component } from "vue";
import type { components } from "../../shared/api/generated";

type Schemas = components["schemas"];
type ResourceType = Schemas["ResourceType"];
type ResourceSummary = Schemas["ResourceSummary"];

const props = defineProps<{
  resources: ResourceSummary[];
  resourceTotal: number;
  loading: boolean;
  stats: { total: number; inUse: number; review: number; pendingChanges: number };
  typeLabels: Record<ResourceType, string>;
  lifecycleLabels: Record<Schemas["Lifecycle"], string>;
  verificationLabels: Record<Schemas["Verification"], string>;
  statusClass: (value: string) => string;
}>();

const search = defineModel<string>("search", { required: true });
const typeFilter = defineModel<ResourceType | "">("typeFilter", { required: true });
const lifecycleFilter = defineModel<Schemas["Lifecycle"] | "">("lifecycleFilter", { required: true });

const emit = defineEmits<{
  submit: [];
  reset: [];
  open: [resource: ResourceSummary];
}>();

const iconByType: Record<ResourceType, Component> = {
  platform_account: UsersRound,
  mailbox_account: Mail,
  api_key: KeyRound,
  service_subscription: PackageOpen,
  business_space: Store,
  application: Boxes,
  api_service: Boxes,
  cloud_resource: Boxes,
  domain: Boxes,
};

function iconFor(type: ResourceType) {
  return iconByType[type];
}
</script>

<template>
  <section class="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
    <div class="stat-card"><div class="mb-4 flex items-center justify-between"><span class="rounded-lg bg-blue-50 p-2 text-blue-600"><Archive class="h-4 w-4" /></span><span class="text-[11px] text-gray-400">当前范围</span></div><strong class="block text-2xl font-semibold text-gray-900">{{ stats.total }}</strong><span class="mt-1 block text-xs text-gray-500">资源总数</span></div>
    <div class="stat-card"><div class="mb-4 flex items-center justify-between"><span class="rounded-lg bg-emerald-50 p-2 text-emerald-600"><LayoutDashboard class="h-4 w-4" /></span><span class="text-[11px] text-gray-400">生命周期</span></div><strong class="block text-2xl font-semibold text-gray-900">{{ stats.inUse }}</strong><span class="mt-1 block text-xs text-gray-500">当前在用</span></div>
    <div class="stat-card"><div class="mb-4 flex items-center justify-between"><span class="rounded-lg bg-amber-50 p-2 text-amber-600"><CircleAlert class="h-4 w-4" /></span><span class="text-[11px] text-gray-400">数据质量</span></div><strong class="block text-2xl font-semibold text-gray-900">{{ stats.review }}</strong><span class="mt-1 block text-xs text-gray-500">待补充 / 待核实</span></div>
    <div class="stat-card"><div class="mb-4 flex items-center justify-between"><span class="rounded-lg bg-violet-50 p-2 text-violet-600"><ClipboardList class="h-4 w-4" /></span><span class="text-[11px] text-gray-400">治理队列</span></div><strong class="block text-2xl font-semibold text-gray-900">{{ stats.pendingChanges }}</strong><span class="mt-1 block text-xs text-gray-500">待处理事项</span></div>
  </section>

  <section class="feishu-section">
    <form class="flex flex-wrap items-center gap-2 border-b border-gray-100 p-3" @submit.prevent="emit('submit')">
      <div class="relative min-w-[220px] flex-1"><Search class="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-gray-400" /><input v-model="search" class="feishu-input w-full pl-9" placeholder="搜索名称、编号、平台或用途" /></div>
      <select v-model="typeFilter" class="feishu-input min-w-[132px]"><option value="">全部类型</option><option v-for="(label, value) in typeLabels" :key="value" :value="value">{{ label }}</option></select>
      <select v-model="lifecycleFilter" class="feishu-input min-w-[120px]"><option value="">全部生命周期</option><option value="in_use">在用</option><option value="unknown">待确认</option><option value="disabled">已停用</option><option value="retired">已退役</option></select>
      <button type="submit" class="btn-secondary">查询</button><button type="button" class="btn-ghost" @click="emit('reset')">重置</button>
    </form>
    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 px-4 py-3 text-xs text-gray-500"><span>显示 <strong class="text-gray-800">{{ resources.length }}</strong> / {{ resourceTotal }} 项</span><span>服务端分页 · 只读状态来自 API</span></div>
    <div v-if="loading" class="flex items-center justify-center gap-2 px-5 py-16 text-sm text-gray-500"><LoaderCircle class="h-5 w-5 animate-spin" /> 正在读取服务端资源…</div>
    <div v-else-if="resources.length === 0" class="flex flex-col items-center justify-center gap-2 px-5 py-16 text-center"><PackageOpen class="h-9 w-9 text-gray-300" /><strong class="text-sm text-gray-700">暂无资源记录</strong><span class="text-xs text-gray-500">没有把演示数据伪装成真实数据；可检查权限、筛选或登记第一项资源。</span></div>
        <div v-else class="admin-table-scroll" tabindex="0" aria-label="资源台账，可横向滚动"><table class="feishu-table min-w-[880px]"><caption class="sr-only">资源台账列表</caption><thead><tr><th scope="col">资源实例</th><th scope="col">类型</th><th scope="col">平台 / 供应商</th><th scope="col">归属部门</th><th scope="col">负责人</th><th scope="col">生命周期</th><th scope="col">核实状态</th><th scope="col"></th></tr></thead><tbody><tr v-for="resource in resources" :key="resource.id" class="cursor-pointer" role="button" tabindex="0" :aria-label="'打开资源 ' + resource.name" @click="emit('open', resource)" @keydown.enter.prevent="emit('open', resource)" @keydown.space.prevent="emit('open', resource)"><td><div class="flex min-w-0 items-center gap-2.5"><span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600"><component :is="iconFor(resource.type_code)" class="h-4 w-4" /></span><div class="min-w-0"><strong class="block max-w-[260px] truncate text-sm font-medium text-gray-800" :title="resource.name">{{ resource.name }}</strong><span class="mt-0.5 block max-w-[280px] truncate font-mono text-[10px] text-gray-400">{{ resource.code }} · {{ resource.purpose || '暂无用途说明' }}</span></div></div></td><td><span class="text-xs text-gray-600">{{ typeLabels[resource.type_code] }}</span></td><td class="max-w-[160px] truncate text-gray-600">{{ resource.provider_name || '未设置' }}</td><td class="text-gray-600">{{ resource.owning_department?.display_name || '未设置' }}</td><td><span :class="resource.owner ? 'text-gray-700' : 'text-gray-400'">{{ resource.owner?.display_name || '待补充' }}</span></td><td><span class="feishu-badge" :class="statusClass(resource.lifecycle)">{{ lifecycleLabels[resource.lifecycle] }}</span></td><td><span class="feishu-badge" :class="statusClass(resource.verification)">{{ verificationLabels[resource.verification] }}</span></td><td><ArrowRight class="h-4 w-4 text-gray-400" /></td></tr></tbody></table></div>
  </section>
</template>
