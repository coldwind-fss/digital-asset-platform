import type { components } from "./generated";

type ErrorBody = components["schemas"]["ApiError"];
type ErrorEnvelope = components["schemas"]["ErrorEnvelope"];

export class ApiClientError extends Error {
  readonly code: string;
  readonly requestId?: string;
  readonly retryable: boolean;
  readonly details: ErrorBody["details"];
  readonly status: number;

  constructor(status: number, error: ErrorBody, requestId?: string) {
    super(error.message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = error.code;
    this.requestId = requestId;
    this.retryable = error.retryable;
    this.details = error.details;
  }
}

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

const configuredBase = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const apiBase = configuredBase.replace(/\/+$/, "");
const testSubject = import.meta.env.VITE_TEST_SUBJECT?.trim();
const testCapabilities = import.meta.env.VITE_TEST_CAPABILITIES?.trim();
let sessionCsrfToken: string | null = null;
let sessionExpiredHandler: (() => void) | undefined;
export function setSessionCsrfToken(value: string | null) { sessionCsrfToken = value; }
export function onSessionExpired(handler: () => void) { sessionExpiredHandler = handler; }

function errorEnvelope(value: unknown): ErrorEnvelope | null {
  if (typeof value !== "object" || value === null || !("error" in value)) return null;
  const candidate = value as Partial<ErrorEnvelope>;
  if (candidate.data !== null || !candidate.error || !candidate.meta) return null;
  return candidate as ErrorEnvelope;
}

function networkFailure(responseStatus?: number, requestId?: string): ApiClientError {
  const unavailable = [502, 503, 504].includes(responseStatus ?? -1);
  const oversized = responseStatus === 413;
  return new ApiClientError(
    responseStatus ?? 0,
    {
      code: unavailable
        ? "UPSTREAM_UNAVAILABLE"
        : oversized
          ? "PAYLOAD_TOO_LARGE"
          : responseStatus === undefined
            ? "NETWORK_ERROR"
            : "INVALID_API_RESPONSE",
      message: unavailable
        ? "服务暂不可用，请稍后重试"
        : oversized
          ? "请求内容过大"
          : responseStatus === undefined
            ? "无法连接服务，请检查网络后重试"
            : "服务响应格式不符合约定",
      details: [],
      retryable: unavailable || responseStatus === undefined,
    },
    requestId,
  );
}

export async function request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (sessionCsrfToken && !["GET", "HEAD", "OPTIONS"].includes((options.method ?? "GET").toUpperCase())) {
    headers.set("X-CSRF-Token", sessionCsrfToken);
  }
  if (testSubject && testCapabilities) {
    headers.set("X-DAP-Test-Subject", testSubject);
    headers.set("X-DAP-Test-Capabilities", testCapabilities);
  }

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    if (
      options.body instanceof FormData ||
      options.body instanceof Blob ||
      typeof options.body === "string"
    ) {
      body = options.body;
    } else {
      headers.set("Content-Type", "application/json; charset=utf-8");
      body = JSON.stringify(options.body);
    }
  }

  let response: Response;
  try {
    response = await fetch(`${apiBase}${path.startsWith("/") ? path : `/${path}`}`, {
      ...options,
      headers,
      body,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw networkFailure();
  }

  const requestId = response.headers.get("X-Request-ID") ?? undefined;
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw networkFailure(response.status, requestId);
  }

  if (!response.ok) {
    if (response.status === 401 && sessionCsrfToken) sessionExpiredHandler?.();
    const envelope = errorEnvelope(payload);
    if (envelope) throw new ApiClientError(response.status, envelope.error, envelope.meta.request_id);
    throw networkFailure(response.status, requestId);
  }

  if (typeof payload !== "object" || payload === null || !("data" in payload)) {
    throw networkFailure(response.status, requestId);
  }
  const envelope = payload as { data: T; error: null; meta?: { request_id?: string } };
  if (envelope.error !== null) throw networkFailure(response.status, requestId);
  return envelope.data;
}

export const api = {
  get<T>(path: string, signal?: AbortSignal): Promise<T> {
    return request<T>(path, { method: "GET", signal });
  },
  post<T>(path: string, body: unknown, headers?: HeadersInit): Promise<T> {
    return request<T>(path, { method: "POST", body, headers });
  },
  patch<T>(path: string, body: unknown, headers?: HeadersInit): Promise<T> {
    return request<T>(path, { method: "PATCH", body, headers });
  },
};

export function idempotencyHeaders(): HeadersInit {
  return { "Idempotency-Key": crypto.randomUUID() };
}

export const testIdentityConfigured = Boolean(testSubject && testCapabilities);

export async function download(path: string, filename: string): Promise<void> {
  const headers=new Headers();
  if(testSubject&&testCapabilities){headers.set('X-DAP-Test-Subject',testSubject);headers.set('X-DAP-Test-Capabilities',testCapabilities);}
  let response:Response;
  try{response=await fetch(`${apiBase}${path}`,{headers,credentials:'same-origin',cache:'no-store'});}catch{throw networkFailure();}
  if(!response.ok){
    if(response.status===401)sessionExpiredHandler?.();
    const payload=await response.json().catch(()=>null);const envelope=errorEnvelope(payload);
    if(envelope)throw new ApiClientError(response.status,envelope.error,envelope.meta.request_id);
    throw networkFailure(response.status,response.headers.get('X-Request-ID')??undefined);
  }
  const blob=await response.blob(),url=URL.createObjectURL(blob),anchor=document.createElement('a');
  anchor.href=url;anchor.download=filename.replace(/[\\/:*?"<>|]/g,'_');anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
