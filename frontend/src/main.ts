import { createApp } from "vue";
import IdentityGate from "./features/identity/IdentityGate.vue";
import { router } from "./router";
import "./styles/admin-ui.css";

createApp(IdentityGate).use(router).mount("#app");
