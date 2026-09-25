"""Privacy-safe analysis request validation shared with stage B."""

from dataclasses import dataclass
from typing import Any


MODEL_IDS = ("tfidf_lr", "lstm", "klue_bert")
MAX_TEXT_CODEPOINTS = 500


@dataclass(frozen=True)
class AnalysisInput:
    text: str
    model_id: str
    include_explanation: bool = False


class ValidationProblem(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_analysis_request(payload: Any) -> AnalysisInput:
    """Validate without ever putting the supplied text in an exception."""
    result = parse_request_shape(payload)
    validate_text(result.text)
    return result


def parse_request_shape(payload: Any) -> AnalysisInput:
    """Reject malformed requests before creating an analysis record."""
    if not isinstance(payload, dict) or set(payload) not in ({"text", "modelId"}, {"text", "modelId", "includeExplanation"}):
        raise ValidationProblem("INVALID_REQUEST")
    if not isinstance(payload["text"], str) or not isinstance(payload["modelId"], str):
        raise ValidationProblem("INVALID_REQUEST")
    if "includeExplanation" in payload and type(payload["includeExplanation"]) is not bool:
        raise ValidationProblem("INVALID_REQUEST")
    model_id = payload["modelId"]
    if model_id not in MODEL_IDS:
        raise ValidationProblem("UNSUPPORTED_MODEL")
    include_explanation = payload.get("includeExplanation", False)
    return AnalysisInput(text=payload["text"], model_id=model_id, include_explanation=include_explanation)


def validate_text(supplied_text: str) -> None:
    if not supplied_text.strip() or len(supplied_text) > MAX_TEXT_CODEPOINTS:
        raise ValidationProblem("INVALID_TEXT")
