import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from anthropic import Anthropic

from workout_planner.defaults import WorkoutPlannerDefaults as WPD


class WorkoutPlanner:
    """Generates AI-powered workout plans using Claude API."""

    def __init__(self, **kwargs):
        self.config_file = WPD.getKwargsOrDefault("config_file", **kwargs)
        self.history_file = WPD.getKwargsOrDefault("history_file", **kwargs)
        self.api_key_file = WPD.getKwargsOrDefault("claude_api_key_file", **kwargs)
        self.enable_logging = WPD.getKwargsOrDefault("enable_logging", **kwargs)

        if self.enable_logging:
            logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
            logging.getLogger().setLevel(logging.INFO)

        # Load Claude API key
        if not os.path.exists(self.api_key_file):
            raise Exception(f"Claude API key file not found: {self.api_key_file}")

        with open(self.api_key_file, "r") as f:
            api_key = f.read().strip()

        self.client = Anthropic(api_key=api_key)

    def _load_config(self):
        """Load user workout configuration."""
        if not os.path.exists(self.config_file):
            raise Exception(
                f"Config file not found: {self.config_file}\n"
                f"Please create it with your workout preferences."
            )

        with open(self.config_file, "r") as f:
            return yaml.safe_load(f)

    def _load_history(self, days=30):
        """Load recent workout history."""
        if not os.path.exists(self.history_file):
            if self.enable_logging:
                logging.info("No history file found, starting fresh")
            return []

        history = []
        cutoff_date = datetime.now() - timedelta(days=days)

        with open(self.history_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
                    if entry_date >= cutoff_date:
                        history.append(entry)

        return sorted(history, key=lambda x: x["date"])

    def _save_history_entry(self, date, completed, workout, notes=""):
        """Append entry to workout history."""
        # Ensure directory exists
        Path(self.history_file).parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "date": date.strftime("%Y-%m-%d"),
            "completed": completed,
            "workout": workout,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
        }

        with open(self.history_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        if self.enable_logging:
            logging.info(f"Logged workout entry for {entry['date']}")

    def _build_prompt(self, config, history, yesterday_completed):
        """Build the prompt for Claude API."""
        # Format config
        config_str = yaml.dump(config, default_flow_style=False)

        # Format recent history (last 7 days)
        recent_history = history[-7:] if len(history) > 7 else history
        history_str = ""
        for entry in recent_history:
            status = "✓ Completed" if entry["completed"] else "✗ Missed"
            history_str += f"\n- {entry['date']}: {status}\n  {entry['workout']}\n"

        # Build prompt
        prompt = f"""You are a professional strength training coach. Generate a workout plan for today based on the user's configuration and workout history.

USER CONFIGURATION:
{config_str}

RECENT WORKOUT HISTORY (last 7 days):
{history_str if history_str else "No recent history"}

YESTERDAY'S WORKOUT STATUS:
{"Completed - Good job! Consider progression." if yesterday_completed else "Missed - Consider adjusting today's plan if needed."}

INSTRUCTIONS:
1. Generate a specific, actionable workout plan for today
2. Consider the user's goals, constraints, and available equipment
3. Follow the specified training split if provided
4. Ensure appropriate progression based on history
5. Keep the workout realistic (30-45 min as specified in constraints)
6. If yesterday was missed, don't overcompensate - stay consistent

OUTPUT FORMAT:
Provide two parts:

1. SHORT TITLE (max 40 chars): A brief description for the task title
   Format: "Workout: [type/focus]"
   Example: "Workout: Push Day - Chest Focus"
   NOTE: Do NOT include "P0:" prefix - this will be added automatically

2. WORKOUT DETAILS: Full workout description with clear structure for Google Tasks.
   Format as plain text with clear sections separated by blank lines:

   WARMUP
   - Exercise 1: details
   - Exercise 2: details

   MAIN WORKOUT
   - Exercise 1: sets x reps @ weight
   - Exercise 2: sets x reps @ weight
   - Exercise 3: sets x reps @ weight

   COOLDOWN
   - Exercise 1: details
   - Exercise 2: details

   NOTES
   - Any coaching cues or tips

   Keep formatting simple (no markdown, no headers with #, no bold/italic).
   Use bullet points (-) and blank lines for structure.
   Be concise but specific with exercise details.

Separate these with "---" on its own line.
"""

        return prompt

    def _count_workouts_this_week(self, history):
        """Count completed workouts this week (Monday-Sunday)."""
        today = datetime.now()
        # Get Monday of this week
        monday = today - timedelta(days=today.weekday())
        monday_str = monday.strftime("%Y-%m-%d")

        completed_this_week = sum(
            1 for entry in history
            if entry["date"] >= monday_str and entry["completed"]
        )

        return completed_this_week

    def _has_carryover_workout(self):
        """Check if there's an incomplete workout from a previous day."""
        # This will be checked by task_checker in the CLI
        # For now, return False (will be overridden in CLI)
        return False

    def generate_workout(self, yesterday_completed=None):
        """
        Generate today's workout plan.

        Args:
            yesterday_completed: Boolean indicating if yesterday's workout was done.
                               If None, will attempt to determine from history.

        Returns:
            tuple: (task_title, workout_details) or None if no workout needed
        """
        config = self._load_config()
        history = self._load_history()

        # Determine yesterday's completion status
        if yesterday_completed is None:
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_str = yesterday.strftime("%Y-%m-%d")

            # Check if yesterday's workout was logged as completed
            yesterday_completed = any(
                entry["date"] == yesterday_str and entry["completed"]
                for entry in history
            )

            if self.enable_logging:
                status = "completed" if yesterday_completed else "not completed/missed"
                logging.info(f"Yesterday's workout was {status}")

        # Check if we should generate a workout
        # Get target frequency from config
        target_frequency = config.get("preferences", {}).get("frequency_per_week", 4)
        workouts_this_week = self._count_workouts_this_week(history)

        if self.enable_logging:
            logging.info(f"Workouts completed this week: {workouts_this_week}/{target_frequency}")

        # Don't generate if we've hit the target for the week
        if workouts_this_week >= target_frequency:
            if self.enable_logging:
                logging.info(f"Weekly target reached ({workouts_this_week}/{target_frequency}). No new workout generated.")
            return None

        # Build prompt and call Claude API
        prompt = self._build_prompt(config, history, yesterday_completed)

        # Get model from config, default to haiku if not specified
        model = config.get("api", {}).get("model", "claude-haiku-4-5-20251001")

        if self.enable_logging:
            logging.info(f"Calling Claude API to generate workout plan (model: {model})...")

        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=2048,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            # Parse response
            if "---" in response_text:
                parts = response_text.split("---", 1)
                task_title = parts[0].strip()
                workout_details = parts[1].strip()
            else:
                # Fallback if format isn't followed
                task_title = "Workout: Generated Plan"
                workout_details = response_text

            # Clean up title - remove markdown headers and extra formatting
            task_title = task_title.replace("#", "").strip()

            # Ensure title starts with P0: (but not duplicate)
            if not task_title.startswith("P0:"):
                task_title = f"P0: {task_title}"

            # Remove duplicate P0: prefix if it exists
            if task_title.count("P0:") > 1:
                # Remove all P0: and add one at the start
                task_title = "P0: " + task_title.replace("P0:", "").strip()

            # Ensure reasonable title length
            if len(task_title) > 100:
                task_title = task_title[:97] + "..."

            return task_title, workout_details

        except Exception as e:
            error_str = str(e)
            # Check if this is a credit/quota depletion error
            if ("credit balance is too low" in error_str or
                "insufficient_quota" in error_str or
                "quota" in error_str.lower()):
                raise Exception(
                    "CLAUDE_API_QUOTA_EXCEEDED: Your Claude API quota has been exceeded. "
                    "Please refill your tokens to continue using the workout planner."
                )
            raise Exception(f"Failed to generate workout with Claude API: {e}")

    def log_workout(self, workout_title, workout_details, completed=False, notes=""):
        """Log a workout to history."""
        today = datetime.now()
        full_workout = f"{workout_title}\n\n{workout_details}"
        self._save_history_entry(today, completed, full_workout, notes)
