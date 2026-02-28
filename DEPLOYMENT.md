# Workout Planner Deployment Guide

## Overview

The workout planner system has been successfully implemented and integrated into your ATS (Automated Task System). It consists of:

1. **workout-planner** Python package - AI-powered workout generation
2. **ATS integration** - Automated daily job at 05:30
3. **Configuration system** - User-editable YAML config
4. **History tracking** - JSONL-based workout log

## Architecture

### Data Flow

```
05:30 Daily Trigger
    ↓
ats-workout-planner job
    ↓
├─ authm refresh (Google Auth)
├─ rcrsync sync configs (Sync config file)
├─ workout-planner generate
│   ├─ Check for carryover workouts (incomplete tasks)
│   ├─ SKIP if carryover exists → Exit
│   ├─ Load ~/configs/workout-config.yaml
│   ├─ Load recent history from ~/data/workout/history.jsonl
│   ├─ Count workouts completed this week
│   ├─ SKIP if weekly target reached → Exit
│   ├─ Call Claude API for workout generation (ONLY if needed)
│   ├─ Create Google Task "P0: Workout: ..."
│   └─ Append to history log
└─ logger success message

06:00 ats-task-migrator
    └─ Migrates incomplete tasks (including missed workouts)
```

### Components

#### 1. workout-planner Package
**Location**: `/data/andrew/dev/anix/sources/workout-planner/`

**Modules**:
- `cli.py` - Command-line interface with Click
- `planner.py` - Claude API integration and workout generation
- `task_checker.py` - Google Tasks API integration
- `defaults.py` - Configuration defaults

**Commands**:
- `workout-planner generate` - Generate and publish workout
- `workout-planner generate --dry-run` - Test without publishing
- `workout-planner history` - View workout history
- `workout-planner check-yesterday` - Check completion status

#### 2. ATS Integration
**Location**: `/data/andrew/dev/packages/sources/anixpkgs/pkgs/nixos/profiles/ats.nix`

**Job**: `ats-workout-planner`
- **Schedule**: Daily at 05:30 (before task-migrator at 06:00)
- **Persistent**: Yes (runs even if system was off)
- **Dependencies**: authm, rcrsync, workout-planner

#### 3. Configuration
**Location**: `~/configs/workout-config.yaml`

**Structure**:
```yaml
goals:
  - Your fitness goals
constraints:
  - Session length, equipment, injuries
available_equipment:
  - List of equipment
preferences:
  split: push_pull_legs
  frequency_per_week: 4
  style: mixed
current_status:
  last_updated: "YYYY-MM-DD"
  notes: "Current focus areas"
```

#### 4. History
**Location**: `~/data/workout/history.jsonl`

**Format**:
```json
{"date": "2026-02-22", "completed": false, "workout": "Full workout text", "notes": "", "timestamp": "..."}
```

## Setup Instructions

### 1. Create Configuration File

```bash
# Copy the template
mkdir -p ~/configs
cp /data/andrew/dev/anix/sources/workout-planner/workout-config.yaml.template \
   ~/configs/workout-config.yaml

# Edit with your preferences
vim ~/configs/workout-config.yaml
```

### 2. Store Claude API Key

```bash
mkdir -p ~/secrets/claude
echo "your-anthropic-api-key" > ~/secrets/claude/api_key.txt
chmod 600 ~/secrets/claude/api_key.txt
```

### 3. Verify Google Credentials

Ensure these files exist (they should already be configured for task-tools):
- `~/secrets/google/client_secret.json`
- `~/secrets/google/refresh_token.json`

### 4. Update Flake Lock (When Ready to Deploy)

Currently, the flake.nix points to a local path for development:

```nix
workout-planner.url = "path:/data/andrew/dev/anix/sources/workout-planner";
```

When ready to deploy to GitHub:

