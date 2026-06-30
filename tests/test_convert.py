"""Unit tests for conversion helpers."""

import pytest

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


def test_unknown_binary_file_is_rejected():
    with pytest.raises(convert.ConversionError):
        convert.from_file(b"hello\x00\x00world", "notes.unknown")


def test_importable_extensions_include_common_markdown_aliases():
    assert ".mkd" in convert.importable_extensions()
    assert ".mkd" in convert.import_accept()


def test_format_catalog_reports_import_and_export_availability():
    catalog = convert.format_catalog()
    assert {"tools", "text", "binary", "import"} <= catalog.keys()
    assert any(item["key"] == "html" for item in catalog["text"])
    assert any(item["key"] == "pdf" for item in catalog["binary"])

    pdf_import = next(item for item in catalog["import"] if item["key"] == "pdf")
    assert pdf_import["extensions"] == [".pdf"]
    assert pdf_import["available"] is bool(convert.PDFTOTEXT)
