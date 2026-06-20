#!/usr/bin/env python3
"""
Fixed unit tests for Windrose Server Monitor

This test module ensures the monitor does not attempt to create /var/log at import time
by setting LOG_DIR and STATE_FILE environment variables to writable temporary locations
before importing the monitor module.

It preserves your original unittest-style tests with minimal changes.
"""

import os
import tempfile
import shutil
import unittest
import json
from pathlib import Path
from datetime import datetime

# --- Ensure tests run in a writable environment before importing the monitor ---
# Create a temporary directory for logs and state and export env vars so the module
# uses these paths instead of /var/log or /var/lib.
_TEST_TMPDIR = tempfile.mkdtemp(prefix="windrose_test_")
os.environ.setdefault("LOG_DIR", os.path.join(_TEST_TMPDIR, "logs"))
os.environ.setdefault("STATE_FILE", os.path.join(_TEST_TMPDIR, "state.json"))

# Ensure the directories exist so import-time code that checks them won't fail
os.makedirs(os.environ["LOG_DIR"], exist_ok=True)
state_parent = os.path.dirname(os.environ["STATE_FILE"])
if state_parent:
    os.makedirs(state_parent, exist_ok=True)

# Try to import the monitor.
try:
    from windrose_monitor import WindroseMonitor  # type: ignore
except Exception:
    raise

# --- Test cases


class TestPlayerListParsing(unittest.TestCase):
    """Test log parsing for player detection"""

    def setUp(self):
        # Create a fresh monitor instance for each test
        self.monitor = WindroseMonitor()
        # Ensure monitor uses our test-safe paths
        self.monitor.config['discord']['webhook_url'] = ''
        # Reset state to a known baseline
        self.monitor.state = {
            'players': [],
            'players_meta': {},
            'player_count': 0,
            'performance_counter': 0,
            'balanced_counter': 0
        }

        # Sample realistic log formats
        self.sample_logs_with_connected_and_reserved = """
[2026-05-16 10:30:00] Server Status Update
Connected Accounts
    1. Name 'PlayerOne'. AccountId 'ID123'. State 'ReadyToPlay'. NetAddress '192.168.1.1'
    2. Name 'PlayerTwo'. AccountId 'ID456'. State 'ReadyToPlay'. NetAddress '192.168.1.2'
Reserved Accounts
    1. Name 'PlayerThree'. AccountId 'ID789'. State 'Reserved'. NetAddress '192.168.1.3'
Disconnected Accounts
    1. Name 'OldPlayer'. State 'SaidFarewell'. AccountId 'IDXYZ'
"""

        self.sample_logs_only_connected = """
[2026-05-16 10:30:00] Server Status Update
Connected Accounts
    1. Name 'AlicePlayer'. AccountId 'IDABC'. State 'ReadyToPlay'. NetAddress '10.0.0.1'
    2. Name 'BobPlayer'. AccountId 'IDDEF'. State 'ReadyToPlay'. NetAddress '10.0.0.2'
Reserved Accounts
Disconnected Accounts
"""

        self.sample_logs_only_reserved = """
[2026-05-16 10:30:00] Server Status Update
Connected Accounts
Reserved Accounts
    1. Name 'CharliePlayer'. AccountId 'IDGHI'. State 'Reserved'. NetAddress '10.0.0.3'
Disconnected Accounts
"""

        self.sample_logs_no_players = """
[2026-05-16 10:30:00] Server Status Update
Connected Accounts
Reserved Accounts
Disconnected Accounts
    1. Name 'OldPlayer'. State 'SaidFarewell'. AccountId 'IDXYZ'
"""

        self.sample_logs_empty = """
[2026-05-16 10:30:00] Server Status Update
Connected Accounts
Reserved Accounts
Disconnected Accounts
"""

    def test_parse_connected_and_reserved_accounts(self):
        """Test parsing when players are in both Connected and Reserved"""
        logs = self.sample_logs_with_connected_and_reserved
        active, found = self.monitor.parse_player_list(logs)
        self.assertTrue(found)
        # Expect AccountIds for PlayerOne, PlayerTwo, PlayerThree
        self.assertIn('ID123', active)
        self.assertIn('ID456', active)
        self.assertIn('ID789', active)
        # Disconnected account should not be present
        self.assertNotIn('IDXYZ', active)

    def test_parse_only_connected_accounts(self):
        """Test parsing when players are only in Connected section"""
        logs = self.sample_logs_only_connected
        active, found = self.monitor.parse_player_list(logs)
        self.assertTrue(found)
        self.assertIn('IDABC', active)
        self.assertIn('IDDEF', active)
        self.assertEqual(active['IDABC']['name'], 'AlicePlayer')

    def test_parse_only_reserved_accounts(self):
        """Test parsing when players are only in Reserved section"""
        logs = self.sample_logs_only_reserved
        active, found = self.monitor.parse_player_list(logs)
        self.assertTrue(found)
        self.assertIn('IDGHI', active)
        self.assertEqual(active['IDGHI']['name'], 'CharliePlayer')

    def test_parse_empty_accounts(self):
        """Test parsing when no players are present"""
        logs = self.sample_logs_no_players
        active, found = self.monitor.parse_player_list(logs)
        self.assertTrue(found)
        # No active players expected
        self.assertEqual(len(active), 0)

    def test_ignores_disconnected_accounts(self):
        """Test that Disconnected Accounts section is ignored for active players"""
        logs = self.sample_logs_with_connected_and_reserved
        active, found = self.monitor.parse_player_list(logs)
        self.assertTrue(found)
        self.assertNotIn('IDXYZ', active)


