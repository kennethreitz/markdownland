"""Unit tests for conversion helpers."""

import shutil

import pytest

from markdownland import convert


def test_single_newlines_render_as_line_breaks():
    # Poetry / lyrics: a single newline must become a real break, not a space.
    html = convert.to_text("Roses are red,\nViolets are blue,", "html")
    assert "<br" in html
    latex = convert.to_text("Roses are red,\nViolets are blue,", "latex")
    assert "\\\\" in latex


def test_clean_pdf_text_dedents_and_drops_page_number():
    # pdftotext -layout output: page-margin indent + a trailing page number.
    raw = "    Title\n\n      Indented line\n\n    12\f    Page two\n"
    out = convert._clean_pdf_text(raw)
    assert out.splitlines()[0] == "Title"  # common margin removed
    assert "  Indented line" in out  # relative indent preserved
    assert "12" not in out.splitlines()  # lone page number dropped
    assert "Page two" in out


@pytest.mark.skipif(
    shutil.which("pdftotext") is None or shutil.which("tectonic") is None,
    reason="pdftotext (poppler) and tectonic required",
)
def test_pdf_import_preserves_relative_indentation():
    md = "# Title\n\n- Top item\n    - Nested item\n"
    lines = convert.from_pdf(convert.to_binary(md, "pdf")).splitlines()
    top = next(line for line in lines if "Top item" in line)
    nested = next(line for line in lines if "Nested item" in line)

    def indent(s):
        return len(s) - len(s.lstrip())

    assert indent(nested) > indent(top)


def test_standalone_html_uses_frontmatter_title():
    out = convert.to_text("---\ntitle: Export Title\n---\n\n# Ignored", "html_doc")

    assert "<title>Export Title</title>" in out


def test_from_file_imports_html_as_markdown():
    out = convert.from_file(b"<h1>Imported</h1><p>Hello <strong>there</strong>.</p>", "x.html")

    assert "# Imported" in out
    assert "**there**" in out


def test_unknown_text_file_imports_as_text():
    assert convert.from_file(b"# Plain", "notes.unknown") == "# Plain"


def test_unknown_binary_file_is_rejected():
    with pytest.raises(convert.ConversionError):
        convert.from_file(b"hello\x00\x00world", "notes.unknown")


def test_importable_extensions_include_common_markdown_aliases():
    assert ".mkd" in convert.importable_extensions()
    assert ".mkd" in convert.import_accept()


def test_importable_extensions_follow_available_tools(monkeypatch):
    monkeypatch.setattr(convert, "PANDOC", None)

    assert ".md" in convert.importable_extensions()
    assert ".docx" not in convert.importable_extensions()


def test_format_catalog_reports_import_and_export_availability():
    catalog = convert.format_catalog()
    assert {
        "tools",
        "accept",
        "importable_extensions",
        "routes",
        "text",
        "binary",
        "import",
    } <= catalog.keys()
    assert ".mkd" in catalog["accept"]
    assert ".mkd" in catalog["importable_extensions"]
    assert any(route["path"] == "/docs/" for route in catalog["routes"])
    assert any(
        item["key"] == "html" and item["endpoint"] == "/text/html" for item in catalog["text"]
    )
    assert any(
        item["key"] == "pdf" and item["endpoint"] == "/download/pdf" for item in catalog["binary"]
    )

    pdf_import = next(item for item in catalog["import"] if item["key"] == "pdf")
    assert pdf_import["extensions"] == [".pdf"]
    assert pdf_import["endpoint"] == "/import/file"
    assert pdf_import["available"] is bool(convert.PDFTOTEXT)


def test_clean_pdf_text_preserves_relative_indent_and_drops_page_numbers():
    raw = "    1\n\n    Title\n      indented\n    2\f  2\n  Next\n    keep\n"

    assert convert._clean_pdf_text(raw) == "Title\n  indented\n\nNext\n  keep"
