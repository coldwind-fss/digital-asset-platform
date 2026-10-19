<script setup lang="ts">
import { nextTick, ref, watch, onBeforeUnmount } from "vue";
import { X } from "lucide-vue-next";

const props = defineProps<{
  open: boolean;
  title: string;
  description?: string;
  titleId: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

const dialog = ref<HTMLDivElement | null>(null);
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
  const focusable = Array.from(dialog.value?.querySelectorAll<HTMLElement>(focusableSelector) ?? []).filter(el=>el.getClientRects().length>0);
  if (!focusable.length) {
    event.preventDefault();
    dialog.value?.focus();
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
  () => props.open,
  async (open) => {
    if (open) {
      returnTarget = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      await nextTick();
      const firstField = dialog.value?.querySelector<HTMLElement>(focusableSelector);
      (firstField ?? dialog.value)?.focus();
      return;
    }
    await nextTick();
    if(returnTarget?.isConnected)returnTarget.focus();
    returnTarget = null;
  },
  {immediate:true},
);
onBeforeUnmount(()=>{if(returnTarget?.isConnected)returnTarget.focus();});
</script>

<template>
  <Teleport to="body"><div v-if="open" class="admin-dialog-backdrop" @click.self="emit('close')">
    <div ref="dialog" class="admin-dialog-card" role="dialog" aria-modal="true" :aria-labelledby="titleId" tabindex="-1" @keydown="handleKeydown" @keydown.esc.stop="emit('close')">
      <header class="admin-dialog-header">
        <div><h2 :id="titleId" class="text-lg font-semibold text-gray-900">{{ title }}</h2><p v-if="description" class="mt-1 text-xs text-gray-500">{{ description }}</p></div>
        <button class="btn-ghost !px-2" aria-label="关闭窗口" type="button" @click="emit('close')"><X class="h-5 w-5" /></button>
      </header>
      <slot />
    </div>
  </div></Teleport>
</template>
