"""Unit tests for the markdown validators."""

import validators


def rules(source):
    return {f.rule for f in validators.validate(source).findings}


def test_relative_link_flagged():
    assert "relative-link" in rules("See [docs](guide/intro.md).")


def test_absolute_link_ok():
    assert "relative-link" not in rules("See [docs](https://example.com).")


def test_anchor_link_ok():
    assert "relative-link" not in rules("Jump to [top](#intro).")


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


def test_unclosed_fence_is_error():
    report = validators.validate("```python\nprint(1)\n")
    assert "unclosed-fence" in {f.rule for f in report.findings}


def test_links_inside_code_fence_ignored():
    src = "```\n[rel](a/b.md)\n```\n"
    assert "relative-link" not in rules(src)


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
