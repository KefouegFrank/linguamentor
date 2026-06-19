from pydantic import BaseModel, Field
from typing import List

class MCQOption(BaseModel):
    key: str = Field(..., description="The option identifier label, e.g., A, B, C, or D.")
    text: str = Field(..., description="The clear textual substance of the choice option.")

class GrammarItem(BaseModel):
    question: str = Field(..., description="The contextual sentence pattern challenge with a targeted fill-in blank gap.")
    options: List[MCQOption] = Field(..., min_items=4, max_items=4, description="Exactly 4 unique logical choice options.")
    correct_key: str = Field(..., description="The correct option key matching one of the options (e.g., A, B, C, or D).")
    explanation: str = Field(..., description="A granular explanation detailing the structural grammar rule tested.")

class VocabularyItem(BaseModel):
    context_sentence: str = Field(..., description="A sentence utilizing an advanced lexical semantic item in context.")
    question: str = Field(..., description="The core definition or semantic replacement question.")
    options: List[MCQOption] = Field(..., min_items=4, max_items=4, description="Exactly 4 unique choice alternatives.")
    correct_key: str = Field(..., description="The correct target key choice matching options.")
    explanation: str = Field(..., description="Granular definition detailing the semantic nuance of the target word.")

class WritingPromptItem(BaseModel):
    prompt_text: str = Field(..., description="An open-ended, engaging creative or professional prompt tailored to test syntactic variety.")
    evaluation_focus: List[str] = Field(..., min_items=3, description="List of 3 distinct criteria that the downstream calibration system will check (e.g., Aspect Markers, Cohesion).")

class DiagnosticTemplate(BaseModel):
    """
    The rigid structural contract mapping directly to Section 11.3 of the Master PRD.
    Enforces a strict 3-part diagnostic challenge matrix.
    """
    target_language: str = Field(..., description="The language being tested (e.g., ENGLISH, FRENCH).")
    assumed_level: str = Field(..., description="The baseline level of the challenge, typically A1 for a new entry profile.")
    grammar_test: GrammarItem
    vocabulary_test: VocabularyItem
    writing_test: WritingPromptItem