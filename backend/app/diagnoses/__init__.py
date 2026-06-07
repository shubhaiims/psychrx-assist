"""Diagnosis rule modules.

Importing this package imports every diagnosis submodule, and each submodule
registers its module with the engine registry as a side effect of import. After
all submodules are loaded we assert the registry covers the ``Diagnosis`` enum
exactly, so a missing or stray module is caught at startup rather than at the
bedside.

Detailed modules are imported below. Remaining ICD-11 catalogue entries are
registered as conservative generic modules: they validate, show the selected
diagnosis, and run shared safety checks without inventing medication candidates.
"""
from __future__ import annotations

from app.diagnosis_catalog import DIAGNOSIS_OPTIONS
from app.engine.base import DiagnosisRuleModule
from app.engine.registry import all_modules, register

# Importing each module runs its register(...) call. Order does not affect
# behaviour (the engine selects candidates by indication and sorts
# deterministically), but we keep it grouped by clinical area for readability.

# Mood — unipolar
from app.diagnoses import major_depressive_disorder  # noqa: F401

# Mood — bipolar spectrum
from app.diagnoses import bipolar_mania  # noqa: F401
from app.diagnoses import bipolar_depression  # noqa: F401
from app.diagnoses import bipolar_maintenance  # noqa: F401

# Psychosis
from app.diagnoses import schizophrenia  # noqa: F401
from app.diagnoses import acute_psychosis  # noqa: F401
from app.diagnoses import catatonia  # noqa: F401

# Anxiety / obsessive-compulsive / trauma
from app.diagnoses import ocd  # noqa: F401
from app.diagnoses import generalized_anxiety_disorder  # noqa: F401
from app.diagnoses import social_anxiety_disorder  # noqa: F401
from app.diagnoses import panic_disorder  # noqa: F401
from app.diagnoses import ptsd  # noqa: F401

# Neurodevelopmental
from app.diagnoses import autism_spectrum_disorder  # noqa: F401
from app.diagnoses import adhd  # noqa: F401

# Substance use
from app.diagnoses import alcohol_use_disorder  # noqa: F401
from app.diagnoses import opioid_use_disorder  # noqa: F401

# Older adults / neurocognitive
from app.diagnoses import dementia_related_behavioural_symptoms  # noqa: F401

from app.engine.registry import assert_registry_complete


def _register_generic_catalogue_modules() -> None:
    registered = all_modules()
    for diagnosis, display_name in DIAGNOSIS_OPTIONS:
        if diagnosis not in registered:
            register(DiagnosisRuleModule(diagnosis=diagnosis, display_name=display_name))
            registered[diagnosis] = all_modules()[diagnosis]


_register_generic_catalogue_modules()

# Fail fast if the Diagnosis enum and the registered modules have drifted apart.
assert_registry_complete()
