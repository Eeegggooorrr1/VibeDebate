from vibedebate.ai.exercises import Kind

EXERCISE_KINDS: dict[str, tuple[Kind, ...]] = {
    "unclear_claim": ("rewrite", "coach"),
    "claim_shift": ("quiz", "rewrite"),
    "irrelevance": ("quiz", "coach"),
    "unsupported_inference": ("order", "premise", "rewrite"),
    "contradiction": ("order", "quiz"),
    "false_dilemma": ("premise", "rewrite"),
    "hasty_generalization": ("quiz", "rewrite"),
    "straw_man": ("rewrite", "coach"),
    "ad_hominem": ("quiz", "rewrite"),
    "circular_reasoning": ("order", "premise"),
    "equivocation": ("quiz", "rewrite"),
    "causal_error": ("premise", "quiz"),
    "weak_evidence": ("quiz", "coach"),
    "unanswered_objection": ("rewrite", "coach"),
    "overclaiming": ("rewrite", "quiz"),
    "burden_shift": ("quiz", "coach"),
    "appeal_to_authority": ("quiz", "premise"),
}


def exercise_kinds(issue_type: str) -> tuple[Kind, ...]:
    return EXERCISE_KINDS.get(issue_type, ("rewrite",))
