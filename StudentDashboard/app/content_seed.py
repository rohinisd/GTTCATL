import importlib.util
from pathlib import Path

from app.models import Course, Lesson


def _load_donotuse_projects():
    root = Path(__file__).resolve().parents[2]
    source = root / "DoNotUse" / "app" / "core" / "seed_projects.py"
    if not source.exists():
        return []

    spec = importlib.util.spec_from_file_location("donotuse_seed_projects", source)
    if spec is None or spec.loader is None:
        return []

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "PROJECTS", [])


def seed_lms_content(db):
    projects = _load_donotuse_projects()
    if not projects:
        return

    existing_titles = {row[0] for row in db.query(Course.title).all()}

    for exp_no, name, items in projects:
        title = f"Experiment {exp_no}: {name}"
        if title in existing_titles:
            continue

        course = Course(
            title=title,
            description=(
                "Imported from the GTTC ATL experiment source list. "
                "This course can be edited, expanded, or deleted from the LMS module later."
            ),
            level="ATL Experiment",
        )
        db.add(course)
        db.flush()

        db.add(
            Lesson(
                course_id=course.id,
                title="Experiment Overview",
                content_type="article",
                content_body=(
                    f"Experiment No: {exp_no}\n"
                    f"Title: {name}\n\n"
                    "Use this lesson as the editable overview/instructions page for the experiment."
                ),
                sort_order=1,
            )
        )

        material_lines = [f"{index}. {item_name} - {quantity}" for index, (item_name, quantity) in enumerate(items, start=1)]
        db.add(
            Lesson(
                course_id=course.id,
                title="Bill of Materials",
                content_type="materials",
                content_body="\n".join(material_lines),
                sort_order=2,
            )
        )

    db.commit()
