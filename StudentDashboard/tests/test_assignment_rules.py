import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import _join_assigned_schools, _split_assigned_schools


class AssignmentRulesTest(unittest.TestCase):
    def test_join_and_split_preserve_unique_schools(self):
        joined = _join_assigned_schools("1", "2", "1", "3")
        self.assertEqual(joined, "1, 2, 3")

        parts = _split_assigned_schools(joined)
        self.assertEqual(parts, ["1", "2", "3"])


if __name__ == "__main__":
    unittest.main()
