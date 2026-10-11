# INFRASTRUCTURE
from dev.pdf_conversion_qa.cleanup_classes import cleanup_class_counts
from dev.pdf_conversion_qa.text_metrics import normalize, page_profile, recall_counts


# FUNCTIONS
def test_normalize_applies_nfkc_and_drops_whitespace():
    assert normalize("ﬁ n d\n") == "find"


def test_recall_counts_special_and_umlaut_subsets():
    counts = recall_counts("Größe „A“ – §5 €", "Groesse A 5")
    assert counts["ref_umlaut"] == 2
    assert counts["matched_umlaut"] == 0
    assert counts["ref_special"] == 5
    assert counts["matched_special"] == 0
    assert counts["matched_chars"] < counts["ref_chars"]


def test_recall_ignores_markdown_extras():
    counts = recall_counts("Kosten 10", "# Kosten | 10 **")
    assert counts["matched_chars"] == counts["ref_chars"]


def test_page_profile_flags_replacement_characters():
    assert page_profile("a" * 300)["eligible"]
    assert not page_profile("a" * 150)["eligible"]
    assert not page_profile("a" * 290 + "�" * 10)["eligible"]


def test_cleanup_classes_count_skill_patterns():
    text = "x � y &amp; ![img](a.png)\n```\n```\n<table><tr></tr></table>\n" + "a" * 1100 + "\n" + "a" * 50 + "\n$$   $$ z $$"
    counts = cleanup_class_counts(text)
    assert counts["A_replacement_char"] == 1
    assert counts["C"] == 1
    assert counts["G"] == 1
    assert counts["H"] >= 1
    assert counts["F"] == 1
    assert counts["J_long_lines"] == 1
    assert counts["J_repeat_runs"] == 2
