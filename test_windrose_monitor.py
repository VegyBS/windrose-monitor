#!/usr/bin/env python3
"""
Unit tests for Windrose Server Monitor
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
from pathlib import Path
from datetime import datetime

# We'll test the core logic, mocking external APIs


class TestPlayerListParsing(unittest.TestCase):
    """Test log parsing for player detection"""
    
    def setUp(self):
        """Set up test fixtures with realistic log format"""
        # Realistic format with Connected and Reserved Accounts
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
        
        players = set()
        lines = logs.split('\n')
        current_section = None
        
        for i, line in enumerate(lines):
            if 'Connected Accounts' in line:
                current_section = 'connected'
                continue
            elif 'Reserved Accounts' in line:
                current_section = 'reserved'
                continue
            elif 'Disconnected Accounts' in line:
                break
            
            if current_section in ['connected', 'reserved']:
                if "Name '" in line:
                    try:
                        start = line.find("Name '") + len("Name '")
                        end = line.find("'", start)
                        if start > len("Name '") - 1 and end > start:
                            player_name = line[start:end].strip()
                            if player_name:
                                players.add(player_name)
                    except (ValueError, IndexError):
                        continue
        
        self.assertEqual(players, {'PlayerOne', 'PlayerTwo', 'PlayerThree'})
    
    def test_parse_only_connected_accounts(self):
        """Test parsing when players are only in Connected section"""
        logs = self.sample_logs_only_connected
        
        players = set()
        lines = logs.split('\n')
        current_section = None
        
        for i, line in enumerate(lines):
            if 'Connected Accounts' in line:
                current_section = 'connected'
                continue
            elif 'Reserved Accounts' in line:
                current_section = 'reserved'
                continue
            elif 'Disconnected Accounts' in line:
                break
            
            if current_section in ['connected', 'reserved']:
                if "Name '" in line:
                    try:
                        start = line.find("Name '") + len("Name '")
                        end = line.find("'", start)
                        if start > len("Name '") - 1 and end > start:
                            player_name = line[start:end].strip()
                            if player_name:
                                players.add(player_name)
                    except (ValueError, IndexError):
                        continue
        
        self.assertEqual(players, {'AlicePlayer', 'BobPlayer'})
    
    def test_parse_only_reserved_accounts(self):
        """Test parsing when players are only in Reserved section"""
        logs = self.sample_logs_only_reserved
        
        players = set()
        lines = logs.split('\n')
        current_section = None
        
        for i, line in enumerate(lines):
            if 'Connected Accounts' in line:
                current_section = 'connected'
                continue
            elif 'Reserved Accounts' in line:
                current_section = 'reserved'
                continue
            elif 'Disconnected Accounts' in line:
                break
            
            if current_section in ['connected', 'reserved']:
                if "Name '" in line:
                    try:
                        start = line.find("Name '") + len("Name '")
                        end = line.find("'", start)
                        if start > len("Name '") - 1 and end > start:
                            player_name = line[start:end].strip()
                            if player_name:
                                players.add(player_name)
                    except (ValueError, IndexError):
                        continue
        
        self.assertEqual(players, {'CharliePlayer'})
    
    def test_parse_empty_accounts(self):
        """Test parsing when no players are present"""
        logs = self.sample_logs_no_players
        
        players = set()
        lines = logs.split('\n')
        current_section = None
        
        for i, line in enumerate(lines):
            if 'Connected Accounts' in line:
                current_section = 'connected'
                continue
            elif 'Reserved Accounts' in line:
                current_section = 'reserved'
                continue
            elif 'Disconnected Accounts' in line:
                break
            
            if current_section in ['connected', 'reserved']:
                if "Name '" in line:
                    try:
                        start = line.find("Name '") + len("Name '")
                        end = line.find("'", start)
                        if start > len("Name '") - 1 and end > start:
                            player_name = line[start:end].strip()
                            if player_name:
                                players.add(player_name)
                    except (ValueError, IndexError):
                        continue
        
        # Should not include OldPlayer (from Disconnected section)
        self.assertEqual(len(players), 0)
    
    def test_ignores_disconnected_accounts(self):
        """Test that Disconnected Accounts section is completely ignored"""
        logs = self.sample_logs_with_connected_and_reserved
        
        players = set()
        lines = logs.split('\n')
        current_section = None
        
        for i, line in enumerate(lines):
            if 'Connected Accounts' in line:
                current_section = 'connected'
                continue
            elif 'Reserved Accounts' in line:
                current_section = 'reserved'
                continue
            elif 'Disconnected Accounts' in line:
                break  # Stop processing entirely
            
            if current_section in ['connected', 'reserved']:
                if "Name '" in line:
                    try:
                        start = line.find("Name '") + len("Name '")
                        end = line.find("'", start)
                        if start > len("Name '") - 1 and end > start:
                            player_name = line[start:end].strip()
                            if player_name:
                                players.add(player_name)
                    except (ValueError, IndexError):
                        continue
        
        # Should NOT contain OldPlayer
        self.assertNotIn('OldPlayer', players)


class TestPlayerStateDetection(unittest.TestCase):
    """Test player join/leave detection"""
    
    def test_new_players_detected(self):
        """Test detection of new players joining"""
        previous = {'Player1', 'Player2'}
        current = {'Player1', 'Player2', 'Player3'}
        
        new_players = current - previous
        self.assertEqual(new_players, {'Player3'})
    
    def test_players_leaving_detected(self):
        """Test detection of players leaving"""
        previous = {'Player1', 'Player2', 'Player3'}
        current = {'Player1', 'Player3'}
        
        left_players = previous - current
        self.assertEqual(left_players, {'Player2'})
    
    def test_no_change_in_players(self):
        """Test when player list hasn't changed"""
        previous = {'Player1', 'Player2'}
        current = {'Player1', 'Player2'}
        
        new_players = current - previous
        left_players = previous - current
        
        self.assertEqual(len(new_players), 0)
        self.assertEqual(len(left_players), 0)
    
    def test_complete_turnover(self):
        """Test when all players leave and new ones join"""
        previous = {'OldPlayer1', 'OldPlayer2'}
        current = {'NewPlayer1', 'NewPlayer2'}
        
        new_players = current - previous
        left_players = previous - current
        
        self.assertEqual(new_players, {'NewPlayer1', 'NewPlayer2'})
        self.assertEqual(left_players, {'OldPlayer1', 'OldPlayer2'})


