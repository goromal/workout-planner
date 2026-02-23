import os


class WorkoutPlannerDefaults(object):
    """Default configuration values for workout planner."""

    CONFIG_FILE = os.path.expanduser("~/configs/workout-config.yaml")
    HISTORY_FILE = os.path.expanduser("~/data/workout/history.jsonl")
    CLAUDE_API_KEY_FILE = os.path.expanduser("~/secrets/claude/api_key.txt")

    # Task-tools defaults (inherited from task-tools package)
    TASK_SECRETS_FILE = os.path.expanduser("~/secrets/google/client_secret.json")
    TASK_REFRESH_TOKEN = os.path.expanduser("~/secrets/google/refresh_token.json")
    TASK_LIST_ID = "MTMzOTU3MTU1MTY2OTc1MDQwOTc6MDow"

    ENABLE_LOGGING = False

    @staticmethod
    def getKwargsOrDefault(key, **kwargs):
        """Get value from kwargs or return default."""
        if key in kwargs:
            return kwargs[key]
        return getattr(WorkoutPlannerDefaults, key.upper(), None)
