import sys
import types
import unittest
from datetime import datetime
from unittest import mock

# task_checker imports easy_google_auth at module level; use a stand-in where
# it isn't installed.
_ega = types.ModuleType("easy_google_auth")
_ega_auth = types.ModuleType("easy_google_auth.auth")
_ega_auth.getRateLimitedGoogleService = mock.MagicMock()
_ega.auth = _ega_auth
sys.modules.setdefault("easy_google_auth", _ega)
sys.modules.setdefault("easy_google_auth.auth", _ega_auth)

from workout_planner import task_checker  # noqa: E402

MONDAY = datetime(2026, 11, 23, 5, 30)


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return MONDAY


class TestCheckPreviousDayWorkout(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(task_checker, "datetime", FixedDatetime)
        patcher.start()
        self.addCleanup(patcher.stop)
        with mock.patch.object(task_checker, "getRateLimitedGoogleService"):
            self.checker = task_checker.TaskChecker()
        self.service = mock.MagicMock()
        self.checker.service = self.service

    def set_items(self, items):
        self.service.tasks().list().execute.return_value = {"items": items}
        self.service.tasks().list.reset_mock()

    def test_window_reaches_a_week_ahead(self):
        self.set_items([])
        self.checker.check_previous_day_workout()
        kwargs = self.service.tasks().list.call_args.kwargs
        self.assertEqual(kwargs["dueMin"], "2026-10-24T23:59:59.000Z")
        self.assertEqual(kwargs["dueMax"], "2026-11-30T23:59:59.000Z")
        self.assertFalse(kwargs["showCompleted"])

    def test_postponed_open_workout_is_a_carryover(self):
        self.set_items(
            [{"title": "P0: Workout: Push Day", "due": "2026-11-26T00:00:00.000Z"}]
        )
        self.assertFalse(self.checker.check_previous_day_workout())

    def test_no_workout_task_means_no_carryover(self):
        self.set_items([{"title": "P1: Something else", "due": "2026-11-23T00:00:00.000Z"}])
        self.assertTrue(self.checker.check_previous_day_workout())


if __name__ == "__main__":
    unittest.main()
