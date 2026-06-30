"""Unit tests for the markdown validators."""

from markdownland import validators


def rules(source):
    return {f.rule for f in validators.validate(source).findings}


def findings(source, rule):
    return [f for f in validators.validate(source).findings if f.rule == rule]


def test_relative_link_flagged():
    assert "relative-link" in rules("See [docs](guide/intro.md).")


def test_absolute_link_ok():
    assert "relative-link" not in rules("See [docs](https://example.com).")


def test_anchor_link_ok():
    src = "# Intro\n\nJump to [top](#intro)."
    assert "relative-link" not in rules(src)
    assert "missing-anchor" not in rules(src)


def test_missing_anchor_flagged():
    assert "missing-anchor" in rules("# Intro\n\nJump to [later](#later).")


def test_explicit_heading_id_satisfies_anchor():
    src = "# Intro\n\n## Install {#setup}\n\nJump to [setup](#setup)."
    assert "missing-anchor" not in rules(src)


def test_empty_anchor_is_info():
    report = validators.validate("# Intro\n\nBack to [top](#).")
    finding = next(f for f in report.findings if f.rule == "empty-anchor")
    assert finding.severity == "info"


def test_wikilink_flagged():
    assert "wikilink" in rules("See [[Some Page]] for details.")


def test_wikilink_with_alias_flagged():
    assert "wikilink" in rules("See [[Some Page|the page]].")


def test_wikilink_embed_flagged():
    found = findings("![[diagram.png]]", "wikilink")
    assert found and "embed" in found[0].message


def test_standard_link_is_not_a_wikilink():
    assert "wikilink" not in rules("See [the page](https://example.com).")


def test_wikilink_inside_code_fence_ignored():
    assert "wikilink" not in rules("```\n[[Some Page]]\n```")


def test_local_image_is_error():
    report = validators.validate("![cat](images/cat.png)")
    assert "local-image" in {f.rule for f in report.findings}
    assert any(f.severity == "error" for f in report.findings)


def test_remote_image_ok():
    assert "local-image" not in rules("![cat](https://ex.com/cat.png)")


def test_image_without_alt_warns():
    assert "image-alt" in rules("![](https://ex.com/cat.png)")


def test_heading_skip_flagged():
    assert "heading-skip" in rules("# Title\n\n### Too deep")


def test_clean_hierarchy_ok():
    assert "heading-skip" not in rules("# Title\n\n## Section\n\n### Sub")


def test_duplicate_heading_flagged():
    assert "duplicate-heading" in rules("## Setup\n\ntext\n\n## Setup")


def test_duplicate_explicit_heading_id_flagged():
    assert "duplicate-heading" in rules("## One {#x}\n\n## Two {#x}")


def test_unclosed_fence_is_error():
    report = validators.validate("```python\nprint(1)\n")
    assert "unclosed-fence" in {f.rule for f in report.findings}


def test_longer_code_fence_not_closed_by_shorter_fence():
    src = "````\n[rel](a/b.md)\n```\n"
    report_rules = rules(src)
    assert "unclosed-fence" in report_rules
    assert "relative-link" not in report_rules


def test_links_inside_code_fence_ignored():
    src = "```\n[rel](a/b.md)\n```\n"
    assert "relative-link" not in rules(src)


def test_raw_html_warns_for_portability():
    raw = findings("# Title\n\n<div>Only HTML export sees this.</div>", "raw-html")
    assert raw and raw[0].severity == "warning"


def test_dangerous_html_is_error():
    dangerous = findings("# Title\n\n<script>alert(1)</script>", "dangerous-html")
    assert dangerous and dangerous[0].severity == "error"


def test_frontmatter_title_suppresses_no_title_hint():
    src = "---\ntitle: A Real Title\n---\n\n## Section"
    assert "no-title" not in rules(src)


def test_clean_document_reports_ok():
    report = validators.validate(
        "# Title\n\n## Section\n\nA [link](https://example.com).\n"
    )
    assert report.ok
    assert report.counts == {"error": 0, "warning": 0, "info": 0}


def test_line_numbers_are_one_based():
    report = validators.validate("# Title\n\n[bad](rel/path)")
    finding = next(f for f in report.findings if f.rule == "relative-link")
    assert finding.line == 3
