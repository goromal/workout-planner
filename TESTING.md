# Testing Workout Planner

This guide shows you how to test the workout planner before deploying it to your ATS automated server.

## Prerequisites

1. **Config File**: Copy the template and customize it
   ```bash
   mkdir -p ~/configs
   cp workout-config.yaml.template ~/configs/workout-config.yaml
   # Edit ~/configs/workout-config.yaml with your preferences
   ```

2. **Claude API Key**: Store your API key
   ```bash
   mkdir -p ~/secrets/claude
   echo "your-api-key-here" > ~/secrets/claude/api_key.txt
   chmod 600 ~/secrets/claude/api_key.txt
   ```

3. **Google Tasks Credentials**: Ensure you have these already set up
   - `~/secrets/google/client_secret.json`
   - `~/secrets/google/refresh_token.json`

## Testing Commands

### 1. Check for Carryover Workouts

See if there are any incomplete workout tasks:

```bash
workout-planner check-yesterday
```

Output:
- ✓ if no carryover workouts (all previous workouts completed)
- ✗ if carryover workout exists (incomplete task from any previous day)

### 2. Dry Run (May Skip API Call)

Test workout generation without creating tasks or logging history:

```bash
workout-planner --enable-logging generate --dry-run
```

This will:
- Check for carryover workouts (incomplete tasks)
- Check if weekly workout target has been reached
- **SKIP Claude API call** if:
  - Carryover workout exists, OR
  - Weekly target reached (e.g., 4 workouts already completed this week)
- **CALL Claude API** only if new workout is needed
- Display the workout plan (if generated)
- **NOT** create a Google Task
- **NOT** log to history

**Note**: This is now more efficient - it won't waste API calls when you don't need a workout!

### 3. Force Completion Status

Override yesterday's completion status for testing:

```bash
# Test with yesterday completed
workout-planner --enable-logging generate --dry-run --force-yesterday-completed True

# Test with yesterday missed
workout-planner --enable-logging generate --dry-run --force-yesterday-completed False
```

### 4. Full Test (Creates Task)

Generate and publish a real workout task:

```bash
workout-planner --enable-logging generate
```

This will:
- Check for carryover workouts
- Check weekly workout target
- **SKIP API call** if carryover exists or weekly target reached
- **Generate workout with Claude API** only if needed
- Create Google Task with "P0: Workout: ..." title (if generated)
- Log to `~/data/workout/history.jsonl` (if generated)

### 5. View History

See your workout history:

```bash
# Last 7 days (default)
workout-planner history

# Last 30 days
workout-planner history --days 30
```

## Idempotent Testing Pattern

To safely test the full workflow repeatedly:

```bash
# 1. Generate a workout
workout-planner --enable-logging generate

# 2. Check it was created
task-tools list all --date $(date +%Y-%m-%d)

# 3. Delete the test workout task
task-tools delete <task-id>

# 4. Repeat as needed
```

Or use the dry-run flag for non-destructive testing:

```bash
# Run multiple times safely
workout-planner --enable-logging generate --dry-run
```

## Expected File Structure After Testing

```
~/
├── configs/
│   └── workout-config.yaml          # Your configuration
├── secrets/
│   ├── claude/
│   │   └── api_key.txt             # Claude API key
│   └── google/
│       ├── client_secret.json      # Google OAuth client
│       └── refresh_token.json      # Google OAuth token
└── data/
    └── workout/
        └── history.jsonl           # Workout history log
```

## Testing the ATS Job

To test the automated job before it runs on schedule:

```bash
# Simulate the full ATS job script
authm refresh --headless
rcrsync sync configs
workout-planner --enable-logging generate
```

## API Call Optimization

The system is designed to minimize Claude API calls:

### When API Calls Are SKIPPED:

1. **Carryover Workout Exists**
   - If any incomplete "P0: Workout" task exists from any previous day
   - Message: "⚠️  Carryover workout detected"
   - Reason: You should complete existing workout before getting a new one

2. **Weekly Target Reached**
   - If you've completed ≥ `frequency_per_week` workouts this week (Mon-Sun)
   - Message: "✓ Weekly workout target reached"
   - Reason: You've already hit your weekly goal

### When API Calls ARE MADE:

- No carryover workouts exist
- AND weekly target not yet reached
- Example: 3/4 workouts done this week, no incomplete tasks

### Testing API Call Behavior:

```bash
# Scenario 1: Test with incomplete task (should skip API)
workout-planner generate  # Creates a task
workout-planner generate  # Should skip - carryover exists

# Scenario 2: Test weekly limit (should skip API after hitting target)
# Complete 4 workouts in the same week
# Next call should skip with "Weekly target reached"
```

## Troubleshooting

### "Config file not found"
Ensure `~/configs/workout-config.yaml` exists and is properly formatted YAML.

### "Claude API key file not found"
Create `~/secrets/claude/api_key.txt` with your API key.

### "Failed to initialize Google Tasks service"
Check that Google credentials are valid:
```bash
authm refresh --headless
```

### "No history file found"
This is normal on first run. The file will be created automatically.

## Daily Workflow

Once deployed to ATS, the system will:

1. **05:30 AM** - `ats-workout-planner` runs
   - Checks if you completed yesterday's workout
   - Generates today's workout with Claude
   - Creates P0 task in Google Tasks
   - Logs to history

2. **06:00 AM** - `ats-task-migrator` runs
   - Migrates incomplete tasks (including missed workouts)

If you complete your workout (delete the task), the next day's plan will reflect that. If you miss it, the task will be migrated forward and the next plan will account for the miss.
