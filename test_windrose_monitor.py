# test_windrose_monitor_pytest.py
import json
import pytest
from pathlib import Path
from datetime import datetime
from windrose_monitor import WindroseMonitor

# Sample snapshots used across tests
SAMPLE_SNAPSHOT_1 = """
Connected Accounts
Reserved Accounts
    1. Name 'Adazio'. AccountId 'AA83AD724AAA0CA42C13D899D09D6F45'. State 'WaitingForClientIsReady'. NetAddress '86.16.78.230'
Disconnected Accounts
    1. Name 'Papa Shango'. AccountId '21B48274495BA38F9AFAB29BC7322C53'. State 'SaidFarewell'.
"""

SAMPLE_SNAPSHOT_2 = """
Connected Accounts
    1. Name 'Adazio'. AccountId 'AA83AD724AAA0CA42C13D899D09D6F45'. State 'ReadyToPlay'. NetAddress '86.16.78.230'
    2. Name 'Poxy Squidwrangler'. AccountId '2108354A4A7AAD84BE03AD80448AAEBA'. State 'ReadyToPlay'. NetAddress '86.16.78.230'
Reserved Accounts
    1. Name 'Scratchnsniff'. AccountId 'AB15F3C4401E6A80CB58B8BD2C5EA01D'. State 'WaitingForClientIsReady'. NetAddress '88.97.202.94'
Disconnected Accounts
    1. Name 'Papa Shango'. AccountId '21B48274495BA38F9AFAB29BC7322C53'. State 'SaidFarewell'.
"""

NO_SNAPSHOT = "Some random log line\nAnother unrelated line\n"


@pytest.fixture
def monitor(tmp_path, monkeypatch):
    """
    Create a WindroseMonitor instance with isolated state and no network calls.
    Use tmp_path for state file to avoid touching system paths.
    """
    # Ensure the monitor uses a temporary state file
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("STATE_FILE", str(state_file))
    m = WindroseMonitor()
    # Disable actual Discord webhook
    m.config['discord']['webhook_url'] = ''
    # Start with a clean state
    m.state = {
        'players': [],
        'players_meta': {},
        'player_count': 0,
        'performance_counter': 0,
        'balanced_counter': 0
    }
    return m


# Parser and snapshot behavior tests

def test_parse_returns_ids_and_found_flag(monitor):
    active, found = monitor.parse_player_list(SAMPLE_SNAPSHOT_1)
    assert found is True
    assert 'AA83AD724AAA0CA42C13D899D09D6F45' in active
    assert active['AA83AD724AAA0CA42C13D899D09D6F45']['name'] == 'Adazio'
    # Disconnected account should not be present
    assert '21B48274495BA38F9AFAB29BC7322C53' not in active


def test_parser_handles_connected_reserved_and_disconnected(monitor):
    active2, found2 = monitor.parse_player_list(SAMPLE_SNAPSHOT_2)
    assert found2 is True
    assert 'AA83AD724AAA0CA42C13D899D09D6F45' in active2
    assert '2108354A4A7AAD84BE03AD80448AAEBA' in active2
    assert 'AB15F3C4401E6A80CB58B8BD2C5EA01D' in active2
    assert active2['AB15F3C4401E6A80CB58B8BD2C5EA01D']['state'] == 'WaitingForClientIsReady'


def test_skip_tick_without_snapshot(monitor, monkeypatch):
    # If logs contain no snapshot headers, check_and_update should skip and not change state
    monkeypatch.setattr(monitor, 'get_server_logs', lambda: NO_SNAPSHOT)
    prev_players = list(monitor.state['players'])
    monitor.check_and_update()
    assert monitor.state['players'] == prev_players
    assert monitor.state['player_count'] == 0


# Integration-like behavior tests (mocking network calls)

