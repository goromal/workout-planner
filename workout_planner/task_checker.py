import logging
import sys
from datetime import datetime, timedelta

from easy_google_auth.auth import getRateLimitedGoogleService
from workout_planner.defaults import WorkoutPlannerDefaults as WPD


class TaskChecker:
    """Checks Google Tasks for workout completion status."""

    def _check_valid_interface(func):
        def wrapper(self, *args, **kwargs):
            if self.service is None:
                raise Exception(
                    "Tasks interface not initialized properly; check your secrets"
                )
            return func(self, *args, **kwargs)

        return wrapper

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
        except:
            pass  # Service will be None, checked later

    def _date_to_google_date(self, date_time):
        """Convert datetime to Google Tasks date format."""
        return f"{date_time.strftime('%Y-%m-%d')}T23:59:59.000Z"

    @_check_valid_interface
    def check_previous_day_workout(self, prefix="P0: Workout"):
        """
        Check if there are ANY incomplete workout tasks (carryover workouts).

        This checks for incomplete workout tasks from ANY previous day, not just yesterday.
        The presence of any incomplete workout task means we should not generate a new one.

        Args:
            prefix: The prefix to search for in task titles (default: "P0: Workout")

        Returns:
            bool: True if no carryover workouts exist (all previous workouts completed),
                  False if there's a carryover workout (incomplete task exists)
        """
        today = datetime.now()
        # Check from 30 days ago to yesterday
        start_date = today - timedelta(days=30)
        yesterday = today - timedelta(days=1)

        start_date_str = self._date_to_google_date(start_date)
        yesterday_end_str = self._date_to_google_date(yesterday + timedelta(days=1))

        try:
            # Query all incomplete tasks up to yesterday
            results = (
                self.service.tasks()
                .list(
                    tasklist=self.task_list_id,
                    maxResults=100,
                    showCompleted=False,  # Only show incomplete tasks
                    dueMin=start_date_str,
                    dueMax=yesterday_end_str,
                )
                .execute()
            )

            items = results.get("items", [])

            # Check if any task matches the workout prefix
            for item in items:
                if item.get("title", "").startswith(prefix):
                    # Task still exists = there's a carryover workout
                    if self.enable_logging:
                        logging.info(
                            f"Found carryover workout task: {item['title']} (due: {item.get('due', 'unknown')})"
                        )
                    return False

            # No workout tasks found = all previous workouts completed
            if self.enable_logging:
                logging.info("No carryover workout tasks found - all previous workouts completed")

            return True

        except Exception as e:
            if self.enable_logging:
                logging.error(f"Error checking for carryover workouts: {e}")
            # Default to assuming no carryover to avoid blocking (conservative approach)
            return True

    @_check_valid_interface
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
