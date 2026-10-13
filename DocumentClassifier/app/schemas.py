"""
Pydantic schemas for the GroundTruth QA system.

Defines the structured response format returned by the question-answering pipeline.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional


class QAResponse(BaseModel):
    """Structured response from the QA system.

    Attributes:
        answer: The answer derived solely from the source document.
        evidence: Relevant quotations from the source document that support the answer.
        confidence: A numeric estimate between 0 and 1 indicating answer reliability.
        abstained: Whether the system declined to answer the question.
        abstention_reason: Brief explanation when the system abstains, otherwise null.
        page_numbers: Source page numbers supporting the evidence (where available).
    """

    answer: str = Field(
        ...,
        description="The answer to the question, based only on the source document.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Relevant quotations from the source document supporting the answer, with page numbers where available.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1.",
    )
    abstained: bool = Field(
        default=False,
        description="Whether the system declined to answer.",
    )
    abstention_reason: Optional[str] = Field(
        default=None,
        description="Brief explanation when the system abstains, otherwise null.",
    )
    page_numbers: list[int] = Field(
        default_factory=list,
        description="Source page numbers where evidence was found.",
    )

    @model_validator(mode="after")
    def validate_abstention_consistency(self) -> "QAResponse":
        """Ensure abstention fields are consistent with each other."""
        if self.abstained and not self.abstention_reason:
            raise ValueError(
                "abstention_reason is required when abstained is True."
            )
        if not self.abstained and self.abstention_reason:
            # Auto-correct: clear the reason if not abstaining
            self.abstention_reason = None
        return self

