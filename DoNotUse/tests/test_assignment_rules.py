import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.admin import get_available_school_ids


class AssignmentRulesTests(unittest.TestCase):
    def test_available_school_ids_exclude_already_assigned_schools(self):
        school_ids = [101, 102, 103, 104]
        assigned_school_ids = {102, 104}

        self.assertEqual(get_available_school_ids(school_ids, assigned_school_ids), [101, 103])


if __name__ == "__main__":
    unittest.main()