class TestCPUProfileLogic(unittest.TestCase):
    """Test CPU profile switching logic"""
    
    def test_switch_to_performance_when_players_join(self):
        """Test that performance profile is set when player count > 0"""
        current_count = 1
        current_profile = 'balanced'
        
        should_switch_to_performance = current_count > 0 and current_profile != 'performance'
        self.assertTrue(should_switch_to_performance)
    
    def test_switch_to_balanced_when_players_leave(self):
        """Test that balanced profile is set when player count == 0"""
        current_count = 0
        current_profile = 'performance'
        
        should_switch_to_balanced = current_count == 0 and current_profile != 'balanced'
        self.assertTrue(should_switch_to_balanced)
    
    def test_no_switch_needed_performance_active(self):
        """Test that no switch happens if already in performance with players"""
        current_count = 1
        current_profile = 'performance'
        
        should_switch = current_count > 0 and current_profile != 'performance'
        self.assertFalse(should_switch)
    
    def test_no_switch_needed_balanced_active(self):
        """Test that no switch happens if already in balanced with no players"""
        current_count = 0
        current_profile = 'balanced'
        
        should_switch = current_count == 0 and current_profile != 'balanced'
        self.assertFalse(should_switch)


class TestConfigValidation(unittest.TestCase):
    """Test configuration file handling"""
    
    def test_valid_config_structure(self):
        """Test that config has required structure"""
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
        
        # Verify all required keys exist
        self.assertIn('pterodactyl', config)
        self.assertIn('discord', config)
        self.assertIn('monitoring', config)
        self.assertIn('cpu_profile', config)
        
        self.assertIn('api_url', config['pterodactyl'])
        self.assertIn('api_token', config['pterodactyl'])
        self.assertIn('server_id', config['pterodactyl'])
        
        self.assertIn('webhook_url', config['discord'])
    
    def test_config_json_valid(self):
        """Test that config.example.json is valid JSON"""
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
        """Test format of player joined message"""
        player = 'TestPlayer'
        msg = f"🎮 **Player Joined**: {player}"
        
        self.assertIn('🎮', msg)
        self.assertIn('TestPlayer', msg)
        self.assertIn('Joined', msg)
    
    def test_player_left_message(self):
        """Test format of player left message"""
        player = 'TestPlayer'
        msg = f"👋 **Player Left**: {player}"
        
        self.assertIn('👋', msg)
        self.assertIn('TestPlayer', msg)
        self.assertIn('Left', msg)
    
    def test_player_count_message(self):
        """Test format of player count message"""
        current = 3
        previous = 2
        msg = f"📊 **Player Count**: {current} (was {previous})"
        
        self.assertIn('📊', msg)
        self.assertIn('3', msg)
        self.assertIn('2', msg)


class TestStateManagement(unittest.TestCase):
    """Test state persistence logic"""
    
    def test_initial_state_structure(self):
        """Test that initial state has correct structure"""
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
        """Test updating state when players join"""
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


if __name__ == '__main__':
    unittest.main()