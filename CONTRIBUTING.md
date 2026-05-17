# Contributing to Windrose Monitor 🤝🛠️

Thank you for your interest in contributing to the Windrose Server Monitor.
This project benefits from clear, consistent contributions — whether you’re fixing bugs, improving documentation, or adding new features.

This guide explains how to contribute safely and effectively.

---

## 1. Ways You Can Contribute 🌟

You can help the project by:

- Reporting bugs
- Improving documentation
- Adding tests
- Enhancing WebSocket handling
- Improving CPU scaling logic
- Adding new configuration options
- Refactoring code for clarity or reliability

All contributions are welcome as long as they maintain the project’s goals:
reliability, clarity, and operational safety.

---

## 2. Areas for Contribution 📌

### High Priority
- [ ] Improve log parsing accuracy
- [ ] Add support for different server types
- [ ] Create web dashboard for monitoring
- [ ] Add metrics export (Prometheus, StatsD)
- [ ] Improve error handling and recovery

### Documentation
- [ ] Video tutorials
- [ ] Troubleshooting guides for common issues
- [ ] Integration guides for other services

### Testing
- [ ] Unit tests for core functions
- [ ] Integration tests with mock Pterodactyl API
- [ ] Performance tests under load

### Features
- [ ] Player session tracking and statistics
- [ ] Server performance monitoring (CPU, RAM, network)
- [ ] Discord command for server status
- [ ] Multiple server support
- [ ] Database backend for historical data

---

## 3. Development Workflow 🔄

### Fork the repository
Create your own fork on GitHub so you can work independently.

### Clone your fork
Clone it onto your development machine.

### Create a feature branch
Use descriptive names such as:

feature/websocket-retry
fix/cpu-profile-permissions
docs/update-setup-guide

### Make your changes
Follow the coding standards below.

### Run the test suite
Before submitting a pull request:

python -m unittest discover -s . -p 'test_*.py' -v

### Submit a pull request
Describe:

- What you changed
- Why you changed it
- Any risks or breaking changes
- How you tested it

---

## 4. Coding Standards 🧩

### Python style
- Follow PEP 8
- Use descriptive variable names
- Avoid deeply nested logic
- Prefer small, testable functions
- Use type hints where helpful

### Logging
- Use structured, readable log messages
- Avoid noisy or repetitive logs
- Never log secrets

### Error handling
- Catch only specific exceptions
- Provide meaningful error messages
- Avoid silent failures

### State file safety
- Always write state.json atomically
- Never assume the file exists
- Handle corruption gracefully

---

## 5. Documentation Standards 📘

When updating documentation:

- Keep language clear and concise
- Use consistent formatting
- Avoid nested backticks
- Ensure examples match actual behaviour
- Update SETUP.md, TESTING.md, and QUICKREF.md if needed

---

## 6. Testing Expectations 🧪

All new features should include tests covering:

- Normal behaviour
- Edge cases
- Failure modes
- Recovery behaviour

If you fix a bug, add a test that would have caught it.

---

## 7. Commit Message Guidelines ✍️

Use clear, meaningful commit messages.

Examples:

Fix WebSocket reconnect loop
Add CPU profile fallback for missing sysfs entries
Improve Discord error handling
Update documentation for new config options

Avoid vague messages like “fix stuff”.

---

## 8. Pull Request Guidelines 📥

A good pull request includes:

- A clear description of the change
- Why the change is needed
- How it was tested
- Any limitations or follow‑up work
- Confirmation that tests pass

Small, focused pull requests are easier to review.

---

## 9. Code of Conduct 🤝

Contributors are expected to:

- Be respectful and constructive
- Welcome different viewpoints
- Focus on improving the project
- Avoid personal attacks or hostility

This project aims to be a friendly, collaborative environment.

---

## 10. Security Considerations 🔐

Because the monitor interacts with:

- Pterodactyl API tokens
- Discord webhooks
- Systemd
- sysfs CPU controls

Contributors must:

- Never commit secrets
- Never weaken systemd hardening
- Avoid adding unnecessary privileges
- Ensure new features fail safely

---

## 11. Thank You 🙌

Your contributions help make the Windrose Server Monitor more reliable, more capable, and easier for others to use.

Whether you’re fixing a typo or adding a major feature — you’re appreciated.
