"""Structured output schema for the medication safety report."""

from pydantic import BaseModel, Field, field_validator


class DrugSummary(BaseModel):
    name: str = Field(description="Canonical drug name")
    what_it_does: str = Field(
        description="Plain-language explanation of what the drug treats"
    )
    how_to_take: str = Field(
        description="Plain-language dosing instructions"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Key warnings in plain language",
    )
    other_names: list[str] = Field(
        default_factory=list,
        description="Brand names / generics this drug may appear under",
    )

    # Models sometimes emit null for empty lists — coerce to [].
    @field_validator("warnings", "other_names", mode="before")
    @classmethod
    def _lists_not_none(cls, v):
        return v if v is not None else []


class InteractionWarning(BaseModel):
    drugs: list[str]
    severity: str = Field(description="high | moderate | low")
    plain_language_explanation: str
    action: str = Field(
        description="What the user should do, e.g. 'call your doctor today'"
    )

    @field_validator("drugs", mode="before")
    @classmethod
    def _lists_not_none(cls, v):
        return v if v is not None else []


class MedicationSafetyReport(BaseModel):
    patient_medication_list: list[str]
    drugs: list[DrugSummary]
    interaction_warnings: list[InteractionWarning]
    urgent_flags: list[str] = Field(
        default_factory=list,
        description="Anything requiring immediate medical attention",
    )
    questions_for_pharmacist: list[str] = Field(
        default_factory=list,
        description="Suggested questions to ask a pharmacist or doctor",
    )
    disclaimer: str = Field(
        default=(
            "This report is for education only and is not medical advice. "
            "Always confirm with your pharmacist or doctor before changing "
            "how you take any medication."
        )
    )

    @field_validator(
        "patient_medication_list",
        "drugs",
        "interaction_warnings",
        "urgent_flags",
        "questions_for_pharmacist",
        mode="before",
    )
    @classmethod
    def _lists_not_none(cls, v):
        return v if v is not None else []
