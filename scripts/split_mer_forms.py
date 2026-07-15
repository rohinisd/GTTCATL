"""Split All_ATL_MER_Forms.docx into individual downloadable form files.

Previously used a naive `<w:tbl` search that also matched `<w:tblCellMar` /
`<w:tblPr`, which sliced tables mid-structure and produced blank Word docs.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SOURCE_DOCX = Path(r"C:\Users\rohin\OneDrive\Documents\Downloads\All_ATL_MER_Forms.docx")
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "StudentDashboard" / "app" / "static" / "uploads" / "forms"
CATALOG_PATH = Path(__file__).resolve().parents[1] / "StudentDashboard" / "app" / "forms_catalog.py"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"

FORM_TITLES = {
    "01": "ATL Monthly Progress Report",
    "02": "Trainer Daily Diary / Session Log",
    "03": "Student Attendance Register",
    "04": "Master Trainer Field Visit Report",
    "05": "Student Assessment Record",
    "06": "Industry Exposure Visit Report",
    "07": "Inter-ATL Competition Report",
    "08": "Consumables Register",
    "09": "Quarterly Performance Rating",
    "10": "Utilization Certificate & Project Report",
}

FORM_CODE_RE = re.compile(r"Form\s*Code\s*:\s*MER-?\s*0?\s*(\d{1,2})", re.I)


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _element_text(element: ET.Element) -> str:
    parts: list[str] = []
    for node in element.iter():
        if _local(node.tag) == "t" and node.text:
            parts.append(node.text)
    return " ".join(parts)


def _detect_form_code(text: str) -> str | None:
    match = FORM_CODE_RE.search(text.replace("\xa0", " "))
    if not match:
        return None
    return f"{int(match.group(1)):02d}"


def _register_namespaces(document_xml: str) -> None:
    for match in re.finditer(r'xmlns:([A-Za-z0-9_]+)="([^"]+)"', document_xml):
        ET.register_namespace(match.group(1), match.group(2))
    # Default Word namespace often has no prefix on root children in OOXML.
    ET.register_namespace("w", W_NS)


def _split_document_xml(document_xml: str) -> list[tuple[str, str]]:
    _register_namespaces(document_xml)
    root = ET.fromstring(document_xml)
    body = root.find(f"{W}body")
    if body is None:
        raise RuntimeError("Could not locate document body.")

    children = list(body)
    sect_pr = None
    content_nodes: list[ET.Element] = []
    for child in children:
        if _local(child.tag) == "sectPr":
            sect_pr = child
        else:
            content_nodes.append(child)

    form_starts: list[tuple[int, str]] = []
    for index, node in enumerate(content_nodes):
        code = _detect_form_code(_element_text(node))
        if code and code in FORM_TITLES:
            form_starts.append((index, code))

    # Deduplicate while keeping first occurrence of each code.
    seen: set[str] = set()
    unique_starts: list[tuple[int, str]] = []
    for index, code in form_starts:
        if code in seen:
            continue
        seen.add(code)
        unique_starts.append((index, code))

    if len(unique_starts) < len(FORM_TITLES):
        found = ", ".join(code for _index, code in unique_starts) or "(none)"
        raise RuntimeError(f"Expected MER-01..10. Found: {found}")

    sections: list[tuple[str, str]] = []
    for position, (start_index, code) in enumerate(unique_starts):
        end_index = unique_starts[position + 1][0] if position + 1 < len(unique_starts) else len(content_nodes)
        chunk_nodes = content_nodes[start_index:end_index]
        if not chunk_nodes:
            raise RuntimeError(f"Empty section for MER-{code}")

        new_root = ET.fromstring(document_xml)
        new_body = new_root.find(f"{W}body")
        if new_body is None:
            raise RuntimeError("Could not rebuild document body.")
        for child in list(new_body):
            new_body.remove(child)
        for node in chunk_nodes:
            new_body.append(node)
        if sect_pr is not None:
            new_body.append(sect_pr)

        sections.append((code, ET.tostring(new_root, encoding="unicode")))

    return sections


def _build_docx(source_docx: Path, document_xml: str, target_docx: Path) -> None:
    target_docx.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_docx, "r") as source, zipfile.ZipFile(target_docx, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "word/document.xml":
                data = document_xml.encode("utf-8")
            target.writestr(item, data)


def main() -> None:
    if not SOURCE_DOCX.exists():
        raise SystemExit(f"Source file not found: {SOURCE_DOCX}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("mer-*.docx"):
        old.unlink()

    with zipfile.ZipFile(SOURCE_DOCX, "r") as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")

    sections = _split_document_xml(document_xml)
    manifest: list[str] = []

    for code, section_xml in sections:
        title = FORM_TITLES.get(code, f"MER Form {code}")
        filename = f"mer-{code}.docx"
        target = OUTPUT_DIR / filename
        _build_docx(SOURCE_DOCX, section_xml, target)
        manifest.append(
            "    {\n"
            f'        "code": "MER-{code}",\n'
            f'        "title": "{title}",\n'
            f'        "filename": "{filename}",\n'
            f'        "url": "/static/uploads/forms/{filename}",\n'
            "    },"
        )
        with zipfile.ZipFile(target) as check:
            xml = check.read("word/document.xml").decode("utf-8")
        open_tbl = len(re.findall(r"<w:tbl(?:\s|>)", xml))
        close_tbl = xml.count("</w:tbl>")
        print(f"Wrote {filename} ({title}) tables {open_tbl}/{close_tbl}")

    CATALOG_PATH.write_text("ATL_MER_FORMS = [\n" + "\n".join(manifest) + "\n]\n", encoding="utf-8")
    print(f"Wrote catalog with {len(sections)} forms.")


if __name__ == "__main__":
    main()
