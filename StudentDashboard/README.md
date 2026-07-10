# GTTC Student Dashboard & LMS

Separate starter app for trainer, school, student, and LMS workflows.

This project intentionally lives outside `DoNotUse` and uses its own SQLite database:

```text
StudentDashboard/student_dashboard.db
```

Run locally from this folder:

```powershell
..\.venv-donotuse-run\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Open:

```text
http://127.0.0.1:8001/dashboard
```