```bash
# 1. Create GitHub repository
gh repo create goromal/workout-planner --public --source=/data/andrew/dev/anix/sources/workout-planner --push

# 2. Update flake.nix to use GitHub
# Change: workout-planner.url = "path:/data/andrew/dev/anix/sources/workout-planner";
# To:     workout-planner.url = "github:goromal/workout-planner";

# 3. Update flake lock
cd /data/andrew/dev/packages/sources/anixpkgs
nix flake lock --update-input workout-planner

# 4. Rebuild system
sudo nixos-rebuild switch --flake .#your-hostname
```

## Testing (Before Full Deployment)

### Test 1: Dry Run Generation

```bash
workout-planner --enable-logging generate --dry-run
```

**Expected Output**:
- Shows yesterday's completion status
- Generates workout with Claude API
- Displays workout title and details
- Does NOT create task or log history

### Test 2: Check Yesterday's Status

```bash
workout-planner check-yesterday
```

**Expected Output**:
- ✓ if yesterday's workout was completed
- ✗ if yesterday's workout was missed

### Test 3: Full Generation (Idempotent)

```bash
# Generate a test workout
workout-planner --enable-logging generate

# Check it was created
task-tools list all --date $(date +%Y-%m-%d) | grep "P0: Workout"

# View the history
workout-planner history --days 1

# Delete the test task (to repeat idempotently)
task-tools delete <task-id-from-list>
```

### Test 4: Simulate ATS Job

```bash
# Run the exact commands from the ATS job
authm refresh --headless
rcrsync sync configs
workout-planner --enable-logging generate
```

### Test 5: Force Completion Status

```bash
# Test with yesterday completed
workout-planner generate --dry-run --force-yesterday-completed True

# Test with yesterday missed
workout-planner generate --dry-run --force-yesterday-completed False
```

## Monitoring

### Check Job Status

```bash
# View systemd timer status
systemctl status ats-workout-planner.timer

# View latest job logs
journalctl -u ats-workout-planner.service -n 50 -f

# Check if job is scheduled
systemctl list-timers | grep ats-workout-planner
```

### View Generated Tasks

```bash
# List today's tasks
task-tools list all --date $(date +%Y-%m-%d)

# List P0 tasks specifically
task-tools list p0 --date $(date +%Y-%m-%d)
```

### Check History

```bash
# View recent workouts
workout-planner history --days 7

# View history file directly
tail -f ~/data/workout/history.jsonl | jq
```

## Workflow

### Daily Automated Flow

1. **05:30 AM** - `ats-workout-planner` runs
   - Authenticates with Google
   - Syncs config from cloud
   - **Checks for carryover workouts** (incomplete tasks from ANY previous day)
     - If carryover exists → SKIP (no API call, no new task)
   - **Checks weekly workout count** from history
     - If weekly target reached → SKIP (no API call, no new task)
   - **Only if both checks pass:**
     - Calls Claude API with config + history + completion status
     - Creates new "P0: Workout: ..." task for today
     - Logs entry to `~/data/workout/history.jsonl`

2. **06:00 AM** - `ats-task-migrator` runs
   - Processes all incomplete tasks
   - Migrates late P0 tasks to today (if manually created)
   - Auto-generated tasks that are late get deleted

3. **Throughout Day** - You complete workout
   - Complete (delete) the task when done
   - Or leave it if you skip/miss the workout

4. **Next Morning** - Cycle repeats
   - Carryover check ensures you finish current workout first
   - Weekly count ensures you don't exceed your target
   - History builds up for long-term pattern analysis

### API Call Optimization

The system minimizes Claude API calls intelligently:

**API calls are SKIPPED when:**
- ❌ Carryover workout exists (incomplete task from previous day)
  - Reason: Finish your current workout before getting a new one
- ❌ Weekly target reached (e.g., 4/4 workouts done this week)
  - Reason: You've already hit your weekly goal

**API calls are MADE when:**
- ✅ No carryover workouts exist
- ✅ AND weekly target not yet reached
- Example: 3/4 workouts done this week, no incomplete tasks

