import { readFileSync } from "node:fs";

const contractPath = new URL("../../backend/openapi/v1.openapi.json", import.meta.url);
const contract = JSON.parse(readFileSync(contractPath, "utf8"));
const failures = [];
const fail = (message) => failures.push(message);

function resolvePointer(reference) {
  if (!reference.startsWith("#/")) {
    fail(`Only local OpenAPI references are allowed: ${reference}`);
    return undefined;
  }
  return reference.slice(2).split("/").map((part) => part.replaceAll("~1", "/").replaceAll("~0", "~"))
    .reduce((current, part) => current?.[part], contract);
}

function walk(value, visit) {
  if (Array.isArray(value)) return value.forEach((child) => walk(child, visit));
  if (!value || typeof value !== "object") return;
  if (typeof value.$ref === "string") {
    if (resolvePointer(value.$ref) === undefined) fail(`Unresolved reference: ${value.$ref}`);
    visit(value.$ref, value);
  }
  Object.values(value).forEach((child) => walk(child, visit));
}

function dereference(value) {
  let current = value;
  const visited = new Set();
  while (current?.$ref) {
    if (visited.has(current.$ref)) return undefined;
    visited.add(current.$ref);
    current = resolvePointer(current.$ref);
  }
  return current;
}

function responseSchema(response) {
  const resolved = dereference(response);
  return resolved?.content?.["application/json"]?.schema;
}

function isEnvelopeSchema(schema) {
  const resolved = dereference(schema);
  const properties = resolved?.properties;
  return Boolean(properties?.data && properties?.error && properties?.meta);
}

if (contract.openapi !== "3.1.0") fail("Contract must declare OpenAPI 3.1.0.");
if (contract.servers?.some((server) => server.url === "/api/v1") !== true) fail("Internal /api/v1 server is missing.");

const operationIds = new Set();
const knownTags = new Set((contract.tags ?? []).map(({ name }) => name));
const methods = new Set(["get", "post", "put", "patch", "delete", "options", "head"]);
const idempotencyExemptions = new Set(["createSecretStage", "revealCredential", "exchangeAuthCode", "logoutSession", "discoverResourceImpacts"]);
const csrfExemptOperationIds = new Set(["exchangeAuthCode"]);
const publicOperationIds = new Set(["getLiveness", "getReadiness", "getLoginContext", "exchangeAuthCode"]);
// Lifecycle tokens are single-use and must never be stored in response replay
// caches. Versioned admin writes reject repeated versions. These explicit
// policies are documented per operation; unrelated business checks stay strict.
const identityWrites = ["bootstrapAdministrator", "loginLocalAccount", "redeemAccountToken", "logoutLocalSession", "changeLocalPassword", "reauthenticateLocalSession", "createLocalAccount", "patchLocalAccount", "issueAccountRecoveryToken", "createDepartment", "patchDepartment"];
identityWrites.forEach((id) => idempotencyExemptions.add(id));
["bootstrapAdministrator", "loginLocalAccount", "redeemAccountToken"].forEach((id) => csrfExemptOperationIds.add(id));
["getBootstrapStatus", "bootstrapAdministrator", "loginLocalAccount", "redeemAccountToken"].forEach((id) => publicOperationIds.add(id));
const bodylessOperations = new Set(["logoutLocalSession", "issueAccountRecoveryToken"]);
for (const id of contract["x-stage2-secret-operations"] ?? []) idempotencyExemptions.add(id);
for (const id of contract["x-stage2-bodyless-operations"] ?? []) bodylessOperations.add(id);
const fileOperations = new Set(contract["x-stage2-file-operations"] ?? []);

