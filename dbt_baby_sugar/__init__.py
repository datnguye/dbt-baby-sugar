"""dbt-sugar: a live progress bar and per-node status tree for dbt runs.

Activation is automatic. dbt imports every top-level ``dbt_*`` module at startup
(``PluginManager.get_prefixed_modules``), so importing this package is what wires
dbt-sugar into dbt's event bus — there is no console script to run. Plain
``dbt run``/``build``/``test``/``seed`` light up once this package is installed.
"""

from __future__ import annotations

from dbt_baby_sugar.activation.activation import activate

activate()
