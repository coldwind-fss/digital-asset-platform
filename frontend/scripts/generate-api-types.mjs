import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const contractPath = new URL("../../backend/openapi/v1.openapi.json", import.meta.url);
const outputPath = new URL("../src/shared/api/generated.ts", import.meta.url);
const contract = JSON.parse(readFileSync(contractPath, "utf8"));
const componentNames = Object.keys(contract.components.schemas).sort();

function resolvePointer(reference) {
  if (!reference.startsWith("#/")) return;
  const target = reference
    .slice(2)
    .split("/")
    .map((part) => part.replaceAll("~1", "/").replaceAll("~0", "~"))
    .reduce((current, part) => current?.[part], contract);
  if (target === undefined) throw new Error(`Unresolved OpenAPI reference: ${reference}`);
}

function validateContract() {
  if (contract.openapi !== "3.1.0") throw new Error("The Digital Asset Platform API contract must use OpenAPI 3.1.0");
  const operationIds = new Set();
  const methods = new Set(["get", "post", "put", "patch", "delete", "options", "head"]);
  for (const [path, pathItem] of Object.entries(contract.paths)) {
    for (const [method, operation] of Object.entries(pathItem)) {
      if (!methods.has(method)) continue;
      if (!operation.operationId || operationIds.has(operation.operationId)) {
        throw new Error(`Missing or duplicate operationId for ${method.toUpperCase()} ${path}`);
      }
      if (!operation["x-implementation-status"]) {
        throw new Error(`Missing x-implementation-status for ${method.toUpperCase()} ${path}`);
      }
      operationIds.add(operation.operationId);
    }
  }
  const visit = (value) => {
    if (Array.isArray(value)) return value.forEach(visit);
    if (value && typeof value === "object") {
      if (typeof value.$ref === "string") resolvePointer(value.$ref);
      Object.values(value).forEach(visit);
    }
  };
  visit(contract);
}

validateContract();

function refType(reference) {
  const prefix = "#/components/schemas/";
  if (!reference.startsWith(prefix)) {
    throw new Error(`Unsupported OpenAPI schema reference: ${reference}`);
  }
  const name = reference.slice(prefix.length);
  if (!componentNames.includes(name)) {
    throw new Error(`Unknown OpenAPI schema: ${name}`);
  }
  return `components["schemas"][${JSON.stringify(name)}]`;
}

function schemaType(schema) {
  if (schema.$ref) return refType(schema.$ref);
  if (schema.const !== undefined) return JSON.stringify(schema.const);
  if (schema.enum) return schema.enum.map((value) => JSON.stringify(value)).join(" | ");
  if (schema.oneOf || schema.anyOf) {
    return (schema.oneOf ?? schema.anyOf).map(schemaType).join(" | ");
  }
  if (schema.allOf) return schema.allOf.map(schemaType).join(" & ");

  if (Array.isArray(schema.type)) {
    const nonNull = schema.type.filter((type) => type !== "null");
    const union = nonNull.map((type) => schemaType({ ...schema, type })).join(" | ");
    return schema.type.includes("null") ? `${union} | null` : union;
  }
  if (schema.type === "array") return `Array<${schemaType(schema.items ?? {})}>`;
  if (schema.type === "object" || schema.properties) {
    const properties = Object.entries(schema.properties ?? {}).map(([name, child]) => {
      const optional = !(schema.required ?? []).includes(name);
      return `    ${JSON.stringify(name)}${optional ? "?" : ""}: ${schemaType(child)};`;
    });
    const extra = schema.additionalProperties;
    if (extra !== false) {
      const valueType = extra && typeof extra === "object" ? schemaType(extra) : "unknown";
      properties.push(`    [key: string]: ${valueType};`);
    }
    return properties.length ? `{\n${properties.join("\n")}\n  }` : "Record<string, never>";
  }
  if (schema.type === "integer" || schema.type === "number") return "number";
  if (schema.type === "boolean") return "boolean";
  if (schema.type === "null") return "null";
  if (schema.type === "string") return "string";
  return "unknown";
}

const schemas = componentNames
  .map((name) => `    ${JSON.stringify(name)}: ${schemaType(contract.components.schemas[name])};`)
  .join("\n");
const contents = [
  "/* eslint-disable */",
  "// Generated from ../../../../backend/openapi/v1.openapi.json. Do not edit by hand.",
  "export interface components {",
  "  schemas: {",
  schemas,
  "  };",
  "}",
  "",
  "export type ApiSchemas = components[\"schemas\"];",
  "",
].join("\n");

const path = fileURLToPath(outputPath);
if (process.argv.includes("--check")) {
  const current = readFileSync(outputPath, "utf8");
  if (current !== contents) throw new Error("Generated API types are out of date; run npm run api:types");
  console.log("OpenAPI contract and generated TypeScript DTOs are in sync.");
} else {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, contents, "utf8");
  console.log(`Generated ${path} from ${fileURLToPath(contractPath)}`);
}