for (const [path, pathItem] of Object.entries(contract.paths ?? {})) {
  const pathParams = [...path.matchAll(/\{([^}]+)\}/g)].map((match) => match[1]);
  for (const [method, rawOperation] of Object.entries(pathItem)) {
    if (!methods.has(method)) continue;
    const operation = dereference(rawOperation);
    if (!operation?.operationId || operationIds.has(operation.operationId)) fail(`Missing/duplicate operationId: ${method.toUpperCase()} ${path}`);
    operationIds.add(operation?.operationId);
    if (!operation?.summary || !operation?.tags?.length) fail(`Missing summary or tags: ${method.toUpperCase()} ${path}`);
    for (const tag of operation?.tags ?? []) if (!knownTags.has(tag)) fail(`Unknown tag ${tag}: ${operation.operationId}`);
    if (!operation?.["x-implementation-status"]) fail(`Missing x-implementation-status: ${operation.operationId}`);
    if (!operation?.security?.length && !publicOperationIds.has(operation?.operationId)) fail(`Operation lacks explicit authentication policy: ${operation.operationId}`);

    const params = [...(pathItem.parameters ?? []), ...(operation?.parameters ?? [])].map(dereference).filter(Boolean);
    const declaredPathParams = new Set(params.filter((param) => param.in === "path" && param.required && param.schema).map((param) => param.name));
    for (const name of pathParams) if (!declaredPathParams.has(name)) fail(`Undeclared required path parameter {${name}}: ${operation.operationId}`);
    for (const param of params) if (param.in === "path" && !pathParams.includes(param.name)) fail(`Unused path parameter ${param.name}: ${operation.operationId}`);

    const isWrite = ["post", "put", "patch", "delete"].includes(method);
    if (isWrite && !csrfExemptOperationIds.has(operation.operationId) && !operation.security.some((requirement) => requirement.SessionCookie && requirement.CsrfToken)) {
      fail(`Write operation lacks session-bound CSRF security: ${operation.operationId}`);
    }
    if (isWrite && !idempotencyExemptions.has(operation.operationId)) {
      const hasKey = params.some((param) => param.in === "header" && param.name === "Idempotency-Key" && param.required === true);
      if (!hasKey) fail(`Write operation lacks Idempotency-Key: ${operation.operationId}`);
    }
    if (identityWrites.includes(operation.operationId) && !operation["x-retry-policy"]) fail(`Identity write lacks explicit retry policy: ${operation.operationId}`);
    if (isWrite && method !== "delete" && !bodylessOperations.has(operation.operationId) && !operation.requestBody?.required) fail(`Write request body must be required: ${operation.operationId}`);

    for (const [status, response] of Object.entries(operation?.responses ?? {})) {
      const resolvedResponse = dereference(response);
      const isBinaryFileDownload = (operation.operationId === "downloadFileContent" || fileOperations.has(operation.operationId)) && status === "200" && Object.values(resolvedResponse?.content ?? {}).some((value) => value.schema?.format === "binary");
      if (isBinaryFileDownload) continue;
      const schema = responseSchema(response);
      if (!schema) fail(`Response ${status} has no application/json schema: ${operation.operationId}`);
      else if (!isEnvelopeSchema(schema)) fail(`Response ${status} does not use the common data/error/meta envelope: ${operation.operationId}`);
      if (status === "204") fail(`204 is prohibited by the API contract: ${operation.operationId}`);
      if (/^[45]/.test(status) && schema?.$ref !== "#/components/schemas/ErrorEnvelope") {
        const resolvedSchema = dereference(schema);
        if (resolvedSchema?.properties?.data?.type !== "null" || resolvedSchema?.properties?.error?.$ref !== "#/components/schemas/ApiError") {
          fail(`Error response ${status} must use ErrorEnvelope: ${operation.operationId}`);
        }
      }
    }
  }
}

walk(contract, () => {});

const resourceTypes = contract.components.schemas.ResourceType?.enum ?? [];
const create = contract.components.schemas.ResourceCreate;
const discriminator = create?.discriminator?.mapping ?? {};
if (resourceTypes.length !== 9 || Object.keys(discriminator).length !== 9) fail("ResourceCreate must cover all nine V3 resource types.");
for (const type of resourceTypes) {
  const schemaName = discriminator[type]?.split("/").at(-1);
  const schema = contract.components.schemas[schemaName];
  const constValues = [];
  walk(schema, (_ref, _node) => {});
  function collect(value) {
    if (Array.isArray(value)) return value.forEach(collect);
    if (!value || typeof value !== "object") return;
    if (value.properties?.type_code?.const) constValues.push(value.properties.type_code.const);
    Object.values(value).forEach(collect);
  }
  collect(schema);
  if (!constValues.includes(type)) fail(`Create DTO ${schemaName} does not discriminate type_code=${type}.`);
}

const resourceFields = contract.components.schemas.ResourceFields;
for (const field of ["owning_department", "confirmed_company", "owner"]) {
  if (!resourceFields?.required?.includes(field) || !resourceFields?.properties?.[field]) fail(`ResourceView base is missing confirmed field ${field}.`);
}
const resourceViewProperties = contract.components.schemas.ResourceView?.allOf?.[1]?.properties ?? {};
for (const field of ["people", "attributes", "account", "capabilities"]) if (!resourceViewProperties[field]) fail(`ResourceView is missing confirmed field ${field}.`);
const meResponse = dereference(contract.paths["/me/resources"]?.get?.responses?.["200"]);
const meSchema = responseSchema(meResponse);
const meEnvelope = dereference(meSchema);
const meData = dereference(meEnvelope?.properties?.data);
const myItemSchema = meData?.properties?.items?.items;
if (myItemSchema?.$ref !== "#/components/schemas/MyResourceSummary" || !contract.components.schemas.MyResourceSummary) fail("/me/resources must return my_roles via MyResourcePageEnvelope.");
if (!JSON.stringify(contract.components.schemas.ChangeItemProposal).includes('"replace_key"') || !JSON.stringify(contract.components.schemas.ChangeItemProposal).includes('"change_management_relation"')) fail("Typed change proposals must include replacement and managed-relation actions.");

for (const operationId of ["createSecretStage", "revealCredential"]) {
  const operation = Object.values(contract.paths).flatMap((pathItem) => Object.values(pathItem)).map(dereference).find((item) => item?.operationId === operationId);
  const success = Object.values(operation?.responses ?? {}).map(dereference).find((response) => response?.headers?.["Cache-Control"]?.schema?.const === "no-store");
  if (!success) fail(`${operationId} success response must set Cache-Control: no-store.`);
}

if (failures.length) {
  console.error(failures.map((failure) => `- ${failure}`).join("\n"));
  process.exitCode = 1;
} else {
  console.log(`OpenAPI contract checks passed (${operationIds.size} operations).`);
}
