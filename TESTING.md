# Windrose Monitor Testing Guide 🧪🔍

This document describes how to test the Windrose Server Monitor to ensure it behaves correctly, handles WebSocket events reliably, and responds safely to real‑world conditions such as disconnects, token expiry, and CPU profile changes.

The tests are designed to run on the Linux host where the monitor is installed, but many can also be executed from a development machine.

---

## 1. Overview of Test Coverage 📋

The test suite covers the following areas:

- Player list parsing
- Join and leave detection
- WebSocket connection and reconnection logic
- Token refresh behaviour
- CPU profile switching
- Discord message formatting
- Configuration precedence
- State file handling
- Error handling and resilience

These tests help ensure the monitor behaves consistently even under unstable network or panel conditions.

---

## 2. Running the Test Suite ▶️

From the project directory:

python -m unittest discover -s . -p 'test_*.py' -v

This command will:

- Discover all test files matching test_*.py
- Run them in verbose mode
- Display pass, fail, and error output

If the monitor is installed system‑wide, you can still run tests from the cloned repository.

---

## 3. Unit Tests Included 🧩

### 3.1 Player Parsing Tests

These tests verify that the monitor correctly extracts:

- Connected Accounts
- Reserved Accounts
- Disconnected Accounts

They also validate:

- Active player calculation
- Transition from active to inactive
- Handling of empty or malformed sections

---

### 3.2 Join and Leave Detection

Tests simulate:

- A player joining
- A player leaving
- Multiple players joining or leaving
- Rapid join‑leave sequences
- Duplicate entries

The monitor must update state.json correctly and avoid false positives.

---

### 3.3 WebSocket Behaviour

Tests include:

- Successful authentication
- Token expiry
- Unexpected disconnects
- Reconnect attempts
- Exponential backoff
- Handling of malformed messages

These tests ensure the monitor stays connected even when Wings is unstable.

---

### 3.4 CPU Profile Switching

Tests verify:

- Switching to performance mode when players join
- Switching to balanced mode when the server empties
- Writing to the correct sysfs paths
- Handling missing or read‑only sysfs entries
- State persistence across restarts

---

### 3.5 Discord Notification Formatting

Tests validate:

- Join messages
- Leave messages
- Player count updates
- Error handling when the webhook fails
- Message throttling if implemented

---

### 3.6 Configuration Precedence

Tests ensure:

- .env overrides config.json
- config.json overrides defaults
- Missing values fall back safely
- Invalid values produce warnings

---

### 3.7 State File Handling

Tests cover:

- Creating state.json if missing
- Updating state.json safely
- Handling corrupted state files
- Ensuring atomic writes where possible

---

## 4. Manual Testing 🧪🖐️

In addition to automated tests, you can manually verify behaviour.

### 4.1 Simulate a Player Join

Start your Windrose server and join it.
Check:

- Discord receives a join message
- CPU profile switches to performance
- state.json updates

### 4.2 Simulate a Player Leave

Leave the server.
Check:

- Discord receives a leave message
- CPU profile switches to balanced
- state.json updates

### 4.3 Restart the Monitor

sudo systemctl restart windrose-monitor

Verify:

- WebSocket reconnects
- State persists
- No duplicate notifications

### 4.4 Break the WebSocket Connection

Disable your network temporarily or restart Wings.
The monitor should:

- Detect the disconnect
- Attempt reconnection
- Resume normal operation

---

## 5. Log Inspection 📜

To observe behaviour in real time:

sudo journalctl -u windrose-monitor -f

Look for:

- WebSocket events
- Reconnect attempts
- Player detection
- CPU profile changes
- Errors or warnings

---

## 6. Troubleshooting 🛠️

### WebSocket fails to authenticate
Check PTERODACTYL_API_TOKEN and PTERODACTYL_SERVER_ID.

### CPU profile does not change
Ensure the systemd unit includes ReadWritePaths for sysfs.

### Discord messages not sent
Verify DISCORD_WEBHOOK_URL and network connectivity.

### Tests fail due to CRLF
Ensure your editor uses LF line endings.

---

## 7. Conclusion 🎉

The Windrose Server Monitor includes a comprehensive test suite that validates its behaviour under real‑world conditions.
Running these tests regularly helps ensure reliability, especially when updating the monitor or modifying its logic.