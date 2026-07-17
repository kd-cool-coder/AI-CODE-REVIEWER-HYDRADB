# Backend Team Coding Standards

## STYLE-001: Function Length
Functions should do one thing. If a function exceeds 30 lines, extract a helper.
Exceptions: data transformation pipelines where splitting obscures the flow.

## STYLE-002: Error Handling
Never use bare `except`. Always catch specific exceptions.
API endpoints must return structured error responses, not stack traces.

## STYLE-003: Early Returns
Use guard clauses instead of nested conditionals. If a function has more than
two levels of indentation from control flow, refactor to early returns.

## STYLE-004: Naming
- Boolean variables: prefix with `is_`, `has_`, `should_`, `can_`.
- Functions: verb-first (`get_user`, `validate_order`, not `user_getter`).
- Constants: `UPPER_SNAKE_CASE`.

## STYLE-005: Type Hints
All public function signatures must include type hints.
Use `Optional[X]` instead of `X | None` when the reviewed project must support Python 3.9.
