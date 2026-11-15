from vibedebate.services.debate.progression import ChatProgressPolicy, ProgressState


def test_mastery_requires_volume_average_and_streak():
    policy = ChatProgressPolicy()
    state = ProgressState()
    for score in [90, 90, 90, 90]:
        state = policy.advance(state, score)
    assert not state.mastered
    state = policy.advance(state, 90)
    assert state.mastered and policy.percentage(state) == 100
    assert policy.advance(state, 0).mastered


def test_critical_and_low_scores_reset_streak_but_questions_do_not():
    policy = ChatProgressPolicy()
    state = policy.advance(ProgressState(), 90)
    assert policy.advance(state, None) == state
    assert policy.advance(state, 90, critical=True).streak == 0
    assert policy.advance(state, 74).streak == 0
    state = ProgressState(10, 100, 2)
    assert not policy.advance(state, 90).mastered


def test_boundary_average_uses_score_precision():
    policy = ChatProgressPolicy()
    state = ProgressState()
    for score in [74.99, 75.01, 75, 75, 75]:
        state = policy.advance(state, score)
    assert state.total == 375 and state.mastered
