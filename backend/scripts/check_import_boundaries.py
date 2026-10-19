from __future__ import annotations

import ast
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "app"
FRAMEWORK_ROOTS = {"fastapi", "pydantic", "sqlalchemy", "starlette"}
failures: list[str] = []


def imported_modules(tree: ast.AST) -> list[str]:
    results: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            results.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                results.append(node.module)
    return results


def check_domain(path: Path, module_name: str, imports: list[str]) -> None:
    for imported in imports:
        root = imported.split(".", maxsplit=1)[0]
        if root in FRAMEWORK_ROOTS or imported.startswith("app.platform") or imported.startswith("app.api"):
            failures.append(f"{path.relative_to(APP_ROOT)}: domain imports framework/platform module {imported}")
        if imported.startswith("app.modules."):
            target_parts = imported.split(".")
            target_module = target_parts[2] if len(target_parts) > 2 else ""
            if target_module != module_name:
                failures.append(f"{path.relative_to(APP_ROOT)}: domain imports another module {imported}")


def check_module_imports(path: Path, module_name: str, imports: list[str]) -> None:
    for imported in imports:
        if imported.startswith(("backend.app", "legacy_app", "old_backend")):
            failures.append(f"{path.relative_to(APP_ROOT)}: Digital Asset Platform imports a legacy application module {imported}")
        if not imported.startswith("app.modules."):
            continue
        parts = imported.split(".")
        if len(parts) < 3:
            continue
        target_module = parts[2]
        if target_module == module_name:
            continue
        if len(parts) < 4 or parts[3] != "public":
            failures.append(f"{path.relative_to(APP_ROOT)}: cross-module dependency must use the target module's public package: {imported}")
        if "infrastructure" in parts:
            failures.append(f"{path.relative_to(APP_ROOT)}: cross-module infrastructure import is forbidden: {imported}")


def main() -> int:
    if not APP_ROOT.is_dir():
        print(f"Digital Asset Platform application directory not found: {APP_ROOT}", file=sys.stderr)
        return 2

    for path in sorted(APP_ROOT.rglob("*.py")):
        relative = path.relative_to(APP_ROOT)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            failures.append(f"{relative}: syntax error at line {error.lineno}: {error.msg}")
            continue
        imports = imported_modules(tree)
        if relative.parts[:1] == ("modules",) and len(relative.parts) > 1:
            module_name = relative.parts[1]
        else:
            module_name = ""
        if module_name and "domain" in relative.parts:
            check_domain(path, module_name, imports)
        check_module_imports(path, module_name, imports)

    if failures:
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        return 1

    print("Digital Asset Platform module import boundaries passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
