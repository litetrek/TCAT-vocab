"""
test_term_compliance.py
=======================
Unit tests for ai.check_term_compliance() and ai.heading_number() (offline, no API calls).

Run with:  pytest test_term_compliance.py -v
      or:  python test_term_compliance.py
"""

from ai import check_term_compliance, heading_number


def T(zh, en):
    return {"chinese": zh, "english": en, "term_id": "T0"}


def missing(english, zh, en):
    return check_term_compliance(english, [T(zh, en)])


# ── The four required cases ──────────────────────────────────────────────────

def test_leading_capital_article():
    assert missing("First we discuss the greater and a lesser teaching.", "小法", "A lesser teaching") == []
    assert missing("One disparages the lesser teaching.", "小法", "A lesser teaching") == []


def test_verb_tense():
    assert missing("For forty-nine years the Buddha transmitted the Dharma.", "傳法", "transmit the Dharma") == []
    assert missing("He spent his life transmitting Dharma.", "傳法", "transmit the Dharma") == []


def test_plural():
    assert missing("All sentient beings seek liberation.", "眾生", "sentient being") == []


def test_gloss_dropped():
    m = missing("They fall into the intermediate state and suffer.", "中陰", "intermediate state (Bardo in Tibetan)")
    assert len(m) == 1 and m[0]["partial"] is True


# ── Other behaviour ──────────────────────────────────────────────────────────

def test_gloss_kept():
    assert missing("the intermediate state (Bardo in Tibetan) is", "中陰", "intermediate state (Bardo in Tibetan)") == []


def test_really_missing():
    m = missing("He taught the Dharma.", "傳法", "transmit the Dharma")
    assert len(m) == 1 and m[0]["partial"] is False


def test_irregular_forms():
    assert missing("The Buddha taught this sutra.", "說法", "teach") == []
    assert missing("Gifts were given freely.", "施", "give") == []


def test_usage_label_and_alternatives():
    assert missing("to practice the Dharma", "修行", "spiritual practice (noun); to practice the Dharma (verb)") == []
    assert missing("they attain accomplishment", "成就", "be/become/get accomplished; attain accomplishment") == []


def test_heading_number():
    assert heading_number("一 先說大小法 又看邪與正") == 1
    assert heading_number("二、修行之道") == 2
    assert heading_number("（三）結論") == 3
    assert heading_number("十二．總結") == 12
    assert heading_number("一切眾生皆有佛性") is None
    assert heading_number("佛陀在此世界傳法四十九年") is None


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except AssertionError:
            failed += 1
            print("FAIL", name)
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
