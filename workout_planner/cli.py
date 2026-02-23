import click
import sys
import traceback

from workout_planner.defaults import WorkoutPlannerDefaults as WPD
from workout_planner.planner import WorkoutPlanner
from workout_planner.task_checker import TaskChecker


@click.group()
@click.pass_context
@click.option(
    "--config-file",
    "config_file",
    type=click.Path(),
    default=WPD.CONFIG_FILE,
    show_default=True,
    help="Path to workout configuration YAML file.",
)
@click.option(
    "--history-file",
    "history_file",
    type=click.Path(),
    default=WPD.HISTORY_FILE,
    show_default=True,
    help="Path to workout history JSONL file.",
)
@click.option(
    "--claude-api-key-file",
    "claude_api_key_file",
    type=click.Path(),
    default=WPD.CLAUDE_API_KEY_FILE,
    show_default=True,
    help="Path to Claude API key file.",
)
@click.option(
    "--task-secrets-file",
    "task_secrets_file",
    type=click.Path(),
    default=WPD.TASK_SECRETS_FILE,
    show_default=True,
    help="Google Tasks client secrets file.",
)
@click.option(
    "--task-refresh-token",
    "task_refresh_token",
    type=click.Path(),
    default=WPD.TASK_REFRESH_TOKEN,
    show_default=True,
    help="Google Tasks refresh token file.",
)
@click.option(
    "--task-list-id",
    "task_list_id",
    type=str,
    default=WPD.TASK_LIST_ID,
    show_default=True,
    help="UUID of the Google Task List.",
)
@click.option(
    "--enable-logging",
    "enable_logging",
    is_flag=True,
    default=WPD.ENABLE_LOGGING,
    help="Enable verbose logging.",
)
def cli(
    ctx: click.Context,
    config_file,
    history_file,
    claude_api_key_file,
    task_secrets_file,
    task_refresh_token,
    task_list_id,
    enable_logging,
):
    """AI-powered workout planner with Google Tasks integration."""
    ctx.obj = {
        "config_file": config_file,
        "history_file": history_file,
        "claude_api_key_file": claude_api_key_file,
        "task_secrets_file": task_secrets_file,
        "task_refresh_token": task_refresh_token,
        "task_list_id": task_list_id,
        "enable_logging": enable_logging,
    }


@cli.command()
@click.pass_context
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    help="Generate workout but don't create task or log to history.",
)
@click.option(
    "--force-yesterday-completed",
    "force_yesterday_completed",
    type=bool,
    default=None,
    help="Override yesterday's completion status (True/False).",
)
def generate(ctx: click.Context, dry_run, force_yesterday_completed):
    """
    Generate today's workout plan and create a Google Task.

    This command:
    1. Checks if yesterday's workout was completed
    2. Generates a personalized workout using Claude API
    3. Creates a Google Task with the workout
    4. Logs the workout to history
    """
    try:
        # Initialize components
        planner = WorkoutPlanner(**ctx.obj)
        task_checker = TaskChecker(**ctx.obj)

        # Check yesterday's completion status
        if force_yesterday_completed is not None:
            yesterday_completed = force_yesterday_completed
            if ctx.obj["enable_logging"]:
                print(f"Using forced yesterday completion status: {yesterday_completed}")
        else:
            yesterday_completed = task_checker.check_previous_day_workout()

        # Generate workout
        if ctx.obj["enable_logging"]:
            print("Generating workout plan...")

        task_title, workout_details = planner.generate_workout(yesterday_completed)

        print("\n" + "=" * 70)
        print("GENERATED WORKOUT")
        print("=" * 70)
        print(f"\nTitle: {task_title}")
        print(f"\nDetails:\n{workout_details}")
        print("\n" + "=" * 70)

        if dry_run:
            print("\n[DRY RUN] Workout generated but not saved or published.")
            return

        # Create Google Task
        if ctx.obj["enable_logging"]:
            print("\nCreating Google Task...")

        task_checker.create_workout_task(task_title, workout_details)
        print(f"\n✓ Task created: {task_title}")

        # Log to history (marked as not completed yet)
        if ctx.obj["enable_logging"]:
            print("Logging to workout history...")

        planner.log_workout(task_title, workout_details, completed=False)
        print("✓ Workout logged to history")

        print("\nWorkout planning complete!")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if ctx.obj["enable_logging"]:
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.pass_context
@click.option(
    "--days",
    "days",
    type=int,
    default=7,
    show_default=True,
    help="Number of days of history to display.",
)
def history(ctx: click.Context, days):
    """Display recent workout history."""
    try:
        planner = WorkoutPlanner(**ctx.obj)
        history_entries = planner._load_history(days=days)

        if not history_entries:
            print("No workout history found.")
            return

        print("\n" + "=" * 70)
        print(f"WORKOUT HISTORY (Last {days} days)")
        print("=" * 70)

        for entry in history_entries:
            status = "✓ COMPLETED" if entry["completed"] else "✗ MISSED"
            print(f"\n{entry['date']} - {status}")
            print("-" * 70)
            print(entry["workout"])
            if entry.get("notes"):
                print(f"\nNotes: {entry['notes']}")

        print("\n" + "=" * 70)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if ctx.obj["enable_logging"]:
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.pass_context
def check_yesterday(ctx: click.Context):
    """Check if yesterday's workout was completed."""
    try:
        task_checker = TaskChecker(**ctx.obj)
        completed = task_checker.check_previous_day_workout()

        if completed:
            print("✓ Yesterday's workout was COMPLETED (task not found/deleted)")
        else:
            print("✗ Yesterday's workout was MISSED (task still exists)")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if ctx.obj["enable_logging"]:
            traceback.print_exc()
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
