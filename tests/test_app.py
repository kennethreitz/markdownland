"""Integration tests for the markdownland Responder app."""

import shutil

import pytest

from app import api

client = api.requests


def test_index_serves_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "markdownland" in r.text
    assert 'id="source"' in r.text


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


@pytest.mark.skipif(shutil.which("tectonic") is None, reason="tectonic not installed")
def test_pdf_download():
    r = client.post("/download/pdf", data={"source": "# Hello PDF\n\nBody."})
    assert r.status_code == 200, r.text
    assert r.content[:5] == b"%PDF-"
