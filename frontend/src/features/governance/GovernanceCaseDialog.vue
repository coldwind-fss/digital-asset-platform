<script setup lang="ts">
import type { components } from "../../shared/api/generated";
import AdminDialog from "../../shared/ui/AdminDialog.vue";

type Schemas = components["schemas"];
type ResourceSummary = Schemas["ResourceSummary"];
type GovernanceDraft = {
  case_type: Schemas["ChangeCaseView"]["case_type"];
  reason: string;
  coordinator_person_id: string;
  subject_person_id: string;
  resource_id: string;
  target_person_id: string;
};

defineProps<{
  open: boolean;
  draft: GovernanceDraft;
  resources: ResourceSummary[];
  people: Schemas["PersonPickerOption"][];
  saving: boolean;
  error: string;
}>();

const emit = defineEmits<{
  close: [];
  submit: [];
}>();
</script>

<template>
  <AdminDialog :open="open" title="新建负责人交接" description="系统会先创建草稿事项，提交和确认分别推进。" title-id="governance-title" @close="emit('close')">
    <form class="contents" @submit.prevent="emit('submit')">
      <div class="admin-dialog-body grid gap-4 sm:grid-cols-2">
        <label><span class="admin-form-label">变更类型</span><select v-model="draft.case_type" class="admin-field"><option value="transfer">负责人交接</option><option value="change">业务变更</option><option value="offboard">离职下线</option></select></label>
        <label><span class="admin-form-label">资源 <b>*</b></span><select v-model="draft.resource_id" class="admin-field" required><option value="">请选择资源</option><option v-for="resource in resources" :key="resource.id" :value="resource.id">{{ resource.name }}</option></select></label>
        <label><span class="admin-form-label">协调人 <b>*</b></span><select v-model="draft.coordinator_person_id" class="admin-field" required><option value="">请选择人员</option><option v-for="person in people" :key="person.id" :value="person.id">{{ person.display_name }}</option></select></label>
        <label><span class="admin-form-label">目标负责人 <b>*</b></span><select v-model="draft.target_person_id" class="admin-field" required><option value="">请选择人员</option><option v-for="person in people" :key="person.id" :value="person.id">{{ person.display_name }}</option></select></label>
        <label class="sm:col-span-2"><span class="admin-form-label">变更原因 <b>*</b></span><textarea v-model="draft.reason" class="admin-field min-h-24" rows="4" required></textarea></label>
        <div v-if="error" class="admin-notice admin-notice-error sm:col-span-2" role="alert">{{ error }}</div>
      </div>
      <footer class="admin-dialog-footer"><button class="btn-secondary" type="button" @click="emit('close')">取消</button><button class="btn-primary" type="submit" :disabled="saving">{{ saving ? '创建中…' : '创建草稿' }}</button></footer>
    </form>
  </AdminDialog>
</template>
