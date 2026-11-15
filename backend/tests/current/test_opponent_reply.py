from vibedebate.ai.opponent_reply import OpponentReplyFilter, victory_marker
from vibedebate.services.debate.progression import ChatProgressPolicy, ProgressState


def test_every_footer_split_is_hidden_and_awards_victory():
    marker = victory_marker()
    text = "You have refuted my position."
    wire = text + "\n" + marker
    for split in range(len(wire) + 1):
        parser = OpponentReplyFilter(marker)
        visible = parser.feed(wire[:split]) + parser.feed(wire[split:])
        tail, won = parser.finish()
        assert visible + tail == text
        assert won
    parser = OpponentReplyFilter(marker)
    visible = "".join(parser.feed(char) for char in wire)
    tail, won = parser.finish()
    assert visible + tail == text and won


def test_normal_partial_foreign_and_nonfinal_footer_do_not_win():
    marker = victory_marker()
    for wire in (
        "Normal reply\n",
        "Text\n" + marker + "More objections",
        "Text\n" + victory_marker(),
        "Text\n" + marker[:20],
    ):
        parser = OpponentReplyFilter(marker)
        visible = parser.feed(wire)
        tail, won = parser.finish()
        assert not won
        if wire == "Normal reply\n":
            assert visible + tail == wire


def test_concession_preserves_actual_statistics():
    policy = ChatProgressPolicy()
    state = ProgressState(count=2, total=30, streak=0)
    won = policy.concede(state)
    assert won.mastered and policy.percentage(won) == 100
    assert (won.count, won.total, won.streak) == (2, 30, 0)
    assert policy.advance(won, 0).mastered


def test_malformed_current_token_is_hidden_without_awarding_victory():
    marker = victory_marker()
    wire = "Text" + marker
    for split in range(len(wire) + 1):
        parser = OpponentReplyFilter(marker)
        visible = parser.feed(wire[:split]) + parser.feed(wire[split:])
        tail, won = parser.finish()
        assert visible + tail == "Text" and not won
