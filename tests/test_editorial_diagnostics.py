from white_rabbit.editorial_diagnostics import analyze_editorial_style


def test_detects_cumulative_ai_cadence_without_blocking():
    article = """# Test

This matters because the file exists.

This matters because the date exists.

This matters because the office exists.

It would be a mistake to ignore it. It would be an equal mistake to overstate it.

Not merely policy, but machinery. Both overt offices and covert offices.
"""
    report = analyze_editorial_style(article)
    assert report["symmetric_contrasts"] >= 3
    assert any("cumulative explanatory scaffold" in warning for warning in report["warnings"])
    assert any("symmetric contrast" in warning for warning in report["warnings"])


def test_emphasis_and_visual_integrity_diagnostics():
    article = """# Test

**The whole paragraph is bold.**

**Agency** met **Agency** and later **Agency** returned.

[IMAGE: AI-generated document excerpt | ALT: Proof that the agency secretly ran it]
"""
    report = analyze_editorial_style(article)
    joined = "\n".join(report["warnings"])
    assert "entirely bold" in joined
    assert "repeated bold emphasis" in joined
    assert "argumentative" in joined
    assert "substituting for documentary evidence" in joined


def test_diagnostics_are_metrics_not_style_targets():
    article = """# Test

I opened the file expecting a budget memo. It was a personnel list.

*Why were those names here?*

- State handled policy.
- AID handled the overt program.
- Defense retained selected work.

[IMAGE: Crop of the dated personnel list | ALT: Personnel list showing three agency representatives]
"""
    report = analyze_editorial_style(article)
    assert report["first_person_occurrences"] == 1
    assert report["list_items"] == 3
    assert report["image_markers"] == 1
    assert not any("argumentative" in warning for warning in report["warnings"])


def test_detects_repeated_type_b_performative_caution_without_banning_phrases():
    article = """# Test

I can't prove the name is Engle. I am not going to fill the black bar with a guess.

What the document proves is narrower. The most defensible conclusion stops there.
"""
    report = analyze_editorial_style(article)
    assert report["performative_caution"]["i can't prove"] == 1
    assert report["performative_caution"]["the most defensible"] == 1
    assert any("Type-B performative caution" in warning for warning in report["warnings"])


def test_single_caution_phrase_is_advisory_not_an_automatic_warning():
    report = analyze_editorial_style("# Test\n\nI can't prove who signed the missing page.")
    assert report["performative_caution"] == {"i can't prove": 1}
    assert not any("Type-B performative caution" in warning for warning in report["warnings"])


def test_detects_caution_density_for_compression_review():
    article = """# Test

The file names a redacted employee. The page does not prove it was Engle. I cannot prove
the identity. What the document proves is narrower.
"""
    report = analyze_editorial_style(article)
    assert report["caution_density_passages"] == 1
    assert any("caution density" in warning for warning in report["warnings"])


def test_compact_fact_limit_inference_does_not_trigger_caution_density():
    article = """# Test

The CIA says one employee spent more than ten years as OPS director. The name is blacked
out. By all accounts, it points to Engle.
"""
    report = analyze_editorial_style(article)
    assert report["caution_density_passages"] == 0
