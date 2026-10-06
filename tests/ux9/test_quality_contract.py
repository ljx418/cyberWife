from tests.ux9.accept_voice_dialogue import (
    SCENARIOS,
    character_error_rate,
    normalize_text,
    semantic_checks,
)


def test_normalization_and_cer_ignore_punctuation_but_not_wrong_words():
    assert normalize_text("你好，世界！") == "你好世界"
    assert character_error_rate("二加三等于五。", "二加三等于五") == 0
    assert character_error_rate("二加三等于五。", "二加三等于四。") > 0


def test_character_error_rate_treats_spoken_digits_as_same_notation():
    assert character_error_rate("上午九点", "上午 9 点") == 0


def test_fact_semantic_contract_rejects_a_confident_wrong_answer():
    fact = next(item for item in SCENARIOS if item.id == "fact")
    assert all(semantic_checks(fact, "二加三等于五。 ").values())
    checks = semantic_checks(fact, "当然，答案是四。")
    assert checks["must_any"] is False
    assert checks["forbidden_absent"] is False


def test_context_contract_requires_the_remembered_time():
    context = next(item for item in SCENARIOS if item.id == "context_query")
    assert all(semantic_checks(context, "你明天上午九点开会。 ").values())
    assert semantic_checks(context, "你没有告诉我时间。 ")["must_any"] is False


def test_response_contract_rejects_incomplete_or_repeated_output():
    greeting = SCENARIOS[0]
    assert semantic_checks(greeting, "你好你好你好")["no_abnormal_repeat"] is False
    assert semantic_checks(greeting, "你好")["complete_ending"] is False
