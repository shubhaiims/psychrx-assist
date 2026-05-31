"""Safety modifier modules.

Importing this package imports every safety module, and each one registers its modifier
with the safety registry as an import side effect. The import order below IS the
application order: for every candidate drug the engine runs the modifiers in this order,
and patient-level advisories are merged in this order too. The order is chosen for
readability (population/organ screens first, then risk overlays, then interactions); it
does not affect the final score (deltas are additive) or category.

To add a safety dimension: create ``<name>_safety.py`` subclassing ``SafetyModifier``,
``register(...)`` it, and add it to the imports below.
"""
from __future__ import annotations

from app.safety import pregnancy_lactation_safety  # noqa: F401
from app.safety import renal_safety  # noqa: F401
from app.safety import hepatic_safety  # noqa: F401
from app.safety import cardiac_qtc_safety  # noqa: F401
from app.safety import metabolic_safety  # noqa: F401
from app.safety import seizure_safety  # noqa: F401
from app.safety import elderly_safety  # noqa: F401
from app.safety import child_adolescent_safety  # noqa: F401
from app.safety import suicide_overdose_safety  # noqa: F401
from app.safety import adherence_safety  # noqa: F401
from app.safety import drug_interaction_safety  # noqa: F401
# Guideline-driven rules (JSON-authored) run last, on top of the hard-coded screens.
from app.safety import ips_cpg_safety  # noqa: F401
