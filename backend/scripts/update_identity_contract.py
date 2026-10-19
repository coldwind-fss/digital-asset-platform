"""Merge implemented identity DTOs into the canonical contract, preserving V2 DTOs.

This is explicit code generation, never run during web startup. Future business
operations remain planned until their own work package implements them.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.main import create_app

PATH = ROOT / "openapi/v1.openapi.json"


def main():
    contract = json.loads(PATH.read_text(encoding="utf-8"))
    runtime = create_app(Settings(auth_provider="local")).openapi()
    source = runtime["components"]["schemas"]
    copied = {}

    def rewrite(value):
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {k: rewrite(v) for k, v in value.items() if k != "$ref"}
        if "$ref" in value:
            name = value["$ref"].rsplit("/", 1)[-1]
            target = "Identity" + name
            if target not in copied:
                copied[target] = {}  # break recursive references
                copied[target] = rewrite(source[name])
            result["$ref"] = "#/components/schemas/" + target
        return result

    # Every identity write has explicit retry behavior; no secret token response
    # is replay-cached. Versioned updates conflict safely on a repeated version.
    retry = {
        "bootstrapAdministrator": "once; repeated initialization returns 409",
        "loginLocalAccount": "new session per successful login; no automatic retry",
        "redeemAccountToken": "single-use token; repeated redemption returns 410",
        "logoutLocalSession": "idempotent revocation; no response replay cache",
        "changeLocalPassword": "revokes all sessions; no automatic retry",
        "reauthenticateLocalSession": "verifies password and refreshes recent-auth time",
        "createLocalAccount": "unique username; repeat returns 409; activation token returned only once",
        "patchLocalAccount": "expected_version; stale version returns 409",
        "issueAccountRecoveryToken": "rotates outstanding token; no automatic retry or token replay cache",
        "createDepartment": "non-idempotent create; no automatic retry; inspect list after uncertain response",
        "patchDepartment": "expected_version; stale version returns 409",
    }
    public = {"getBootstrapStatus", "bootstrapAdministrator", "loginLocalAccount", "redeemAccountToken"}
    count = 0
    for path, item in runtime["paths"].items():
        relative = path.removeprefix("/api/v1")
        if not (relative.startswith("/auth/") or relative.startswith("/admin/")):
            continue
        for method, raw in item.items():
            if method not in {"get", "post", "patch", "delete", "put"}:
                continue
            operation = rewrite(deepcopy(raw))
            operation_id = operation["operationId"]
            operation["x-implementation-status"] = "implemented-v3-stage3" if operation_id == 'listManagedDepartments' else "implemented-v3-stage1"
            operation["security"] = [] if operation_id in public else [{"SessionCookie": [], **({"CsrfToken": []} if method != "get" else {})}]
            if operation_id == "logoutLocalSession":
                operation["description"] = "Anonymous logout clears the cookie; authenticated logout requires Origin and session-bound CSRF."
            if operation_id in retry:
                operation["x-retry-policy"] = retry[operation_id]
            for status in ("401", "403", "409", "410", "422", "429", "503"):
                operation["responses"][status] = {
                    "description": "Common API error; see error.code for the cause.",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
                }
            contract["paths"].setdefault(relative, {})[method] = operation
            count += 1
    # Remove stale generated identity schemas before regenerating their closure.
    contract["components"]["schemas"] = {k:v for k,v in contract["components"]["schemas"].items() if not k.startswith("Identity")}
    contract["components"]["schemas"].update(copied)
    if not any(t["name"] == "identity" for t in contract["tags"]):
        contract["tags"].append({"name": "identity", "description": "Local authentication and team administration"})
    contract["components"]["securitySchemes"]["SessionCookie"]["name"] = Settings().auth_cookie_name
    PATH.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {count} implemented identity operations; retained existing and planned business contracts.")


if __name__ == "__main__":
    main()