**Benefits:**
- Saves API costs (no unnecessary calls)
- Prevents workout overload
- Respects your weekly training frequency
- Encourages completion of existing workouts

### Manual Intervention

If you want to manually generate a workout outside the schedule:

```bash
# Generate for today
workout-planner generate

# Force regeneration with different completion status
workout-planner generate --force-yesterday-completed False
```

## Customization

### Update Your Config

```bash
# Edit config
vim ~/configs/workout-config.yaml

# Sync to cloud (if using rcrsync)
rcrsync override configs

# Next generation will use new config
```

### Adjust Schedule

Edit `/data/andrew/dev/packages/sources/anixpkgs/pkgs/nixos/profiles/ats.nix`:

```nix
timerCfg = {
  OnCalendar = [ "*-*-* 05:30:00" ];  # Change time here
  Persistent = true;
};
```

Then rebuild:

```bash
sudo nixos-rebuild switch --flake .#your-hostname
```

## Troubleshooting

### Problem: "Config file not found"

**Solution**:
```bash
cp /data/andrew/dev/anix/sources/workout-planner/workout-config.yaml.template \
   ~/configs/workout-config.yaml
```

### Problem: "Claude API key file not found"

**Solution**:
```bash
mkdir -p ~/secrets/claude
echo "your-api-key" > ~/secrets/claude/api_key.txt
chmod 600 ~/secrets/claude/api_key.txt
```

### Problem: "Failed to initialize Google Tasks service"

**Solution**:
```bash
# Refresh Google authentication
authm refresh --headless

# Check credentials exist
ls -la ~/secrets/google/
```

### Problem: Job not running

**Solution**:
```bash
# Check timer is active
systemctl status ats-workout-planner.timer

# Enable timer if needed
systemctl enable ats-workout-planner.timer

# Start timer
systemctl start ats-workout-planner.timer

# Trigger job manually
systemctl start ats-workout-planner.service
```

### Problem: Workouts not generated

**Solution**:
```bash
# Check logs
journalctl -u ats-workout-planner.service -n 100

# Test manually
workout-planner --enable-logging generate --dry-run
```

## Files Reference

### Created Files

- `/data/andrew/dev/anix/sources/workout-planner/` - Package source
- `/data/andrew/dev/packages/sources/anixpkgs/pkgs/python-packages/workout-planner/default.nix` - Nix package
- Modified: `/data/andrew/dev/packages/sources/anixpkgs/flake.nix` - Added flake input
- Modified: `/data/andrew/dev/packages/sources/anixpkgs/pkgs/default.nix` - Added Python overlay
- Modified: `/data/andrew/dev/packages/sources/anixpkgs/pkgs/nixos/profiles/ats.nix` - Added job

### User Files (You Create)

- `~/configs/workout-config.yaml` - Your workout preferences
- `~/secrets/claude/api_key.txt` - Claude API key
- `~/data/workout/history.jsonl` - Auto-generated history log

## Next Steps

1. ✓ Create `~/configs/workout-config.yaml`
2. ✓ Store Claude API key in `~/secrets/claude/api_key.txt`
3. ✓ Test with dry-run: `workout-planner generate --dry-run`
4. ✓ Test full generation: `workout-planner generate`
5. ✓ Push workout-planner to GitHub (when ready)
6. ✓ Update flake.nix to use GitHub URL
7. ✓ Deploy to ATS server
8. ✓ Monitor first automated run at 05:30

## Summary

The workout planner is now fully implemented and ready for testing. The system will:

- **Daily at 05:30**: Check yesterday's completion, generate today's workout
- **Use Claude API**: For intelligent, personalized workout planning
- **Track History**: Build understanding of your patterns over time
- **Integrate Seamlessly**: Works with existing task-tools and ATS infrastructure

Test it thoroughly using the idempotent testing pattern in TESTING.md before deploying to production.
