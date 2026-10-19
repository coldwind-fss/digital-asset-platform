/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_API_PROXY_TARGET?: string;
  readonly VITE_SAMPLE_USERNAME?: string;
  readonly VITE_SAMPLE_PASSWORD?: string;
  readonly VITE_SAMPLE_REVIEWER_USERNAME?: string;
  readonly VITE_SAMPLE_REVIEWER_PASSWORD?: string;
  readonly VITE_TEST_SUBJECT?: string;
  readonly VITE_TEST_CAPABILITIES?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
