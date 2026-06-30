"""Unit tests for document analysis."""

from markdownland import analyzer


def test_analyze_extracts_title_stats_and_outline():
    source = """\
---
title: Publish Me
---

# Heading One

See [site](https://example.com) and ![Alt](https://example.com/img.png).

```python
print("hi")
```

| A | B |
|---|---|
| 1 | 2 |
"""
    result = analyzer.analyze(source)

    assert result.title == "Publish Me"
    assert result.stats.headings == 1
    assert result.stats.links == 1
    assert result.stats.images == 1
    assert result.stats.code_blocks == 1
    assert result.stats.tables == 1
    assert result.stats.reading_minutes == 1
    assert result.outline[0].title == "Heading One"
    assert result.outline[0].anchor == "heading-one"


def test_analyze_uses_first_h1_when_metadata_title_missing():
    result = analyzer.analyze("## Preface\n\n# Real Title {#real}\n\nBody")

    assert result.title == "Real Title"
    assert result.outline[1].anchor == "real"


def test_analyze_ignores_links_inside_code_fences():
    result = analyzer.analyze("# Title\n\n````\n[not counted](rel.md)\n````\n")

    assert result.stats.links == 0
    assert result.stats.code_blocks == 1