class TestPlayerStateDetection(unittest.TestCase):
    """Test player join/leave detection"""

    def test_new_players_detected(self):
        previous = {'Player1', 'Player2'}
        current = {'Player1', 'Player2', 'Player3'}
        new_players = current - previous
        self.assertEqual(new_players, {'Player3'})

    def test_players_leaving_detected(self):
        previous = {'Player1', 'Player2', 'Player3'}
        current = {'Player1', 'Player3'}
        left_players = previous - current
        self.assertEqual(left_players, {'Player2'})

    def test_no_change_in_players(self):
        previous = {'Player1', 'Player2'}
        current = {'Player1', 'Player2'}
        new_players = current - previous
        left_players = previous - current
        self.assertEqual(len(new_players), 0)
        self.assertEqual(len(left_players), 0)

    def test_complete_turnover(self):
        previous = {'OldPlayer1', 'OldPlayer2'}
        current = {'NewPlayer1', 'NewPlayer2'}
        new_players = current - previous
        left_players = previous - current
        self.assertEqual(new_players, {'NewPlayer1', 'NewPlayer2'})
        self.assertEqual(left_players, {'OldPlayer1', 'OldPlayer2'})


class TestCPUProfileLogic(unittest.TestCase):
    """Test CPU profile switching logic"""

    def test_switch_to_performance_when_players_join(self):
        current_count = 1
        current_profile = 'balanced'
        should_switch_to_performance = current_count > 0 and current_profile != 'performance'
        self.assertTrue(should_switch_to_performance)

    def test_switch_to_balanced_when_players_leave(self):
        current_count = 0
        current_profile = 'performance'
        should_switch_to_balanced = current_count == 0 and current_profile != 'balanced'
        self.assertTrue(should_switch_to_balanced)

    def test_no_switch_needed_performance_active(self):
        current_count = 1
        current_profile = 'performance'
        should_switch = current_count > 0 and current_profile != 'performance'
        self.assertFalse(should_switch)

    def test_no_switch_needed_balanced_active(self):
        current_count = 0
        current_profile = 'balanced'
        should_switch = current_count == 0 and current_profile != 'balanced'
        self.assertFalse(should_switch)


class TestConfigValidation(unittest.TestCase):
    """Test configuration file handling"""

    def test_valid_config_structure(self):
        config = {
            'pterodactyl': {
                'api_url': 'https://example.com',
                'api_token': 'token',
                'server_id': 'uuid'
            },
            'discord': {
                'webhook_url': 'https://discord.com/api/webhooks/...'
            },
            'monitoring': {
                'check_interval_seconds': 20
            },
            'cpu_profile': {
                'enabled': True
            }
        }
        self.assertIn('pterodactyl', config)
        self.assertIn('discord', config)
        self.assertIn('monitoring', config)
        self.assertIn('cpu_profile', config)
        self.assertIn('api_url', config['pterodactyl'])
        self.assertIn('api_token', config['pterodactyl'])
        self.assertIn('server_id', config['pterodactyl'])
        self.assertIn('webhook_url', config['discord'])

    def test_config_json_valid(self):
        config_path = Path(__file__).parent / 'config.example.json'
        if config_path.exists():
            with open(config_path, 'r') as f:
                try:
                    config = json.load(f)
                    self.assertIsInstance(config, dict)
                except json.JSONDecodeError:
                    self.fail("config.example.json is not valid JSON")


class TestDiscordMessageFormat(unittest.TestCase):
    """Test Discord message formatting"""

    def test_player_joined_message(self):
        player = 'TestPlayer'
        msg = f"🎮 **Player Joined**: {player}"
        self.assertIn('🎮', msg)
        self.assertIn('TestPlayer', msg)
        self.assertIn('Joined', msg)

    def test_player_left_message(self):
        player = 'TestPlayer'
        msg = f"👋 **Player Left**: {player}"
        self.assertIn('👋', msg)
        self.assertIn('TestPlayer', msg)
        self.assertIn('Left', msg)

    def test_player_count_message(self):
        current = 3
        previous = 2
        msg = f"📊 **Player Count**: {current} (was {previous})"
        self.assertIn('📊', msg)
        self.assertIn('3', msg)
        self.assertIn('2', msg)


class TestStateManagement(unittest.TestCase):
    """Test state persistence logic"""

    def test_initial_state_structure(self):
        state = {
            'players': [],
            'player_count': 0,
            'last_update': None,
            'cpu_profile': 'balanced'
        }
        self.assertIsInstance(state['players'], list)
        self.assertEqual(state['player_count'], 0)
        self.assertIsNone(state['last_update'])
        self.assertEqual(state['cpu_profile'], 'balanced')

    def test_state_update_with_players(self):
        state = {
            'players': [],
            'player_count': 0,
            'last_update': None,
            'cpu_profile': 'balanced'
        }
        current_players = {'Player1', 'Player2'}
        state['players'] = list(current_players)
        state['player_count'] = len(current_players)
        state['last_update'] = datetime.now().isoformat()
        self.assertEqual(state['player_count'], 2)
        self.assertEqual(len(state['players']), 2)
        self.assertIsNotNone(state['last_update'])


# --- Cleanup temporary directories after tests finish ---
def tearDownModule():
    try:
        shutil.rmtree(_TEST_TMPDIR)
    except Exception:
        # Best-effort cleanup; do not raise during test teardown
        pass


if __name__ == '__main__':
    unittest.main()
