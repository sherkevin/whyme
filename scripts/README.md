# Scripts Directory

This directory contains executable scripts for development and testing.

## Available Scripts

### Server Management
- **run_server.py** - Start the AgentOS development server
- **start.py** - Alternative server startup script

### Testing & Debugging
- **simple_test.py** - Simple test runner
- **hello.py** - Basic hello world test
- **hello_verbose.py** - Verbose hello world test
- **analyze_differences.py** - Analyze code differences
- **force_reload.py** - Force reload components

## Usage

### Start Server
```bash
python scripts/run_server.py
# or
python scripts/start.py
```

### Run Tests
```bash
python scripts/simple_test.py
```

### Analyze Code
```bash
python scripts/analyze_differences.py
```

## Notes

- These scripts are primarily for development purposes
- For production deployment, use Docker containers
- See `../deploy-docker.sh` for Docker deployment
