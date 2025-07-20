# Docker Quick Start Guide

This guide shows you how to run Autodidact using Docker - the easiest way to get started!

## Prerequisites

- Docker and Docker Compose installed on your system
- Git (to clone the repository)

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/raymondlowe/autodidact-agent.git
cd autodidact-agent
```

2. Run the application:
```bash
docker compose up
```

3. Open your browser and go to: http://localhost:8501

That's it! Autodidact is now running in a container.

## Stopping the Application

To stop the application:
```bash
docker compose down
```

## Data Persistence

Your data (database, configuration, and projects) is automatically saved in a Docker volume called `autodidact_data`. This means:

- Your data persists between container restarts
- You can safely update the application by pulling new code and running `docker compose up --build`
- Your API keys and projects will be preserved

## Updating the Application

To update to the latest version:

1. Stop the current application:
```bash
docker compose down
```

2. Pull the latest changes:
```bash
git pull
```

3. Rebuild and restart:
```bash
docker compose up --build
```

## Troubleshooting

### Port Already in Use
If port 8501 is already in use, you can change it by editing `docker-compose.yml`:
```yaml
ports:
  - "8502:8501"  # Change 8502 to any available port
```

### Viewing Logs
To see application logs:
```bash
docker compose logs -f
```

### Removing All Data
To completely reset and remove all data:
```bash
docker compose down -v
```
**Warning**: This will delete all your projects and configuration!

## Running in Background

To run the application in the background (detached mode):
```bash
docker compose up -d
```

Then check status with:
```bash
docker compose ps
```