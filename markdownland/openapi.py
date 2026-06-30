"""OpenAPI metadata: request-body schemas, examples, and tag descriptions.

Responder turns these into the schema served at ``/schema.yml`` and rendered by
the ``/docs/`` UI. Our handlers parse form bodies by hand, so request bodies are
described explicitly here via ``openapi_extra``.
"""

from __future__ import annotations

# Operation tag names (Swagger groups endpoints by these).
TAG_APP = "App"
TAG_CONVERT = "Convert"
TAG_IMPORT = "Import"
TAG_INSPECT = "Inspect"
TAG_META = "Meta"

SAMPLE_MD = "# Quarterly Report\n\nRevenue grew **12%**.\n\n- Ship the thing\n- Tell everyone\n"


def _urlencoded(properties: dict, required: list[str], example: dict) -> dict:
    """An ``openapi_extra`` requestBody for an ``x-www-form-urlencoded`` POST."""
    return {
        "requestBody": {
            "required": True,
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {"type": "object", "properties": properties, "required": required},
                    "example": example,
                }
            },
        }
    }


# --- request bodies ----------------------------------------------------------

SOURCE_BODY = _urlencoded(
    {
        "source": {"type": "string", "description": "The markdown document."},
        "filename": {"type": "string", "description": "Original name, used to title downloads."},
        "download": {
            "type": "string",
            "enum": ["1", "true", "yes"],
            "description": "Force an attachment download instead of inline text.",
        },
    },
    ["source"],
    {"source": SAMPLE_MD, "filename": "report.md"},
)

HTML_BODY = _urlencoded(
    {"html": {"type": "string", "description": "Rich text / HTML (e.g. a clipboard paste)."}},
    ["html"],
    {"html": "<h1>Title</h1><p>Hello <strong>world</strong>.</p>"},
)

DOWNLOAD_EXTRA = {
    **SOURCE_BODY,
    "responses": {
        "200": {
            "description": "The rendered document as a file attachment.",
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
}

FILE_BODY = {
    "requestBody": {
        "required": True,
        "description": "A single document to import (DOCX, PDF, HTML, ODT, …).",
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": "The file to import.",
                        }
                    },
                    "required": ["file"],
                }
            }
        },
    }
}


# --- example response payloads ----------------------------------------------

EXAMPLE_IMPORT_HTML = {"markdown": "# Title\n\nHello **world**."}
EXAMPLE_IMPORT_FILE = {
    "markdown": "# Quarterly Report\n\nRevenue grew **12%**.",
    "filename": "report.docx",
}

EXAMPLE_VALIDATE = {
    "ok": False,
    "counts": {"error": 0, "warning": 1, "info": 0},
    "findings": [
        {
            "line": 7,
            "severity": "warning",
            "rule": "relative-link",
            "message": "Link to “guide.md” is relative — it will break once published elsewhere.",
            "snippet": "[docs](guide.md)",
        }
    ],
}

EXAMPLE_ANALYZE = {
    "title": "Quarterly Report",
    "stats": {
        "lines": 5,
        "words": 12,
        "characters": 78,
        "reading_minutes": 1,
        "headings": 1,
        "links": 0,
        "images": 0,
        "code_blocks": 0,
        "tables": 0,
    },
    "outline": [{"line": 1, "level": 1, "title": "Quarterly Report", "anchor": "quarterly-report"}],
    "score": {"value": 100, "label": "Ready"},
    "validation": {"ok": True, "counts": {"error": 0, "warning": 0, "info": 0}},
}

EXAMPLE_HEALTH = {
    "status": "ok",
    "tools": {
        "pandoc": "pandoc 3.10",
        "tectonic": "Tectonic 0.16.9",
        "pdftotext": "pdftotext version 26.06.0",
        "mmdc": "11.16.0",
    },
}

EXAMPLE_FORMATS = {
    "tools": EXAMPLE_HEALTH["tools"],
    "text": [
        {
            "key": "html",
            "label": "HTML",
            "extension": ".html",
            "mimetype": "text/html",
            "available": True,
            "requires": ["pandoc"],
            "endpoint": "/text/html",
        }
    ],
    "binary": [
        {
            "key": "pdf",
            "label": "PDF",
            "extension": ".pdf",
            "mimetype": "application/pdf",
            "available": True,
            "requires": ["pandoc", "tectonic"],
            "endpoint": "/download/pdf",
        }
    ],
    "import": [
        {
            "key": "docx",
            "label": "Word (DOCX)",
            "extensions": [".docx"],
            "available": True,
            "endpoint": "/import/file",
        }
    ],
}

EXAMPLE_ERROR = {"error": "Nothing to convert."}

# Reusable error responses (descriptions) for the convert/import endpoints.
ERROR_RESPONSES = {
    404: "Unknown format key.",
    422: "Conversion failed, or the document was empty/invalid.",
}
