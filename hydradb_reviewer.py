"""Small demo code reviewer for Python snippets.

This script intentionally stays dependency-free so it can be reviewed and run
quickly in a demo repository.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    line: int
    rule: str
    message: str

    def format(self) -> str:
        return f"L{self.line}: [{self.rule}] {self.message}"


class PythonReviewVisitor(ast.NodeVisitor):
    """Collect simple review comments from a Python AST."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.function_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.findings.append(
                Finding(
                    node.lineno,
                    "broad-except",
                    "Catch a specific exception type instead of a bare except.",
                )
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "print"
            and self.function_stack[-1:] != ["print_findings"]
        ):
            self.findings.append(
                Finding(
                    node.lineno,
                    "debug-print",
                    "Prefer logging or returning structured data over print calls.",
                )
            )
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if ast.get_docstring(node) is None and len(node.body) > 4:
            self.findings.append(
                Finding(
                    node.lineno,
                    "missing-docstring",
                    f"Add a short docstring for non-trivial function `{node.name}`.",
                )
            )


def review_source(source: str) -> list[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [
            Finding(
                error.lineno or 1,
                "syntax-error",
                error.msg,
            )
        ]

    visitor = PythonReviewVisitor()
    visitor.visit(tree)
    return sorted(visitor.findings, key=lambda finding: (finding.line, finding.rule))


def review_file(path: Path) -> list[Finding]:
    return review_source(path.read_text(encoding="utf-8"))


def print_findings(findings: Iterable[Finding]) -> None:
    """Write review findings in a compact command-line format."""

    count = 0
    for count, finding in enumerate(findings, start=1):
        print(finding.format())

    if count == 0:
        print("No review findings.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a tiny Python code review demo.")
    parser.add_argument("path", type=Path, help="Python file to review")
    args = parser.parse_args()

    print_findings(review_file(args.path))


if __name__ == "__main__":
    main()
