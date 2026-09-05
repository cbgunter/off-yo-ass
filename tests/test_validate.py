from oya.prompts.validate import find_violations, is_clean, validate_call_text


def test_clean_text_has_no_violations():
    text = "HRV is 12% under your baseline. 40 minutes walking, easy, 17:30-18:30."
    assert find_violations(text) == []
    assert is_clean(text)


def test_exclamation_mark_is_caught():
    assert "contains an exclamation mark" in find_violations("Let's take it easy today!")


def test_emoji_is_caught():
    assert any("emoji" in v for v in find_violations("Rest tonight 💪"))


def test_em_dash_is_caught():
    assert any("dash" in v for v in find_violations("Sleep is down — rest tonight."))


def test_en_dash_is_caught():
    assert any("dash" in v for v in find_violations("Window: 17:00–18:00."))


def test_cheerleading_phrase_is_caught():
    assert any("cheerleading" in v for v in find_violations("You've got this, go get it."))


def test_cheerleading_check_is_case_insensitive():
    assert any("cheerleading" in v for v in find_violations("WAY TO GO on that ride."))


def test_multiple_violations_are_all_reported():
    text = "Great job! You've got this 💪"
    violations = find_violations(text)
    assert len(violations) >= 3


def test_a_plain_factual_question_is_not_penalized_by_mechanical_checks():
    # Rhetorical-question detection is a system-prompt instruction, not a
    # mechanical check (see the module docstring) -- a real question mark
    # alone must not trip the validator.
    assert is_clean("Is Thursday actually the problem, or is it the time of day?")


def test_validate_call_text_labels_which_field_failed():
    violations = validate_call_text(
        headline="Great job!",
        why="You did the numbers.",
        fallback="A walk works too.",
    )
    assert any(v.startswith("headline") for v in violations)
    assert not any(v.startswith("why") for v in violations)
    assert not any(v.startswith("fallback") for v in violations)


def test_validate_call_text_clean_across_all_fields():
    violations = validate_call_text(
        headline="Resting heart rate is 8 bpm over your 30-day average.",
        why="Sleep was short and stress ran high overnight.",
        fallback="A 15-minute walk covers the minimum.",
    )
    assert violations == []
