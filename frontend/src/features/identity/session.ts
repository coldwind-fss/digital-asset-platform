import { shallowRef, ref } from "vue";
import { api, onSessionExpired, setSessionCsrfToken } from "../../shared/api/client";
import type { components } from "../../shared/api/generated";

export type LocalSession = components["schemas"]["IdentitySessionView"];
export const authSession = shallowRef<LocalSession | null>(null);
export const accountSettingsOpen = ref(false);
export const sessionNotice = ref("");
export function acceptSession(session: LocalSession | null) {
  authSession.value = session;
  setSessionCsrfToken(session?.csrf_token ?? null);
  if (!session) accountSettingsOpen.value = false;
}
onSessionExpired(() => {
  acceptSession(null);
  sessionNotice.value = "会话已失效，请重新登录。";
});
export async function signOut() {
  await api.post("/auth/logout", undefined);
  acceptSession(null);
  sessionNotice.value = "已退出登录。";
}
