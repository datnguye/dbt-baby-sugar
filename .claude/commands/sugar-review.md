---
description: Loop a DRY / pluggable / low-complexity / optimized review over dbt_baby_sugar/ and apply the fixes, keeping ruff + 100% coverage green.
---

Run the `sugar-code-review` skill against the `dbt_baby_sugar/` package.

Review and **apply** behavior-preserving improvements across the four
dimensions — DRY, pluggability, low complexity, optimization — looping until a
pass yields no accepted findings. Reject over-engineering (caches with
invalidation, speculative protocol expansion, dirty-tracking) and say so.

After each round of edits the gate must pass:

```
uv run ruff format .
uv run ruff check .
uv run pytest --cov=dbt_baby_sugar --cov-report=term-missing --cov-fail-under=100
```

If `$ARGUMENTS` names a path or subpackage (e.g. `events/`), scope the review to
that; otherwise review all of `dbt_baby_sugar/`.

Do not change behavior or hunt for bugs — quality only. Finish with a short
report: applied (with file), rejected (with reason), and the final gate result.
