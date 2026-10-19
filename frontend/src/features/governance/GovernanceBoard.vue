<script setup lang="ts">
import { ArrowRight, Check, CheckCircle2, ClipboardList, LoaderCircle, RefreshCw } from "lucide-vue-next";
import type { components } from "../../shared/api/generated";

type Schemas = components["schemas"];
type ChangeCaseView = Schemas["ChangeCaseView"];
type ChangeItemView = Schemas["ChangeItemView"];

const props = defineProps<{
  changeCases: ChangeCaseView[];
  changeItems: ChangeItemView[];
  selectedCase: ChangeCaseView | null;
  loading: boolean;
  actionLoading: boolean;
  stats: { draft: number; active: number; done: number; cancelled: number };
  caseLabels: Record<ChangeCaseView["case_type"], string>;
  itemLabels: Record<string, string>;
  statusClass: (value: string) => string;
  formatDate: (value: string | null | undefined) => string;
  resourceName: (resourceId: string) => string;
  actionLabel: (item: ChangeItemView) => string;
}>();

const emit = defineEmits<{
  refresh: [];
  select: [caseId: string];
  submit: [changeCase: ChangeCaseView];
  close: [changeCase: ChangeCaseView];
  advance: [item: ChangeItemView];
}>();
</script>

<template>
  <section class="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(340px,.8fr)]">
    <div class="space-y-4">
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div class="stat-card !p-4"><span class="text-xs text-gray-500">草稿</span><strong class="mt-2 block text-xl text-gray-900">{{ stats.draft }}</strong></div>
        <div class="stat-card !p-4"><span class="text-xs text-gray-500">执行中</span><strong class="mt-2 block text-xl text-blue-700">{{ stats.active }}</strong></div>
        <div class="stat-card !p-4"><span class="text-xs text-gray-500">已完成</span><strong class="mt-2 block text-xl text-emerald-700">{{ stats.done }}</strong></div>
        <div class="stat-card !p-4"><span class="text-xs text-gray-500">已取消</span><strong class="mt-2 block text-xl text-gray-500">{{ stats.cancelled }}</strong></div>
      </div>

      <section class="feishu-section">
        <div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
          <div><h3 class="text-sm font-semibold text-gray-900">变更单队列</h3><p class="mt-1 text-xs text-gray-500">确认完成前，当前业务事实保持不变。</p></div>
          <button class="btn-ghost" @click="emit('refresh')"><RefreshCw class="h-4 w-4" />刷新</button>
        </div>
        <div v-if="loading" class="flex items-center justify-center gap-2 px-5 py-16 text-sm text-gray-500"><LoaderCircle class="h-5 w-5 animate-spin" /> 正在读取治理事项…</div>
        <div v-else-if="changeCases.length === 0" class="flex flex-col items-center gap-2 px-5 py-16 text-center"><ClipboardList class="h-9 w-9 text-gray-300" /><strong class="text-sm text-gray-700">暂无变更单</strong><span class="text-xs text-gray-500">从右上角创建一项负责人交接，或等待服务端事项进入队列。</span></div>
        <div v-else class="divide-y divide-gray-100">
          <button v-for="changeCase in changeCases" :key="changeCase.id" class="flex w-full items-start gap-3 p-4 text-left transition hover:bg-gray-50" :class="selectedCase?.id === changeCase.id ? 'bg-blue-50/60' : ''" @click="emit('select', changeCase.id)">
            <span class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600"><ClipboardList class="h-4 w-4" /></span>
            <span class="min-w-0 flex-1"><span class="flex flex-wrap items-center gap-2"><strong class="text-sm font-medium text-gray-800">{{ caseLabels[changeCase.case_type] }}</strong><span class="feishu-badge" :class="statusClass(changeCase.status)">{{ changeCase.status }}</span></span><span class="mt-1 block text-xs text-gray-500">{{ changeCase.reason }}</span><span class="mt-2 block font-mono text-[10px] text-gray-400">{{ changeCase.id }} · {{ formatDate(changeCase.created_at) }}</span></span>
            <ArrowRight class="mt-1 h-4 w-4 shrink-0 text-gray-400" />
          </button>
        </div>
      </section>
    </div>

    <aside class="feishu-section h-fit">
      <div class="border-b border-gray-100 px-4 py-3"><h3 class="text-sm font-semibold text-gray-900">事项详情</h3><p v-if="selectedCase" class="mt-1 text-xs text-gray-500">{{ selectedCase.reason }}</p></div>
      <div v-if="!selectedCase" class="px-4 py-12 text-center text-sm text-gray-500">选择左侧变更单查看事项</div>
      <div v-else class="p-4">
        <div class="mb-4 grid gap-2 text-xs"><div class="flex justify-between gap-3"><span class="text-gray-500">状态</span><span class="feishu-badge" :class="statusClass(selectedCase.status)">{{ selectedCase.status }}</span></div><div class="flex justify-between gap-3"><span class="text-gray-500">创建时间</span><span class="text-gray-700">{{ formatDate(selectedCase.created_at) }}</span></div></div>
        <div v-if="selectedCase.status === 'draft'" class="mb-4"><button class="btn-primary w-full" :disabled="actionLoading" @click="emit('submit', selectedCase)"><Check class="h-4 w-4" /> 提交变更单</button></div>
        <div v-if="selectedCase.status === 'active' && changeItems.length > 0 && changeItems.every((item) => item.status === 'completed' || item.status === 'cancelled')" class="mb-4"><button class="btn-primary w-full" :disabled="actionLoading" @click="emit('close', selectedCase)"><CheckCircle2 class="h-4 w-4" /> 关闭变更单</button></div>
        <div v-if="changeItems.length === 0" class="rounded-lg bg-gray-50 p-4 text-center text-xs text-gray-500">该变更单暂无事项。</div>
        <div v-else class="space-y-3">
          <article v-for="item in changeItems" :key="item.id" class="rounded-lg border border-gray-200 p-3">
            <div class="flex items-start justify-between gap-2"><div><span class="text-[11px] text-gray-500">{{ itemLabels[item.action] || item.action }}</span><h4 class="mt-1 text-sm font-medium text-gray-800">{{ resourceName(item.resource_id) }}</h4></div><span class="feishu-badge" :class="statusClass(item.status)">{{ item.status }}</span></div>
            <p class="mt-2 text-xs leading-5 text-gray-500">负责人交接 proposal 已由服务端保存，当前版本 {{ item.version }}。</p>
            <button v-if="item.status !== 'completed' && item.status !== 'cancelled'" class="btn-secondary mt-3 w-full !py-1.5 text-xs" :disabled="actionLoading" @click="emit('advance', item)">{{ actionLabel(item) }} <ArrowRight class="h-3.5 w-3.5" /></button>
            <span v-else class="mt-3 flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 class="h-3.5 w-3.5" /> 已完成</span>
          </article>
        </div>
      </div>
    </aside>
  </section>
</template>
