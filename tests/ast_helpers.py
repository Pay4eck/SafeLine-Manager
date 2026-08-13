from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def source_path(relative_path: str) -> Path:
    return REPOSITORY_ROOT / relative_path


def read_source(relative_path: str) -> str:
    return source_path(relative_path).read_text(encoding="utf-8-sig")


def parse_source(relative_path: str) -> ast.Module:
    path = source_path(relative_path)
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def find_class(tree: ast.Module, class_name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise AssertionError(f"Class {class_name!r} was not found")


def find_method(
    tree: ast.Module, class_name: str, method_name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    class_node = find_class(tree, class_name)
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            return node
    raise AssertionError(f"Method {class_name}.{method_name} was not found")


def compile_method(
    relative_path: str,
    class_name: str,
    method_name: str,
    globals_namespace: dict[str, Any] | None = None,
):
    """Compile one method without importing the application's dependencies."""

    tree = parse_source(relative_path)
    function_node = copy.deepcopy(find_method(tree, class_name, method_name))
    function_node.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[function_node], type_ignores=[]))
    namespace: dict[str, Any] = {}
    exec(compile(module, relative_path, "exec"), globals_namespace or {}, namespace)
    return namespace[method_name]


def class_assignment_names(relative_path: str, class_name: str) -> set[str]:
    class_node = find_class(parse_source(relative_path), class_name)
    names: set[str] = set()
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def method_call_names(relative_path: str, class_name: str, method_name: str) -> set[str]:
    method = find_method(parse_source(relative_path), class_name, method_name)
    return {
        dotted_name(node.func)
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
    }


def route_literals(relative_path: str) -> set[str]:
    routes: set[str] = set()
    for node in ast.walk(parse_source(relative_path)):
        if not isinstance(node, ast.Call) or dotted_name(node.func).split(".")[-1] != "add_url_rule":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            routes.add(node.args[0].value)
    return routes


def string_literals(relative_path: str) -> set[str]:
    return {
        node.value
        for node in ast.walk(parse_source(relative_path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
