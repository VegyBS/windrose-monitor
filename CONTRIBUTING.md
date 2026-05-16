# Contributing to Windrose Monitor

Thanks for your interest in contributing! This document explains how to get started.

## How to Contribute

### Reporting Bugs

- Use the GitHub issue tracker with the **Bug Report** template
- Include logs from `journalctl -u windrose-monitor`
- Include your Ubuntu version and Python version
- Describe steps to reproduce the issue

### Suggesting Features

- Use the **Feature Request** template
- Explain the use case and why it would be useful
- Reference similar features in other projects if applicable

### Writing Code

1. **Fork the repository**
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**:
   - Follow the existing code style
   - Add comments for complex logic
   - Update documentation as needed

4. **Test your changes**:
   ```bash
   python3 test_config.py
   python3 windrose_monitor.py  # Test in foreground
   ```

5. **Commit with clear messages**:
   ```bash
   git commit -m "Add feature: description of what you changed"
   ```

6. **Push to your fork** and **create a Pull Request**

## Development Setup

### Local Testing

```bash
# Install dependencies
pip3 install -r requirements.txt

# Test configuration validator
python3 test_config.py

# Run monitor in foreground (Ctrl+C to stop)
python3 windrose_monitor.py
```

### Code Standards

- Use Python 3.7+ syntax
- Follow PEP 8 style guide
- Add docstrings to functions
- Use type hints where possible
- Keep functions focused and readable

### Documentation

- Update relevant markdown files if you change functionality
- Include examples for new features
- Update config.example.json if you add new options
- Document any new dependencies in requirements.txt

## Pull Request Process

1. Update your local repository:
   ```bash
   git pull origin main
   ```

2. Ensure your code passes testing
3. Write a clear PR description explaining:
   - What problem this solves
   - How to test the changes
   - Any breaking changes
4. Link related issues: `Fixes #123`

## Areas for Contribution

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
- [ ] Grafana dashboard examples

### Testing
- [ ] Unit tests for core functions
- [ ] Integration tests with mock Pterodactyl API
- [ ] Performance tests under load

### Features
- [ ] Telegram/Slack notification support
- [ ] Player session tracking and statistics
- [ ] Server performance monitoring (CPU, RAM, network)
- [ ] Discord command for server status
- [ ] Multiple server support
- [ ] Database backend for historical data

## Questions?

- Check existing issues and documentation first
- Open a discussion or Q&A issue
- Read through the SETUP.md and QUICKREF.md

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
