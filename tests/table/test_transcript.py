from table.transcript import Transcript, TurnRecord


def test_append_and_len():
    t = Transcript()
    assert len(t) == 0
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="Begin!"))
    assert len(t) == 1


def test_tail_returns_last_n():
    t = Transcript()
    for i in range(10):
        t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text=f"turn {i}"))
    tail = t.tail(3)
    assert len(tail) == 3
    assert tail[0].text == "turn 7"
    assert tail[-1].text == "turn 9"


def test_tail_fewer_than_n():
    t = Transcript()
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="only"))
    assert len(t.tail(10)) == 1


def test_to_markdown_contains_speaker_and_text():
    t = Transcript()
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="The goblin lunges!"))
    t.append(TurnRecord(round=1, actor="Brakka", kind="player_action", text="I charge!"))
    md = t.to_markdown()
    assert "GM" in md
    assert "The goblin lunges!" in md
    assert "Brakka" in md
    assert "I charge!" in md


def test_to_markdown_has_round_header():
    t = Transcript()
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="Round 1 starts."))
    t.append(TurnRecord(round=2, actor="GM", kind="gm_narration", text="Round 2 starts."))
    md = t.to_markdown()
    assert "Round 1" in md
    assert "Round 2" in md


def test_turn_record_metadata_defaults_empty():
    r = TurnRecord(round=1, actor="GM", kind="gm_narration", text="hi")
    assert r.metadata == {}


def test_roll_result_shown_in_markdown():
    t = Transcript()
    t.append(TurnRecord(round=1, actor="Brakka", kind="roll_result", text="attack roll: 17",
                        metadata={"formula": "1d20+3", "result": 17}))
    md = t.to_markdown()
    assert "17" in md
    assert "[ROLL]" in md


def test_tail_zero_returns_empty():
    t = Transcript()
    t.append(TurnRecord(round=1, actor="GM", kind="gm_narration", text="x"))
    assert t.tail(0) == []
