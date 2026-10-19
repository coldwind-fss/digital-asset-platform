<script setup lang="ts">
import type { components } from "../../shared/api/generated";
import AdminDialog from "../../shared/ui/AdminDialog.vue";

type Schemas = components["schemas"];
type ResourceType = Schemas["ResourceType"];
type UsageMode = "normal" | "test" | "standby";

type ResourceDraft = {
  name: string;
  type_code?: ResourceType;
  provider_name: string;
  purpose: string;
  owning_department_id?: string;
  owner_person_id?: string;
  usage_mode: UsageMode;
};

defineProps<{
  open: boolean;
  mode: "create" | "edit";
  draft: ResourceDraft;
  typeLabels: Record<ResourceType, string>;
  departments: Schemas["DepartmentPickerOption"][];
  people: Schemas["PersonPickerOption"][];
  saving: boolean;
  error: string;
  version?: number;
}>();

const emit = defineEmits<{
  close: [];
  submit: [];
}>();
</script>

<template>
  <AdminDialog
    :open="open"
    :title="mode === 'create' ? '登记资源' : '编辑资源基础资料'"
    :description="mode === 'create' ? '保存普通业务属性；凭据需走独立受控操作。' : `提交时使用版本 ${version}，冲突后请刷新重试。`"
    :title-id="mode === 'create' ? 'create-title' : 'edit-title'"
    @close="emit('close')"
  >
    <form class="contents" @submit.prevent="emit('submit')">
      <div class="admin-dialog-body grid gap-4 sm:grid-cols-2">
        <label class="sm:col-span-2"><span class="admin-form-label">资源名称 <b>*</b></span><input v-model="draft.name" class="admin-field" required /></label>
        <label v-if="mode === 'create'"><span class="admin-form-label">资源类型 <b>*</b></span><select v-model="draft.type_code" class="admin-field" required><option v-for="(label, value) in typeLabels" :key="value" :value="value">{{ label }}</option></select></label>
        <label><span class="admin-form-label">使用方式</span><select v-model="draft.usage_mode" class="admin-field"><option value="normal">正常</option><option value="test">测试</option><option value="standby">备用</option></select></label>
        <label><span class="admin-form-label">平台 / 供应商</span><input v-model="draft.provider_name" class="admin-field" :placeholder="mode === 'create' ? '可暂不填写' : undefined" /></label>
        <label v-if="mode === 'create'"><span class="admin-form-label">归属部门</span><select v-model="draft.owning_department_id" class="admin-field"><option value="">未设置</option><option v-for="department in departments" :key="department.id" :value="department.id">{{ department.display_name }}</option></select></label>
        <label v-if="mode === 'create'"><span class="admin-form-label">负责人</span><select v-model="draft.owner_person_id" class="admin-field"><option value="">待补充</option><option v-for="person in people" :key="person.id" :value="person.id">{{ person.display_name }}</option></select></label>
        <label :class="mode === 'edit' ? 'sm:col-span-2' : ''"><span class="admin-form-label">用途说明</span><textarea v-if="mode === 'edit'" v-model="draft.purpose" class="admin-field min-h-24" rows="4"></textarea><input v-else v-model="draft.purpose" class="admin-field" placeholder="例如：团队统一使用" /></label>
        <div v-if="error" class="admin-notice admin-notice-error sm:col-span-2" role="alert">{{ error }}</div>
      </div>
      <footer class="admin-dialog-footer"><button class="btn-secondary" type="button" @click="emit('close')">取消</button><button class="btn-primary" type="submit" :disabled="saving">{{ saving ? (mode === 'create' ? '保存中…' : '保存中…') : (mode === 'create' ? '保存资源' : '保存修改') }}</button></footer>
    </form>
  </AdminDialog>
</template>
