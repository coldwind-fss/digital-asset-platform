<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { Boxes, ShieldCheck } from "lucide-vue-next";
import App from "../../App.vue";
import AdminDialog from "../../shared/ui/AdminDialog.vue";
import { api, ApiClientError, testIdentityConfigured } from "../../shared/api/client";
import type { components } from "../../shared/api/generated";
import { acceptSession, accountSettingsOpen, authSession, sessionNotice, type LocalSession } from "./session";

type BootstrapStatus = components["schemas"]["IdentityBootstrapStatus"];
const loading = ref(true), busy = ref(false), error = ref(""), success = ref("");
const bootstrap = ref<BootstrapStatus | null>(null);
const activation = ref(false);
// These optional build values are deliberately public sample login details.
// Real owner credentials must never be supplied through VITE_* variables.
const sampleAccount = { username: import.meta.env.VITE_SAMPLE_USERNAME?.trim() ?? "", password: import.meta.env.VITE_SAMPLE_PASSWORD ?? "" };
const sampleLogin = Boolean(sampleAccount.username && sampleAccount.password);
const sampleReviewer = { username: import.meta.env.VITE_SAMPLE_REVIEWER_USERNAME?.trim() ?? "", password: import.meta.env.VITE_SAMPLE_REVIEWER_PASSWORD ?? "" };
const form = reactive({ username: "", display_name: "", password: "", bootstrap_token: "", action_token: "" });
const security = reactive({ current: "", replacement: "" });
const setup = computed(() => bootstrap.value?.setup_available && !activation.value);
const title = computed(() => activation.value ? "激活或恢复账号" : setup.value ? "初始化管理员" : "登录工作区");
function fillSample() { if (sampleLogin && bootstrap.value?.initialized && !activation.value) Object.assign(form, sampleAccount); }
watch(authSession, (current, previous) => { if (!current && previous) fillSample(); });
function message(value: unknown) { return value instanceof ApiClientError ? value.message : "请求失败，请检查服务后重试"; }
async function initialize() {
  error.value = "";
  try {
    bootstrap.value = await api.get<BootstrapStatus>("/auth/bootstrap-status");
    fillSample();
    if (bootstrap.value.initialized) {
      try {
        const current = await api.get<LocalSession>("/auth/session");
        acceptSession(sampleLogin && current.must_change_password ? null : current);
      }
      catch (e) { if (!(e instanceof ApiClientError && e.status === 401)) throw e; }
    }
    // Retire old guest links without changing the standard login flow.
    const url = new URL(window.location.href);
    if (url.searchParams.get("guest") === "1") {
      url.searchParams.delete("guest");
      window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
    }
  } catch (e) { error.value = message(e); }
  finally { loading.value = false; }
}
onMounted(() => { if (testIdentityConfigured) loading.value = false; else void initialize(); });
async function submit() {
  if (busy.value) return;
  busy.value = true; error.value = ""; success.value = ""; sessionNotice.value = "";
  try {
    if (activation.value) {
      await api.post("/auth/activate", { action_token: form.action_token, new_password: form.password });
      activation.value = false; success.value = "密码已设置，请使用账号登录。";
    } else {
      const payload = setup.value ? { username: form.username, display_name: form.display_name, password: form.password, bootstrap_token: form.bootstrap_token } : { username: form.username, password: form.password };
      const session = await api.post<LocalSession>(setup.value ? "/auth/bootstrap" : "/auth/login", payload);
      acceptSession(session);
      if (bootstrap.value) { bootstrap.value.initialized = true; bootstrap.value.setup_available = false; }
    }
  } catch (e) { error.value = message(e); }
  finally { busy.value = false; form.password = sampleLogin && form.username === sampleAccount.username ? sampleAccount.password : ""; form.bootstrap_token = ""; form.action_token = ""; }
}
async function verifyOrChange(change: boolean) {
  if (busy.value) return;
  busy.value = true; error.value = ""; success.value = "";
  try {
    if (change) {
      await api.post("/auth/change-password", { current_password: security.current, new_password: security.replacement });
      acceptSession(null); sessionNotice.value = "密码已修改，请重新登录。";
    } else {
      await api.post("/auth/reauthenticate", { password: security.current });
      success.value = "身份已重新验证。";
    }
  } catch (e) { error.value = message(e); }
  finally { busy.value = false; security.current = ""; security.replacement = ""; }
}
</script>