def test_check_and_update_persists_players_meta_and_message_order(monitor, monkeypatch):
    # Simulate two ticks: first snapshot then second snapshot
    logs_sequence = [SAMPLE_SNAPSHOT_1, SAMPLE_SNAPSHOT_2]
    monkeypatch.setattr(monitor, 'get_server_logs', lambda: logs_sequence.pop(0))
    sent = []

    def fake_send(msg):
        sent.append(msg)
        return True

    monkeypatch.setattr(monitor, 'send_discord_message', fake_send)

    # First tick: Adazio appears (Reserved)
    monitor.check_and_update()
    assert len(monitor.state['players']) == 1
    assert 'AA83AD724AAA0CA42C13D899D09D6F45' in monitor.state['players_meta']

    # Second tick: Poxy and Scratchnsniff join
    monitor.check_and_update()
    assert len(monitor.state['players']) == 3

    # Ensure join messages were emitted and count message exists
    assert any("Player Joined" in m for m in sent)
    assert any("Player Count" in m for m in sent)

    # Verify ordering: all join messages appear before the first count message
    first_count_idx = next(i for i, m in enumerate(sent) if "Player Count" in m)
    join_indices = [i for i, m in enumerate(sent) if "Player Joined" in m]
    assert all(j < first_count_idx for j in join_indices)


# Keep original set-difference logic tests (still valid)

def test_new_players_detected():
    previous = {'Player1', 'Player2'}
    current = {'Player1', 'Player2', 'Player3'}
    new_players = current - previous
    assert new_players == {'Player3'}


def test_players_leaving_detected():
    previous = {'Player1', 'Player2', 'Player3'}
    current = {'Player1', 'Player3'}
    left_players = previous - current
    assert left_players == {'Player2'}


def test_no_change_in_players():
    previous = {'Player1', 'Player2'}
    current = {'Player1', 'Player2'}
    new_players = current - previous
    left_players = previous - current
    assert len(new_players) == 0
    assert len(left_players) == 0


def test_complete_turnover():
    previous = {'OldPlayer1', 'OldPlayer2'}
    current = {'NewPlayer1', 'NewPlayer2'}
    new_players = current - previous
    left_players = previous - current
    assert new_players == {'NewPlayer1', 'NewPlayer2'}
    assert left_players == {'OldPlayer1', 'OldPlayer2'}


# CPU profile logic tests (kept as simple boolean checks)

def test_switch_to_performance_when_players_join():
    current_count = 1
    current_profile = 'balanced'
    should_switch_to_performance = current_count > 0 and current_profile != 'performance'
    assert should_switch_to_performance


def test_switch_to_balanced_when_players_leave():
    current_count = 0
    current_profile = 'performance'
    should_switch_to_balanced = current_count == 0 and current_profile != 'balanced'
    assert should_switch_to_balanced


def test_no_switch_needed_performance_active():
    current_count = 1
    current_profile = 'performance'
    should_switch = current_count > 0 and current_profile != 'performance'
    assert not should_switch


def test_no_switch_needed_balanced_active():
    current_count = 0
    current_profile = 'balanced'
    should_switch = current_count == 0 and current_profile != 'balanced'
    assert not should_switch


# Config validation tests

def test_valid_config_structure():
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
    assert 'pterodactyl' in config
    assert 'discord' in config
    assert 'monitoring' in config
    assert 'cpu_profile' in config
    assert 'api_url' in config['pterodactyl']
    assert 'api_token' in config['pterodactyl']
    assert 'server_id' in config['pterodactyl']
    assert 'webhook_url' in config['discord']


def test_config_json_valid(tmp_path):
    config_path = Path(__file__).parent / 'config.example.json'
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
            assert isinstance(config, dict)


# Discord message format tests

def test_player_joined_message_format():
    player = 'TestPlayer'
    msg = f"🎮 **Player Joined**: {player}"
    assert '🎮' in msg
    assert 'TestPlayer' in msg
    assert 'Joined' in msg


def test_player_left_message_format():
    player = 'TestPlayer'
    msg = f"👋 **Player Left**: {player}"
    assert '👋' in msg
    assert 'TestPlayer' in msg
    assert 'Left' in msg


def test_player_count_message_format():
    current = 3
    previous = 2
    msg = f"📊 **Player Count**: {current} (was {previous})"
    assert '📊' in msg
    assert '3' in msg
    assert '2' in msg


# State management tests

def test_initial_state_structure():
    state = {
        'players': [],
        'player_count': 0,
        'last_update': None,
        'cpu_profile': 'balanced'
    }
    assert isinstance(state['players'], list)
    assert state['player_count'] == 0
    assert state['last_update'] is None
    assert state['cpu_profile'] == 'balanced'


def test_state_update_with_players():
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
    assert state['player_count'] == 2
    assert len(state['players']) == 2
    assert state['last_update'] is not None
