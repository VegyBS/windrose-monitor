# Testing Guide

This document explains how to run tests locally and understand the testing strategy.

## Overview

The Windrose Monitor uses **unit tests with mocked APIs** to ensure code quality without requiring actual Discord or Pterodactyl credentials during testing.

**Why mocking?**
- ✅ Tests run fast and don't depend on external services
- ✅ No need for test Discord servers or Pterodactyl instances
- ✅ Tests are deterministic and reproducible
- ✅ Safe to run in CI/CD pipelines (GitHub Actions)
- ✅ Standard industry practice

## Running Tests Locally

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
```

### Configuration Validation

The `test_config.py` script has two modes:

#### Local Mode (Default)
Tests real API connectivity. Use this before deploying:

```bash
# Run in local mode - tests real APIs
python test_config.py
```

This validates:
- ✓ Pterodactyl API connectivity
- ✓ Discord webhook works
- ✓ CPU frequency scaling available
- ✓ File permissions

#### CI Mode (GitHub Actions)
Validates configuration structure without real API calls:

```bash
# Run in CI mode - uses mocked APIs
CI=true python test_config.py
```

This validates:
- ✓ Configuration format/structure
- ✓ Required fields present
- ✓ Token format valid
- ✓ No external API calls (faster, safer in CI)

### Run All Tests

```bash
# Run all unit tests with verbose output
python -m unittest discover -s . -p 'test_*.py' -v
```

### Run Specific Test Class

```bash
# Test only player parsing logic
python -m unittest test_windrose_monitor.TestPlayerListParsing -v

# Test only player state detection
python -m unittest test_windrose_monitor.TestPlayerStateDetection -v

# Test only CPU profile logic
python -m unittest test_windrose_monitor.TestCPUProfileLogic -v
```

### Run Individual Tests

```bash
# Test a specific test method
python -m unittest test_windrose_monitor.TestPlayerListParsing.test_parse_players_with_reserved_accounts -v
```

## Test Coverage

### Core Logic Tested

#### 1. **Log Parsing** (`TestPlayerListParsing`)
- ✅ Parsing players from Reserved Accounts section
- ✅ Handling empty player lists
- ✅ Parsing multiple players correctly
- ✅ Ignoring log timestamps and other data

**What this tests:** The heart of the monitoring—correctly identifying who's online from server logs

#### 2. **Player State Detection** (`TestPlayerStateDetection`)
- ✅ Detecting new players joining
- ✅ Detecting players leaving
- ✅ No false positives when list unchanged
- ✅ Complete player turnover scenarios

**What this tests:** Proper join/leave detection logic

#### 3. **CPU Profile Logic** (`TestCPUProfileLogic`)
- ✅ Switching to performance when players join
- ✅ Switching to balanced when players leave
- ✅ Not switching unnecessarily (optimization)

**What this tests:** CPU profile switching decisions are correct

#### 4. **Configuration** (`TestConfigValidation`)
- ✅ Config file structure validation
- ✅ config.example.json is valid JSON
- ✅ All required keys present

**What this tests:** Configuration integrity

#### 5. **Discord Messages** (`TestDiscordMessageFormat`)
- ✅ Player joined message format
- ✅ Player left message format
- ✅ Player count message format
- ✅ Emoji and formatting correct

**What this tests:** Discord message formatting is correct

#### 6. **State Management** (`TestStateManagement`)
- ✅ Initial state structure
- ✅ State updates with new players
- ✅ Timestamp tracking

**What this tests:** State persistence logic

## GitHub Actions Workflow

The `.github/workflows/tests.yml` file automatically runs tests on:
- Every push to `main` or `develop` branches
- Every pull request to `main`

### What the workflow does:

1. **Tests Python 3.7-3.11** - Ensures compatibility with multiple Python versions
2. **Validates JSON/Config** - Checks config.example.json and .env.example are valid
3. **Syntax checks** - Verifies all Python files compile
4. **Linting** - Checks code style with flake8
5. **Runs test_config.py in CI mode** - Validates configuration without external API calls

### CI Mode Configuration

The workflow sets environment variables to enable **CI mode**:

```yaml
env:
  CI: 'true'  # Enables mocked API mode in test_config.py
  PTERODACTYL_API_URL: 'https://example-pterodactyl.com'
  PTERODACTYL_API_TOKEN: 'test-token-12345'
  PTERODACTYL_SERVER_ID: 'test-server-uuid'
  DISCORD_WEBHOOK_URL: 'https://discord.com/api/webhooks/test/test'
