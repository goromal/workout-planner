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

### 1. Dry Run (No Task Creation)

Test workout generation without creating tasks or logging history:

```bash
workout-planner --enable-logging generate --dry-run
```

This will:
- Check if yesterday's workout was completed
- Generate today's workout using Claude API
- Display the workout plan
- **NOT** create a Google Task
- **NOT** log to history

### 2. Check Yesterday's Completion

See if yesterday's workout task exists (to determine if it was completed):

```bash
workout-planner check-yesterday
```

Output:
- ✓ if workout was completed (task deleted/not found)
- ✗ if workout was missed (task still exists)

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
- Check yesterday's completion
- Generate workout
- Create Google Task with "P0: Workout: ..." title
- Log to `~/data/workout/history.jsonl`

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
