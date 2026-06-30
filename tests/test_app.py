"""Integration tests for the markdownland Responder app."""

import shutil

import pytest

import convert
from app import api

client = api.requests


def test_index_serves_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "markdownland" in r.text
    assert 'id="source"' in r.text
    assert 'id="inspector"' in r.text
    assert 'id="tabbar"' in r.text
    assert 'href="/docs/"' in r.text
    assert "/static/tables.js" in r.text
    assert "/static/tabs.js" in r.text
    assert "/static/mermaid.js" in r.text
    assert 'data-table="format"' in r.text
    assert 'data-kind="source-download"' in r.text


def test_api_docs_route_is_available_at_docs_slash():
    r = client.get("/docs/")
    assert r.status_code == 200
    assert "markdownland" in r.text


def test_health_reports_tools():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "pandoc" in body["tools"]


def test_preview_renders_html_and_lint():
    r = client.post("/preview", data={"source": "# Hi\n\n[x](rel/path.md)"})
    assert r.status_code == 200
    assert "<h1" in r.text                       # rendered markdown
    assert 'id="lint"' in r.text                 # OOB validation panel
    assert 'id="inspector"' in r.text            # OOB document inspector
    assert "Words" in r.text
    assert "hx-swap-oob" in r.text
    assert "relative" in r.text.lower()          # the finding


def test_preview_empty_source():
    r = client.post("/preview", data={"source": "   "})
    assert r.status_code == 200
    assert "Nothing to preview" in r.text


def test_text_conversion_rst():
    r = client.post("/text/rst", data={"source": "# Title\n\nHello **bold**."})
    assert r.status_code == 200
    assert "Title" in r.text
    assert "=====" in r.text                     # rST underlines headings


def test_text_conversion_unknown_format():
    r = client.post("/text/nope", data={"source": "# Hi"})
    assert r.status_code == 404


def test_text_download_sets_disposition():
    r = client.post("/text/latex", data={"source": "# Hi", "download": "1",
                                         "filename": "my doc.md"})
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "my-doc.tex" in r.headers["content-disposition"]


def test_standalone_html_download_inlines_stylesheet():
    r = client.post("/text/html_doc", data={"source": "# Hi", "download": "1"})
    assert r.status_code == 200
    assert "<!DOCTYPE html>" in r.text
    assert "<title>Hi</title>" in r.text
    assert "max-width: 46rem" in r.text
    assert 'href=":root' not in r.text


def test_import_html_endpoint_converts_b_tag():
    r = client.post("/import/html", data={"html": "<h1>Imported</h1><p>Hello <b>there</b>.</p>"})
    assert r.status_code == 200
    body = r.json()
    assert "# Imported" in body["markdown"]
    assert "**there**" in body["markdown"]


def test_import_file_html_endpoint():
    r = client.post(
        "/import/file",
        files={"file": ("note.html", b"<h1>Imported</h1><p>Hello.</p>", "text/html")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == "note.html"
    assert "# Imported" in body["markdown"]


def test_analyze_endpoint_json():
    r = client.post("/analyze", data={"source": "# Title\n\nSee [site](https://example.com)."})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Title"
    assert body["stats"]["headings"] == 1
    assert body["stats"]["links"] == 1
    assert body["score"]["label"] == "Ready"


def test_space_heavy_body_does_not_break_decoding():
    # urlencoded forms turn spaces into '+', which chardet can mis-detect as
    # UTF-7 and crash. A long, space-heavy, non-ASCII body must still decode.
    source = ("# Title\n\n" + "word " * 400 + "\n\nGreek café résumé 🚀 — "
              "see [docs](rel/guide.md)")
    r = client.post("/validate", data={"source": source})
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(f["rule"] == "relative-link" for f in body["findings"])


def test_unicode_round_trips_through_conversion():
    r = client.post("/text/plain", data={"source": "# café 🚀 résumé"})
    assert r.status_code == 200
    assert "café" in r.text and "🚀" in r.text


def test_validate_endpoint_json():
    r = client.post("/validate", data={"source": "[x](rel/path.md)"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert any(f["rule"] == "relative-link" for f in body["findings"])


def test_docx_download():
    r = client.post("/download/docx", data={"source": "# Hello\n\nWorld."})
    assert r.status_code == 200
    assert r.headers["content-disposition"].endswith('.docx"')
    assert r.content[:2] == b"PK"                # docx is a zip


def test_import_html_endpoint():
    html = "<h1>Hi</h1><p>Hello <strong>bold</strong> and <em>italic</em>.</p>"
    r = client.post("/import/html", data={"html": html})
    assert r.status_code == 200
    md = r.json()["markdown"]
    assert "# Hi" in md
    assert "**bold**" in md and "*italic*" in md


def test_import_html_empty():
    r = client.post("/import/html", data={"html": "   "})
    assert r.status_code == 200
    assert r.json()["markdown"] == ""


def test_import_file_docx_round_trip():
    docx = convert.to_binary("# Imported\n\nHello **world**.", "docx")
    r = client.post(
        "/import/file",
        files={"file": ("report.docx", docx,
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == "report.docx"
    assert "Imported" in body["markdown"]
    assert "**world**" in body["markdown"]


def test_import_file_html():
    r = client.post(
        "/import/file",
        files={"file": ("page.html", b"<h2>Title</h2><p>Body text.</p>", "text/html")},
    )
    assert r.status_code == 200
    assert "## Title" in r.json()["markdown"]


def test_import_file_missing():
    r = client.post("/import/file", data={"nope": "1"})
    assert r.status_code == 400


@pytest.mark.skipif(
    shutil.which("pdftotext") is None or shutil.which("tectonic") is None,
    reason="pdftotext (poppler) and tectonic required",
)
def test_import_file_pdf():
    pdf = convert.to_binary("# PDF Heading\n\nHello from a PDF.", "pdf")
    r = client.post(
        "/import/file", files={"file": ("paper.pdf", pdf, "application/pdf")}
    )
    assert r.status_code == 200, r.text
    md = r.json()["markdown"]
    assert "PDF Heading" in md
    assert "Hello from a PDF" in md


@pytest.mark.skipif(shutil.which("tectonic") is None, reason="tectonic not installed")
def test_pdf_download():
    r = client.post("/download/pdf", data={"source": "# Hello PDF\n\nBody."})
    assert r.status_code == 200, r.text
    assert r.content[:5] == b"%PDF-"