```

When `CI=true`, the test_config.py script:
- ✅ Skips real API calls (no network requests)
- ✅ Validates configuration structure only
- ✅ Runs fast and reliably
- ✅ Never exposes real credentials
- ✅ Uses placeholder values for testing

This means:
- **No actual API calls to Pterodactyl or Discord during tests**
- **Tests run in seconds instead of minutes**
- **GitHub Actions runners can't compromise real credentials**
- **Tests pass/fail based on code logic, not external services**

### View test results:

1. Go to your GitHub repository
2. Click "Actions" tab
3. Click latest workflow run
4. Expand test jobs to see details
5. Look for "Mode: CI/GitHub Actions (mocked APIs)" in test_config.py output

## What's NOT Tested (and why)

### Actual API Calls
- **Why skip:** Third-party services (Discord, Pterodactyl) are their responsibility to maintain
- **How to test in CI:** `test_config.py` validates structure without API calls
- **How to test locally:** Run `python test_config.py` (real mode) on your machine with real credentials

### Network Communication
- **Why skip:** Network is flaky and slow for CI/CD
- **How to test:** Verify once locally, trust tests in CI after that

### systemd Integration
- **Why skip:** Requires root access in test environment
- **How to test:** Manual testing during deployment on your Ubuntu server

### CPU Frequency Scaling
- **Why skip:** GitHub Actions runners don't have this hardware
- **How to test:** Manual testing on your actual Ubuntu server

## Manual Integration Testing

Before deploying to production, manually test with real APIs:

```bash
# On your Ubuntu server
python test_config.py

# This validates:
# ✓ Pterodactyl API connectivity
# ✓ Discord webhook works
# ✓ CPU frequency scaling available
# ✓ File permissions correct
```

## Adding New Tests

When you add new features, add corresponding tests:

1. **Identify testable logic** - What can you test without external services?
2. **Create test cases** - Add to `test_windrose_monitor.py`
3. **Use mocks** - Mock any external calls
4. **Test edge cases** - Empty lists, null values, errors

Example:

```python
class TestNewFeature(unittest.TestCase):
    def test_new_feature_basic(self):
        # Arrange
        input_data = {...}
        
        # Act
        result = some_function(input_data)
        
        # Assert
        self.assertEqual(result, expected)
```

## Continuous Improvement

- Tests catch bugs early
- Tests document expected behavior
- Tests prevent regressions
- Tests make refactoring safer

## Troubleshooting

### Tests fail locally but pass in GitHub Actions
- Check Python version matches: `python --version`
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Clear Python cache: `find . -type d -name __pycache__ -exec rm -rf {} +`

### Test import errors
```bash
# Make sure you're in the project root
cd /path/to/windrose-monitor

# Run tests from correct directory
python -m unittest discover
```

### Flake8 linting fails
```bash
# Install flake8
pip install flake8

# See specific issues
flake8 windrose_monitor.py

# Fix common issues automatically (requires autopep8)
pip install autopep8
autopep8 --in-place windrose_monitor.py
```

## CI/CD Best Practices

✅ **Do:**
- Test logic, not external services
- Keep tests fast (< 1 second each)
- Mock all external dependencies
- Test edge cases and errors
- Update tests when code changes

❌ **Don't:**
- Make real API calls in tests
- Write tests that depend on network
- Commit hardcoded secrets in tests
- Skip testing "because it's tested in production"
- Ignore failing tests

## Resources

- [Python unittest documentation](https://docs.python.org/3/library/unittest.html)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
