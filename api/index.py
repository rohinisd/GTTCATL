import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STUDENT_DASHBOARD_DIR = PROJECT_ROOT / "StudentDashboard"

sys.path.insert(0, str(STUDENT_DASHBOARD_DIR))

from app.main import app  # noqa: E402
