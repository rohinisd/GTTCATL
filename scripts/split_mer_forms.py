"""Split All_ATL_MER_Forms.docx into individual downloadable form files."""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path


SOURCE_DOCX = Path(r"C:\Users\rohin\OneDrive\Documents\Downloads\All_ATL_MER_Forms.docx")
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "StudentDashboard" / "app" / "static" / "uploads" / "forms"
CATALOG_PATH = Path(__file__).resolve().parents[1] / "StudentDashboard" / "app" / "forms_catalog.py"

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


def _find_form_markers(body_content: str) -> list[tuple[int, str]]:
    markers: list[tuple[int, str]] = []

    for match in re.finditer(r"Form Code: MER-(\d{2})</w:t>", body_content):
        markers.append((match.start(), match.group(1)))

    for match in re.finditer(
        r"Form Code: MER-0</w:t></w:r><w:r>[\s\S]{0,240}?<w:t>(\d)</w:t>",
        body_content,
    ):
        markers.append((match.start(), f"0{match.group(1)}"))

    for match in re.finditer(
        r"Form Code: MER-1</w:t></w:r><w:r>[\s\S]{0,240}?<w:t>0</w:t>",
        body_content,
    ):
        markers.append((match.start(), "10"))

    for match in re.finditer(
        r"Form Code: MER-</w:t></w:r><w:r>[\s\S]{0,240}?<w:t>10</w:t>",
        body_content,
    ):
        markers.append((match.start(), "10"))

    markers = sorted({position: code for position, code in markers}.items())
    return markers


def _form_start(body_content: str, marker_position: int) -> int:
    table_start = body_content.rfind("<w:tbl", 0, marker_position)
    return table_start if table_start >= 0 else marker_position


def _split_document_xml(document_xml: str) -> list[tuple[str, str]]:
    body_match = re.search(r"(<w:body>)(.*)(</w:body>)", document_xml, flags=re.S)
    if not body_match:
        raise RuntimeError("Could not locate document body.")

    body_open, body_content, body_close = body_match.groups()
    markers = _find_form_markers(body_content)
    if not markers:
        raise RuntimeError("No MER form markers found.")

    sections: list[tuple[str, str]] = []
    for index, (position, code) in enumerate(markers):
        start = _form_start(body_content, position)
        end = _form_start(body_content, markers[index + 1][0]) if index + 1 < len(markers) else len(body_content)
        chunk = body_content[start:end]
        chunk = re.sub(r"<w:sectPr[\s\S]*?</w:sectPr>", "", chunk)
        sections.append((code, f"{body_open}{chunk}{body_close}"))

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

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
        print(f"Wrote {filename} ({title})")

    CATALOG_PATH.write_text("ATL_MER_FORMS = [\n" + "\n".join(manifest) + "\n]\n", encoding="utf-8")
    print(f"Wrote catalog with {len(sections)} forms.")


if __name__ == "__main__":
    main()
