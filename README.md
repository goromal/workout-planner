# Workout Planner

AI-powered strength workout planner that integrates with Google Tasks.

## Features

- Generates personalized daily workout plans using Claude API
- Tracks workout history and completion status
- Integrates with Google Tasks for task management
- Considers user goals, constraints, and equipment availability

## Configuration

Create `~/configs/workout-config.yaml` with your workout preferences.

## Usage

```bash
workout-planner generate
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
