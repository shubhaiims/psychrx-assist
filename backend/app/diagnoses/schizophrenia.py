"""Rule module for schizophrenia.

Uses the shared psychosis logic (clozapine reserved for treatment resistance with
ANC monitoring; metabolic monitoring for SGAs) plus the standard safety bundle.
Non-adherence already up-ranks LAI-available agents via the shared rule.
"""
from app.diagnoses._psychosis_common import PsychosisModule
from app.engine.registry import register


class SchizophreniaModule(PsychosisModule):
    # Extension hook (psychiatrist-reviewed, cited): once a structured count of
    # adequate prior antipsychotic trials is captured, surface clozapine positively
    # for treatment-resistant illness rather than only down-ranking it as first-line.
    pass


MODULE = register(
    SchizophreniaModule(
        diagnosis="schizophrenia",
        display_name="Schizophrenia",
    )
)
