import unittest
from datetime import datetime

from workout_planner.schedule import (
    is_rest_day,
    parse_rest_days,
    training_days_remaining,
)

SATURDAY = datetime(2026, 11, 21)
SUNDAY = datetime(2026, 11, 22)
MONDAY = datetime(2026, 11, 23)


class TestParseRestDays(unittest.TestCase):
    def test_missing_or_empty_is_no_rest_days(self):
        for config in [
            None,
            {},
            {"preferences": None},
            {"preferences": {}},
            {"preferences": {"rest_days": None}},
            {"preferences": {"rest_days": []}},
        ]:
            with self.subTest(config=config):
                self.assertEqual(parse_rest_days(config), frozenset())

    def test_names_are_case_and_whitespace_insensitive(self):
        config = {"preferences": {"rest_days": ["Sunday", " saturday "]}}
        self.assertEqual(parse_rest_days(config), frozenset({5, 6}))

    def test_invalid_values_raise(self):
        for rest_days in [["sundy"], [6], "sunday", {"sunday": True}]:
            with self.subTest(rest_days=rest_days):
                with self.assertRaises(ValueError):
                    parse_rest_days({"preferences": {"rest_days": rest_days}})

    def test_unknown_name_error_lists_valid_names(self):
        with self.assertRaises(ValueError) as cm:
            parse_rest_days({"preferences": {"rest_days": ["sundy"]}})
        self.assertIn("'sundy'", str(cm.exception))
        self.assertIn("sunday", str(cm.exception))


class TestTrainingDaysRemaining(unittest.TestCase):
    def test_with_sunday_rest(self):
        rest_days = frozenset({6})
        self.assertEqual(training_days_remaining(SATURDAY, rest_days), 1)
        self.assertEqual(training_days_remaining(MONDAY, rest_days), 6)
        self.assertEqual(training_days_remaining(SUNDAY, rest_days), 0)

    def test_without_rest_days_matches_old_formula(self):
        for today in [SATURDAY, SUNDAY, MONDAY]:
            with self.subTest(today=today):
                self.assertEqual(
                    training_days_remaining(today, frozenset()), 7 - today.weekday()
                )


class TestIsRestDay(unittest.TestCase):
    def test_is_rest_day(self):
        rest_days = frozenset({6})
        self.assertTrue(is_rest_day(SUNDAY, rest_days))
        self.assertFalse(is_rest_day(MONDAY, rest_days))
        self.assertFalse(is_rest_day(SUNDAY, frozenset()))


if __name__ == "__main__":
    unittest.main()
