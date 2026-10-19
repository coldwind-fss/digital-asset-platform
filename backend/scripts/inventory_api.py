"""Inventory the canonical contract against registered routes, without a DB."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.main import create_app


def inventory():
    contract = json.loads((ROOT / "openapi/v1.openapi.json").read_text(encoding="utf-8"))
    runtime = create_app(Settings(auth_provider="local")).openapi()
    actual = {(p.removeprefix("/api/v1"),m):o for p,i in runtime["paths"].items() for m,o in i.items() if m in {"get","post","put","patch","delete"}}
    declared = {(p,m):o for p,i in contract["paths"].items() for m,o in i.items() if m in {"get","post","put","patch","delete"}}
    rows = [{"method":m.upper(),"path":p,"operation_id":o["operationId"],"declared_status":o["x-implementation-status"],"registered":(p,m) in actual} for (p,m),o in declared.items()]
    return {"canonical_operations":len(declared), "registered_operations":len(actual), "contract_only_operations":sum(not r["registered"] for r in rows), "uncontracted_routes":[{"method":m,"path":p} for p,m in actual.keys()-declared.keys()], "operations":rows}


if __name__ == "__main__":
    result = inventory()
    destination = ROOT.parent / ".local/workspace/api-inventory.json"
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    document = destination.with_suffix('.md')
    lines = ["# API 实施清单", "", "由 backend/scripts/inventory_api.py 对规范契约和 FastAPI 实际注册接口生成。前缀统一 /api/v1。", "", f"契约 {result['canonical_operations']} 项，实际注册 {result['registered_operations']} 项，仅规划 {result['contract_only_operations']} 项；契约外路由 {len(result['uncontracted_routes'])} 项。注册数量不等于用户业务接受或生产发布。", "", "| 方法 | 路径 | operationId | 运行状态 |", "| --- | --- | --- | --- |"]
    for row in result["operations"]:
        state = "10—12补充、已注册" if row["registered"] and row["declared_status"]=="implemented-v3-stage3" else "03新增、已注册" if row["registered"] and row["declared_status"]=="implemented-v3-stage1" else "04—09实现、已注册" if row["registered"] and row["declared_status"]=="implemented-v3-stage2" else "基础、已注册" if row["registered"] else "仅规划、未注册"
        lines.append(f"| {row['method']} | `{row['path']}` | {row['operation_id']} | {state} |")
    document.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="operations"},ensure_ascii=False))
