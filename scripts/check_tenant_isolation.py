#!/usr/bin/env python3
"""
Piccadily Industrial Historian — Tenant Isolation Linter
Ensures every DB query executed in route handlers includes user.tenant_id
to prevent cross-tenant data leaks.
"""

import ast
import sys
from pathlib import Path


def check_tenant_isolation(backend_dir: Path) -> bool:
    routers_dir = backend_dir / "app" / "routers"
    if not routers_dir.exists():
        print(f"Error: Routers directory {routers_dir} not found.")
        return False

    has_errors = False

    # Exceptions that are allowed to bypass tenant_id checks (e.g., ops endpoints)
    allowed_exceptions = {
        # function_name: [allowed_queries...]
        "health": ["SELECT 1"],
        "websocket_stream": [
            "SELECT tag_name, value, quality, ts, unit FROM telemetry_latest WHERE tenant_id=$1 AND plant_id=$2"
        ],
        "create_tenant": [
            "SELECT 1 FROM tenants WHERE tenant_id = $1",
            "INSERT INTO tenants (tenant_id, name) VALUES ($1, $2)",
        ],
    }

    for py_file in routers_dir.rglob("*.py"):
        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
                func_name = node.name

                # Check all calls inside the function
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        # Looking for conn.fetch, conn.fetchrow, conn.fetchval, conn.execute
                        if isinstance(child.func, ast.Attribute) and isinstance(child.func.value, ast.Name):
                            if child.func.value.id == "conn" and child.func.attr in (
                                "fetch",
                                "fetchrow",
                                "fetchval",
                                "execute",
                            ):
                                # First argument is usually the query string
                                if (
                                    child.args
                                    and isinstance(child.args[0], ast.Constant)
                                    and isinstance(child.args[0].value, str)
                                ):
                                    query = child.args[0].value

                                    # Skip allowed exceptions
                                    if func_name in allowed_exceptions and query in allowed_exceptions[func_name]:
                                        continue

                                    # Ensure query string contains tenant_id
                                    if "tenant_id" not in query:
                                        print(f"FAIL: {py_file.name} in function '{func_name}'")
                                        print("      Query missing 'tenant_id' filter:")
                                        print(f"      {query[:100]}...")
                                        has_errors = True
                                        continue

                                    # Check if user.tenant_id is passed as an argument
                                    has_tenant_arg = False
                                    for arg in child.args[1:]:
                                        if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
                                            if arg.value.id == "user" and arg.attr == "tenant_id":
                                                has_tenant_arg = True
                                                break

                                    if not has_tenant_arg:
                                        print(f"FAIL: {py_file.name} in function '{func_name}'")
                                        print("      'user.tenant_id' not passed as parameter to query:")
                                        print(f"      {query[:100]}...")
                                        has_errors = True

    return not has_errors


if __name__ == "__main__":
    backend_dir = Path(__file__).parent.parent / "backend"
    print("Running Tenant Isolation Linter...")
    success = check_tenant_isolation(backend_dir)
    if success:
        print("PASS: All queries appear to enforce tenant isolation.")
        sys.exit(0)
    else:
        print("FAIL: Tenant isolation violations found.")
        sys.exit(1)
