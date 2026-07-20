import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main as app_main
from app import models
from app.database import Base


class TrainerSchoolAssignmentTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def _make_school(self, db, name):
        school = models.School(name=name, district="Test District")
        db.add(school)
        db.commit()
        db.refresh(school)
        return school

    def _make_trainer(self, db, name, email, assigned_school=None, is_active=True):
        trainer = models.Trainer(
            name=name,
            email=email,
            role="atl_trainer",
            assigned_school=assigned_school,
            is_active=is_active,
        )
        db.add(trainer)
        db.commit()
        db.refresh(trainer)
        return trainer

    def test_assignment_map_only_contains_assigned_schools(self):
        with self.SessionLocal() as db:
            school_a = self._make_school(db, "School A")
            school_b = self._make_school(db, "School B")
            trainer = self._make_trainer(db, "Trainer One", "trainer.one@example.com", assigned_school=str(school_a.id))

            assignment_map = app_main._active_school_assignment_map(db)

            self.assertEqual(assignment_map, {school_a.id: trainer.id})
            self.assertNotIn(school_b.id, assignment_map)

    def test_inactive_trainer_school_is_not_counted_as_assigned(self):
        with self.SessionLocal() as db:
            school = self._make_school(db, "School A")
            self._make_trainer(db, "Inactive Trainer", "inactive@example.com", assigned_school=str(school.id), is_active=False)

            assignment_map = app_main._active_school_assignment_map(db)

            self.assertEqual(assignment_map, {})

    def test_validate_assignment_blocks_school_already_taken_by_another_trainer(self):
        with self.SessionLocal() as db:
            school = self._make_school(db, "School A")
            other_trainer = self._make_trainer(db, "Other Trainer", "other@example.com", assigned_school=str(school.id))

            conflict = app_main._validate_trainer_assignment_selection(db, [str(school.id)])

            self.assertIn(other_trainer.name, conflict)

    def test_validate_assignment_allows_current_trainer_to_keep_own_school(self):
        with self.SessionLocal() as db:
            school = self._make_school(db, "School A")
            trainer = self._make_trainer(db, "Trainer One", "trainer.one@example.com", assigned_school=str(school.id))

            conflict = app_main._validate_trainer_assignment_selection(db, [str(school.id)], current_trainer_id=trainer.id)

            self.assertIsNone(conflict)

    def test_validate_assignment_allows_unassigned_school(self):
        with self.SessionLocal() as db:
            school = self._make_school(db, "School A")

            conflict = app_main._validate_trainer_assignment_selection(db, [str(school.id)])

            self.assertIsNone(conflict)


if __name__ == "__main__":
    unittest.main()
