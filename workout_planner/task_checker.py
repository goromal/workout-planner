import logging
import sys
from datetime import datetime, timedelta

from easy_google_auth.auth import getRateLimitedGoogleService
from workout_planner.defaults import WorkoutPlannerDefaults as WPD


class TaskChecker:
    """Checks Google Tasks for workout completion status."""

    def __init__(self, **kwargs):
        self.task_secrets_file = WPD.getKwargsOrDefault("task_secrets_file", **kwargs)
        self.task_refresh_token = WPD.getKwargsOrDefault("task_refresh_token", **kwargs)
        self.task_list_id = WPD.getKwargsOrDefault("task_list_id", **kwargs)
        self.enable_logging = WPD.getKwargsOrDefault("enable_logging", **kwargs)

        if self.enable_logging:
            logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
            logging.getLogger().setLevel(logging.INFO)

        self.service = None
        try:
            self.service = getRateLimitedGoogleService(
                "tasks",
                "v1",
                self.task_secrets_file,
                self.task_refresh_token,
                headless=True,
                max_rate_per_sec=1.0,
            )
        except Exception as e:
            raise Exception(f"Failed to initialize Google Tasks service: {e}")

    def _date_to_google_date(self, date_time):
        """Convert datetime to Google Tasks date format."""
        return f"{date_time.strftime('%Y-%m-%d')}T23:59:59.000Z"

    def check_previous_day_workout(self, prefix="P0: Workout"):
        """
        Check if previous day's workout task exists (not completed).

        Args:
            prefix: The prefix to search for in task titles (default: "P0: Workout")

        Returns:
            bool: True if workout was completed (task deleted/not found),
                  False if workout was missed (task still exists)
        """
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = self._date_to_google_date(yesterday - timedelta(days=1))
        yesterday_end = self._date_to_google_date(yesterday + timedelta(days=1))

        try:
            # Query tasks from yesterday
            results = (
                self.service.tasks()
                .list(
                    tasklist=self.task_list_id,
                    maxResults=100,
                    showCompleted=False,  # Only show incomplete tasks
                    dueMin=yesterday_start,
                    dueMax=yesterday_end,
                )
                .execute()
            )

            items = results.get("items", [])

            # Check if any task matches the workout prefix
            for item in items:
                if item.get("title", "").startswith(prefix):
                    # Task still exists = workout was not completed
                    if self.enable_logging:
                        logging.info(
                            f"Found incomplete workout task from yesterday: {item['title']}"
                        )
                    return False

            # No workout task found = it was completed (deleted)
            if self.enable_logging:
                logging.info("Yesterday's workout task not found - assuming completed")

            return True

        except Exception as e:
            if self.enable_logging:
                logging.error(f"Error checking previous day's workout: {e}")
            # Default to assuming it was completed to avoid blocking
            return True

    def create_workout_task(self, title, notes, date=None):
        """
        Create a workout task in Google Tasks.

        Args:
            title: Task title (should start with "P0: Workout:")
            notes: Detailed workout description
            date: Due date (defaults to today)

        Returns:
            dict: Created task object
        """
        if date is None:
            date = datetime.now()

        fdate = f"{date.strftime('%Y-%m-%d')}T00:00:00.000Z"

        body = {
            "status": "needsAction",
            "kind": "tasks#task",
            "title": title,
            "notes": notes,
            "due": fdate,
        }

        if self.enable_logging:
            logging.info(f"Creating workout task: {title} (due {date.strftime('%Y-%m-%d')})")

        try:
            result = (
                self.service.tasks()
                .insert(tasklist=self.task_list_id, body=body)
                .execute()
            )
            return result
        except Exception as e:
            raise Exception(f"Failed to create workout task: {e}")
