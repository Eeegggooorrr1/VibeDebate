import pytest
from pydantic import ValidationError

from vibedebate.ai.exercise_policy import EXERCISE_KINDS, exercise_kinds
from vibedebate.ai.exercises import ExerciseRequest, exercise_schema


def test_format_is_selected_by_issue_not_client():
    assert exercise_kinds("unsupported_inference") == ("order", "premise", "rewrite")
    assert exercise_kinds("unanswered_objection") == ("rewrite", "coach")
    assert len(EXERCISE_KINDS) == 17

    with pytest.raises(ValidationError):
        ExerciseRequest(issue_index=0, kind="quiz")


def test_order_contract_rejects_malformed_or_ambiguous_structure():
    schema = exercise_schema("order")
    data = dict(
        kind="order",
        title="Chain",
        instruction="Arrange the steps.",
        items=["A", "B", "C"],
        solution=[0, 1, 2],
        explanation="Each step depends on the previous step.",
        criteria="Dependency order",
    )
    assert schema.model_validate(data).solution == [0, 1, 2]

    for invalid in (
        {"items": "A -> B -> C"},
        {"solution": [0, 0, 2]},
        {"solution": [1, 2, 3]},
        {"kind": "quiz"},
        {"items": ["A", "A", "C"]},
    ):
        with pytest.raises(ValidationError):
            schema.model_validate(data | invalid)


def test_open_generation_contract_has_no_choice_fields():
    for kind in ("premise", "rewrite", "coach"):
        properties = exercise_schema(kind).model_json_schema()["properties"]
        assert "items" not in properties
        assert "solution" not in properties
