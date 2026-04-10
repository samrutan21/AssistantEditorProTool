"""XML parsing accuracy tests for `app.core.scanner`."""

from __future__ import annotations

from pathlib import Path

from app.core.scanner import element_tag_local, parse_xml_file


def test_parse_xml_file_reads_root(fixtures_dir: Path) -> None:
    xml_path = fixtures_dir / "sample_minimal.xml"
    result = parse_xml_file(xml_path)
    assert result.source_path == xml_path.resolve()
    assert result.root.tag == "project"
    assert result.root.get("name") == "minimal"


def test_element_tag_local_strips_namespace() -> None:
    assert element_tag_local("{http://example.com/ns}clip") == "clip"
    assert element_tag_local("clip") == "clip"