<template>
  <div v-if="loading" class="flex min-h-screen items-center justify-center text-sm text-gray-500" role="status">正在连接工作区…</div>
  <template v-else-if="testIdentityConfigured || (authSession && !authSession.must_change_password)">
    <App />
  </template>
  <main v-else class="flex min-h-screen items-center justify-center bg-gray-50 p-4">
    <section class="w-full max-w-sm overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm" aria-labelledby="login-title">
      <header class="flex items-center gap-3 bg-primary-900 px-6 py-5 text-white"><Boxes class="h-7 w-7 shrink-0" /><div><p class="text-sm font-semibold">数字资产管理中台</p><p class="mt-0.5 text-[10px] text-primary-300">DIGITAL ASSET PLATFORM</p></div></header>
      <div class="p-6">
        <h1 id="login-title" class="text-lg font-semibold">{{ authSession?.must_change_password ? '请修改初始密码' : title }}</h1>
        <p class="mb-5 mt-1 text-xs leading-5 text-gray-500">{{ setup ? '使用本机初始化口令创建首个管理员。' : sampleLogin && !activation ? '示例账号密码已填好，登录即可使用完整产品功能。' : '使用管理员分配的账号进入工作区。' }}</p>
        <p v-if="sessionNotice" class="admin-notice admin-notice-info mb-4" role="status">{{ sessionNotice }}</p>
        <p v-if="error" class="admin-notice admin-notice-error mb-4" role="alert">{{ error }}</p>
        <p v-if="success" class="admin-notice admin-notice-success mb-4" role="status">{{ success }}</p>
        <form v-if="!authSession?.must_change_password" class="space-y-4" @submit.prevent="submit">
          <template v-if="!activation">
            <label class="block"><span class="admin-form-label">账号</span><input v-model="form.username" class="admin-field" name="username" autocomplete="username" required minlength="3" maxlength="64" spellcheck="false" /></label>
            <label v-if="setup" class="block"><span class="admin-form-label">显示名称</span><input v-model="form.display_name" class="admin-field" required maxlength="200" autocomplete="name" /></label>
          </template>
          <label v-else class="block"><span class="admin-form-label">一次性激活 / 恢复口令</span><input v-model="form.action_token" class="admin-field" type="password" autocomplete="off" required /></label>
          <label class="block"><span class="admin-form-label">{{ activation || setup ? '设置密码（至少 12 位）' : '密码' }}</span><input v-model="form.password" class="admin-field" type="password" :autocomplete="activation || setup ? 'new-password' : 'current-password'" required :minlength="activation || setup ? 12 : 1" maxlength="256" /></label>
          <div v-if="sampleLogin && !setup && !activation" class="rounded-md bg-gray-50 px-3 py-2 text-xs leading-5 text-gray-600"><p>示例账号：<span class="font-medium">{{ sampleAccount.username }}</span><br />密码：<span class="break-all font-medium">{{ sampleAccount.password }}</span></p><details v-if="sampleReviewer.username && sampleReviewer.password" class="mt-2"><summary class="cursor-pointer">流程独立复核账号</summary><p class="mt-1">需要另一人确认时，退出后使用 {{ sampleReviewer.username }} / <span class="break-all">{{ sampleReviewer.password }}</span> 登录。执行与复核按原业务规则分开。</p></details></div>
          <label v-if="setup" class="block"><span class="admin-form-label">本机初始化口令</span><input v-model="form.bootstrap_token" class="admin-field" type="password" autocomplete="off" required minlength="32" /></label>
          <button class="btn-primary w-full" type="submit" :disabled="busy || !bootstrap">{{ busy ? '正在登录…' : title }}</button>
          <button v-if="bootstrap?.initialized && !bootstrap.read_only" class="btn-ghost w-full text-xs" type="button" :disabled="busy" @click="activation = !activation; error = ''; success = ''">{{ activation ? '返回登录' : '激活账号 / 使用恢复口令' }}</button>
          <button v-if="!bootstrap" class="btn-secondary w-full" type="button" @click="initialize">重新连接</button>
        </form>
        <form v-else class="space-y-4" @submit.prevent="verifyOrChange(true)">
          <label class="block"><span class="admin-form-label">当前密码</span><input v-model="security.current" class="admin-field" type="password" autocomplete="current-password" required /></label>
          <label class="block"><span class="admin-form-label">新密码（至少 12 位）</span><input v-model="security.replacement" class="admin-field" type="password" autocomplete="new-password" required minlength="12" maxlength="256" /></label>
          <button class="btn-primary w-full" :disabled="busy">修改密码</button>
        </form>
      </div>
      <footer class="flex items-center gap-2 border-t border-gray-100 px-6 py-3 text-[11px] text-gray-500"><ShieldCheck class="h-3.5 w-3.5" />{{ sampleLogin ? '示例数据 · 登记、维护与治理功能完整可用' : '账号由团队管理员管理' }}</footer>
    </section>
  </main>
  <AdminDialog :open="accountSettingsOpen && Boolean(authSession)" title="账号安全" title-id="account-security-title" @close="accountSettingsOpen = false; error = ''; success = ''; security.current = ''; security.replacement = ''">
    <div class="admin-dialog-body">
    <p class="mb-4 text-sm text-gray-600">{{ authSession?.display_name }} · {{ authSession?.username }}</p>
    <p v-if="error" class="admin-notice admin-notice-error mb-4" role="alert">{{ error }}</p>
    <p v-if="success" class="admin-notice admin-notice-success mb-4" role="status">{{ success }}</p>
    <p v-if="authSession?.read_only" class="admin-notice admin-notice-info">只读体验账号不支持改密或查看凭据。</p><form v-else class="space-y-4" @submit.prevent="verifyOrChange(true)">
      <label class="block"><span class="admin-form-label">当前密码</span><input v-model="security.current" class="admin-field" type="password" autocomplete="current-password" required maxlength="256" /></label>
      <button class="btn-secondary" type="button" :disabled="busy || !security.current" @click="verifyOrChange(false)">重新验证身份</button>
      <label class="block"><span class="admin-form-label">新密码（至少 12 位）</span><input v-model="security.replacement" class="admin-field" type="password" autocomplete="new-password" required minlength="12" maxlength="256" /></label>
      <button class="btn-primary" :disabled="busy">修改密码并重新登录</button>
    </form>
    </div>
  </AdminDialog>
</template>
