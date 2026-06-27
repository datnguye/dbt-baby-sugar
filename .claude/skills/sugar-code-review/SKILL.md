---
name: sugar-code-review
description: >-
  Loop a focused code review over the dbt-baby-sugar Python package on four
  dimensions — DRY, pluggability, low complexity, optimization — and APPLY the
  high-confidence fixes, keeping ruff and the 100% coverage gate green. Use when
  asked to review/clean up/refactor dbt-baby-sugar code for quality (not bug-hunting).
---

# Sugar code review

A quality-only review loop for the `dbt_baby_sugar/` package. It finds and **applies**
behavior-preserving improvements across four dimensions, then proves the change
with lint + the 100% coverage gate. It does not hunt for bugs — use a separate
correctness pass for that.

## The four dimensions

1. **DRY** — repeated logic that should be one helper: get-or-create patterns,
   repeated `getattr` coercion, parallel symbol/status maps, near-duplicate
   functions. Merge them; keep one source of truth.
2. **Pluggable** — can someone extend behavior without editing core? Prefer
   dict-dispatch tables over `if/elif` chains on a type/name; instance-level
   override seams (e.g. symbol maps passed to `__init__`) over baked-in module
   constants; a small Protocol as the extension point.
3. **Low complexity** — flatten deep branching, table-drive what is really a
   mapping, delete dead params/redundant guards, use early returns. Each
   function should read top-to-bottom with one job.
4. **Optimized** — the event handler fires on *every* dbt event (thousands per
   run). The ignore path must be cheap and early. Avoid per-event allocation,
   repeated work under lock, and O(n²) sweeps over nodes. Release locks before
   iterating snapshots.

## The loop

1. **Read** every `.py` under `dbt_baby_sugar/` (core/, events/, ui/, activation/).
2. **Fan out** one read-only reviewer per dimension (or two: DRY+complexity,
   pluggability+optimization) via the Explore agent. Each returns a numbered
   list of `file:line → problem → concrete minimal fix`.
3. **Triage** — apply only high-confidence, behavior-preserving findings.
   **Reject over-engineering**: caches with invalidation, speculative protocol
   expansion, and dirty-tracking are usually premature for a 50–200 node run —
   say so explicitly rather than silently skipping.
4. **Apply** the accepted fixes.
5. **Verify** (the gate — all must pass):
   ```
   uv run ruff format .
   uv run ruff check .
   uv run pytest --cov=dbt_baby_sugar --cov-report=term-missing --cov-fail-under=100
   ```
   Never suppress `PLC0415` with `# noqa` — defer imports via
   `importlib.import_module(...)` inside a `try/except ImportError`.
6. **Repeat** until a pass yields no accepted findings.

## House rules (must hold after the review)

- One class per file; no nested functions/classes (a method-wrapper closure in a
  module-level factory is the only allowed closure).
- No relative imports; all imports at module top.
- Group modules in subpackages (core/events/ui/activation), never flat.
- DRY in tests too — share fixtures via `tests/conftest.py`.
- 100% coverage, no `# pragma: no cover` gaming.

## Optional: review the live UX

If the change touches the renderer or event handling, confirm the real terminal
experience — a plain pipe shows nothing (non-TTY suppresses `rich.Live`). Run
under a pty and replay the frames:

```python
import pty, os
out = open("/tmp/sugar.raw", "wb")
pty.spawn(["<venv>/bin/dbt", "build", "--select", "stg_customers+"],
          master_read=lambda fd: (lambda d: (out.write(d), d)[1])(os.read(fd, 4096)))
out.close()
# then: feed /tmp/sugar.raw to pyte.Screen and print screen.display
```

Check: stable total (no jumping counts), no native dbt log bleeding under the
panel, the tree never overflows, and the pet actually animates frame-to-frame.

## Output

End with a short report: what was applied (one line each, with file), what was
rejected and why, and the final gate result (ruff clean, N tests, 100%).
