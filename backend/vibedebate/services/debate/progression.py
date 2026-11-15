from dataclasses import dataclass, replace


from vibedebate.schemas.internal.progression import ProgressState


@dataclass(frozen=True)
class ChatProgressPolicy:
    minimum_answers: int = 5
    target_score: float = 75
    required_streak: int = 3

    def advance(
        self, state: ProgressState, score: float | None, critical: bool = False
    ) -> ProgressState:
        if score is None:
            return state

        count = state.count + 1
        total = round(state.total + score, 2)
        streak = (
            min(self.required_streak, state.streak + 1)
            if score >= self.target_score and not critical
            else 0
        )
        mastered = state.mastered or (
            count >= self.minimum_answers
            and total / count >= self.target_score
            and streak >= self.required_streak
        )

        return ProgressState(count, total, streak, mastered)

    def concede(self, state: ProgressState) -> ProgressState:
        return replace(state, mastered=True)

    def percentage(self, state: ProgressState) -> int:
        if state.mastered:
            return 100
        if not state.count:
            return 0

        quality = min(1, state.total / state.count / self.target_score)
        volume = min(1, state.count / self.minimum_answers)
        consistency = min(1, state.streak / self.required_streak)

        return min(99, round(50 * quality + 25 * volume + 25 * consistency))
