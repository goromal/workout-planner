"""
Tests for the `generate` command's rest-day, reporting, and weekly-target flow.

Claude, Google Tasks, and the tactical server are replaced with mocks, and the
clock is fixed, so these run without network access or credentials.
"""

import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
from unittest import mock

import yaml

# cli imports planner and task_checker, which import these at module level.
# Stand-ins let the tests run where they aren't installed.
_anthropic = types.ModuleType("anthropic")
_anthropic.Anthropic = mock.MagicMock
sys.modules.setdefault("anthropic", _anthropic)
_ega = types.ModuleType("easy_google_auth")
_ega_auth = types.ModuleType("easy_google_auth.auth")
_ega_auth.getRateLimitedGoogleService = mock.MagicMock()
_ega.auth = _ega_auth
sys.modules.setdefault("easy_google_auth", _ega)
sys.modules.setdefault("easy_google_auth.auth", _ega_auth)

from click.testing import CliRunner  # noqa: E402

from workout_planner import cli  # noqa: E402
from workout_planner.task_checker import TaskChecker  # noqa: E402

SATURDAY = datetime(2026, 11, 21, 5, 30)
SUNDAY = datetime(2026, 11, 22, 5, 30)
MONDAY = datetime(2026, 11, 23, 5, 30)


def _fixed_datetime(now):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    return FixedDatetime


class TestGenerate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.api_key_file = os.path.join(self.tmp.name, "api_key.txt")
        with open(self.api_key_file, "w") as f:
            f.write("test-key")
        self.config_file = os.path.join(self.tmp.name, "config.yaml")
        self.history_file = os.path.join(self.tmp.name, "history.jsonl")

    def run_generate(
        self,
        today,
        rest_days=None,
        carryover=False,
        completed_this_week=0,
        args=(),
    ):
        preferences = {"frequency_per_week": 4}
        if rest_days is not None:
            preferences["rest_days"] = rest_days
        with open(self.config_file, "w") as f:
            yaml.safe_dump({"preferences": preferences}, f)

        fixed = _fixed_datetime(today)
        anthropic_client = mock.MagicMock()
        anthropic_client.messages.create.return_value.content = [
            mock.MagicMock(text="Workout: Push Day\n---\nMAIN WORKOUT\n- Push-ups")
        ]
        self.report = mock.MagicMock()
        self.create_task = mock.MagicMock()
        self.messages_create = anthropic_client.messages.create

        patches = [
            mock.patch.object(cli, "datetime", fixed),
            mock.patch("workout_planner.planner.datetime", fixed),
            mock.patch("workout_planner.planner.Anthropic", return_value=anthropic_client),
            mock.patch("workout_planner.task_checker.getRateLimitedGoogleService"),
            mock.patch.object(cli, "report_workout_to_tactical", self.report),
            mock.patch.object(
                TaskChecker, "check_previous_day_workout", return_value=not carryover
            ),
            mock.patch.object(
                TaskChecker,
                "count_completed_workouts_this_week",
                return_value=completed_this_week,
            ),
            mock.patch.object(TaskChecker, "create_workout_task", self.create_task),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        return CliRunner().invoke(
            cli.cli,
            [
                "--config-file", self.config_file,
                "--history-file", self.history_file,
                "--claude-api-key-file", self.api_key_file,
                "generate",
                *args,
            ],
        )

    def prompt(self):
        self.messages_create.assert_called_once()
        return self.messages_create.call_args.kwargs["messages"][0]["content"]

    def test_sunday_rest_day_dry_run_makes_no_api_call(self):
        result = self.run_generate(SUNDAY, rest_days=["sunday"], args=["--dry-run"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Today is a rest day (Sunday)", result.output)
        self.messages_create.assert_not_called()
        self.create_task.assert_not_called()
        self.report.assert_not_called()

    def test_sunday_rest_day_still_reports_saturday(self):
        result = self.run_generate(SUNDAY, rest_days=["sunday"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.report.assert_called_once()
        self.assertEqual(self.report.call_args.args[1].date(), SATURDAY.date())
        self.messages_create.assert_not_called()
        self.create_task.assert_not_called()

    def test_rest_day_message_wins_over_carryover(self):
        result = self.run_generate(SUNDAY, rest_days=["sunday"], carryover=True)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Today is a rest day", result.output)
        self.assertNotIn("Carryover workout detected", result.output)

    def test_monday_does_not_report_rest_sunday(self):
        result = self.run_generate(MONDAY, rest_days=["sunday"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.report.assert_not_called()
        self.assertIn("Yesterday (Sunday) was a rest day", result.output)
        prompt = self.prompt()
        self.assertIn("Yesterday was a scheduled rest day.", prompt)
        self.assertNotIn("Completed - Good job!", prompt)
        self.assertIn("7. The user does not train on: Sunday.", prompt)
        self.create_task.assert_called_once()

    def test_forced_status_overrides_rest_day_skip(self):
        result = self.run_generate(
            MONDAY, rest_days=["sunday"], args=["--force-yesterday-completed", "True"]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.report.assert_called_once()
        _, date, completed, _ = self.report.call_args.args
        self.assertEqual(date.date(), SUNDAY.date())
        self.assertTrue(completed)
        prompt = self.prompt()
        self.assertIn("Completed - Good job! Consider progression.", prompt)
        self.assertNotIn("scheduled rest day", prompt)

    def test_saturday_on_track_counts_only_training_days(self):
        # 2 done + Saturday is 3 < 4. The old 7 - weekday() math counted Sunday
        # too and called this on track.
        result = self.run_generate(
            SATURDAY, rest_days=["sunday"], carryover=True, completed_this_week=2
        )
        self.assertEqual(result.exit_code, 0, result.output)
        _, _, completed, on_track = self.report.call_args.args
        self.assertFalse(completed)
        self.assertFalse(on_track)

    def test_unset_rest_days_keeps_old_behavior(self):
        result = self.run_generate(MONDAY)
        self.assertEqual(result.exit_code, 0, result.output)
        self.report.assert_called_once()
        self.assertEqual(self.report.call_args.args[1].date(), SUNDAY.date())
        prompt = self.prompt()
        self.assertIn("Completed - Good job! Consider progression.", prompt)
        self.assertIn(
            "6. If yesterday was missed, don't overcompensate - stay consistent\n\nOUTPUT FORMAT",
            prompt,
        )
        self.assertNotIn("does not train on", prompt)

    def test_unset_rest_days_saturday_on_track_unchanged(self):
        # Without rest days, Saturday and Sunday both remain: 2 + 2 >= 4.
        result = self.run_generate(SATURDAY, carryover=True, completed_this_week=2)
        self.assertEqual(result.exit_code, 0, result.output)
        _, _, _, on_track = self.report.call_args.args
        self.assertTrue(on_track)

    def test_bad_rest_days_fails_before_reporting(self):
        result = self.run_generate(MONDAY, rest_days=["sundy"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Unknown rest day 'sundy'", result.output)
        self.report.assert_not_called()
        self.messages_create.assert_not_called()

    def test_weekly_target_met_skips_api_call(self):
        result = self.run_generate(MONDAY, completed_this_week=4)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Weekly workout target reached", result.output)
        self.messages_create.assert_not_called()
        self.create_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
