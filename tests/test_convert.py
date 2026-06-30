"""Unit tests for conversion helpers."""

from markdownland import convert


def test_standalone_html_uses_frontmatter_title():
    out = convert.to_text("---\ntitle: Export Title\n---\n\n# Ignored", "html_doc")

    assert "<title>Export Title</title>" in out


def test_from_file_imports_html_as_markdown():
    out = convert.from_file(b"<h1>Imported</h1><p>Hello <strong>there</strong>.</p>", "x.html")

    assert "# Imported" in out
    assert "**there**" in out


def test_unknown_text_file_imports_as_text():
    assert convert.from_file(b"# Plain", "notes.unknown") == "# Plain"
