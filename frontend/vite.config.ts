import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ command, mode }) => {
  const prototypeOnly = command === "build" && mode === "prototype";
  const env = loadEnv(mode, process.cwd(), "VITE_");

  return {
    base: "/",
    plugins: [vue()],
    build: prototypeOnly ? { outDir: "../.codex_tmp/digital-asset-platform-prototype-dist" } : undefined,
    server: {
      proxy: {
        "/api": {
          target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8300",
          changeOrigin: false,
        },
      },
    },
  };
});
