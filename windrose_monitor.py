#!/usr/bin/env python3
"""
Windrose Server Monitor Patched
- Parser returns found_sections and uses AccountId as canonical id
- players_meta persisted in state
- Debug mode and unit test harness included
"""

import json
import logging
import logging.handlers
import time
import requests
import os
import sys
import threading
import base64
from collections import deque

logger = logging.getLogger("windrose-monitor")
logger.setLevel(logging.DEBUG)
try:
    import websocket
except Exception:
    logger.warning("websocket-client library not available; WebSocket log monitoring disabled")
    websocket = None
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Basic logging setup
log_dir = Path(os.getenv('LOG_DIR', '/var/log/windrose-monitor'))
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / 'windrose-monitor.log'
log_format = '%(asctime)s - %(levelname)s - %(message)s'
date_format = '%Y-%m-%d %H:%M:%S'

if not logger.handlers:
    fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    fh.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(fh)
    logger.addHandler(ch)

class WindroseMonitor:
    def __init__(self, config_path: str = '/etc/windrose-monitor/config.json'):
        self.config = self._load_config(config_path)
        self.state = self._load_state()
        self.api_session = requests.Session()
        token = self.config['pterodactyl']['api_token']
        if token:
            self.api_session.headers.update({'Authorization': f"Bearer {token}"})
        self._ws_buffer = deque(maxlen=int(os.getenv('WS_BUFFER_LINES', '10000')))
        self._ws_lock = threading.Lock()
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_stop = threading.Event()
        self._ws_token_data = None
        self._ws_token_expiry = 0
        self.debug = os.getenv('DEBUG_MONITOR', 'false').lower() == 'true'

        if websocket is not None:
            if self._ws_thread is None or not self._ws_thread.is_alive():
                logger.info("Starting WebSocket listener thread")
                self._ws_thread = threading.Thread(target=self._ws_listener, daemon=True)
                self._ws_thread.start()
        else:
            logger.warning("websocket-client not available; falling back to HTTP logs")

    def _load_config(self, config_path: str) -> Dict:
        cfg = {
            'pterodactyl': {
                'api_url': os.getenv('PTERODACTYL_API_URL', ''),
                'api_token': os.getenv('PTERODACTYL_API_TOKEN', ''),
                'server_id': os.getenv('PTERODACTYL_SERVER_ID', ''),
                'websocket_origin': os.getenv('PTERODACTYL_WEBSOCKET_ORIGIN', ''),
                'websocket_host': os.getenv('PTERODACTYL_WEBSOCKET_HOST', '')
            },
            'discord': {
                'webhook_url': os.getenv('DISCORD_WEBHOOK_URL', '')
            },
            'monitoring': {
                'check_interval_seconds': int(os.getenv('CHECK_INTERVAL_SECONDS', '20'))
            },
            'cpu_profile': {
                'enabled': os.getenv('CPU_PROFILE_ENABLED', 'true').lower() == 'true',
                'performance_profile': os.getenv('CPU_PROFILE_PERFORMANCE', 'performance'),
                'balanced_profile': os.getenv('CPU_PROFILE_BALANCED', 'balance_power'),
                'cpu_freq_path': os.getenv('CPU_FREQ_PATH', '/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference')
            },
            'state_file': os.getenv('STATE_FILE', '/var/lib/windrose-monitor/state.json')
        }

        if not cfg['pterodactyl']['api_token'] and Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    file_cfg = json.load(f)
                    for k, v in file_cfg.items():
                        if k not in cfg or not cfg[k]:
                            cfg[k] = v
            except Exception:
                logger.warning("Failed to read config file; using environment variables")

        # Minimal validation
        if not cfg['discord']['webhook_url']:
            logger.error("DISCORD_WEBHOOK_URL not configured")
            # Do not exit; allow tests to run without webhook
        return cfg

    def _load_state(self) -> Dict:
        state_file = Path(self.config.get('state_file', '/var/lib/windrose-monitor/state.json'))
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
            except Exception:
                logger.warning("State file invalid; starting fresh")
                state = {}
        else:
            state = {}
        state.setdefault('players', [])  # list of AccountIds
        state.setdefault('players_meta', {})  # { account_id: {name, last_seen, state} }
        state.setdefault('player_count', 0)
        state.setdefault('cpu_profile', 'balanced')
        state.setdefault('performance_counter', 0)
        state.setdefault('balanced_counter', 0)
        state.setdefault('last_update', None)
        return state

    def _save_state(self):
        state_file = Path(self.config.get('state_file', '/var/lib/windrose-monitor/state.json'))
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def _alert_ws_dead(self, reason: str):
        logger.warning(f"WebSocket issue: {reason}")

    def get_server_logs(self) -> Optional[str]:
        # Prefer websocket buffer if available
        if websocket is not None:
            with self._ws_lock:
                if len(self._ws_buffer) > 0:
                    return "\n".join(list(self._ws_buffer))
            # If buffer empty, try to validate token and return None to wait for live output
            token_data = self._get_websocket_token()
            if not token_data:
                logger.debug("WebSocket token unavailable")
                return None
            return None

        # Fallback to HTTP logs endpoint
        try:
            url = f"{self.config['pterodactyl']['api_url']}/api/client/servers/{self.config['pterodactyl']['server_id']}/logs"
            resp = self.api_session.get(url, timeout=10, headers={'Accept': 'Application/vnd.pterodactyl.v1+json'})
            resp.raise_for_status()
            data = resp.json()
            return data.get('attributes', {}).get('content', '')
        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
            return None

    def _get_websocket_token(self) -> Optional[dict]:
        # Minimal implementation; keep cached token if valid
        try:
            if self._ws_token_data and self._ws_token_expiry and time.time() < (self._ws_token_expiry - 30):
                return self._ws_token_data
            url = f"{self.config['pterodactyl']['api_url']}/api/client/servers/{self.config['pterodactyl']['server_id']}/websocket"
            resp = self.api_session.get(url, timeout=10, headers={'Accept': 'Application/vnd.pterodactyl.v1+json'})
            resp.raise_for_status()
            data = resp.json().get('data')
            token = data.get('token') if data else None
            if token:
                try:
                    parts = token.split('.')
                    if len(parts) >= 2:
                        payload = parts[1]
                        padding = "=" * ((4 - len(payload) % 4) % 4)
                        decoded = base64.urlsafe_b64decode(payload + padding)
                        payload_json = json.loads(decoded)
                        exp = int(payload_json.get('exp', 0))
                        self._ws_token_expiry = exp
                        self._ws_token_data = data
                except Exception:
                    self._ws_token_data = data
                    self._ws_token_expiry = 0
            return data
        except Exception as e:
            logger.debug(f"Could not obtain websocket token: {e}")
            return None

    def _ws_listener(self):
        backoff = 1
        while not self._ws_stop.is_set():
            token_data = self._get_websocket_token()
            if not token_data:
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue
            token = token_data.get('token')
            socket_url = token_data.get('socket')
            if not token or not socket_url:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            try:
                ws = websocket.create_connection(socket_url, timeout=15, origin=self.config['pterodactyl'].get('websocket_origin', ''), header=[f"Authorization: Bearer {token}"])
                auth_msg = json.dumps({"event": "auth", "args": [token]})
                ws.send(auth_msg)
                last_msg = time.time()
                backoff = 1
                while not self._ws_stop.is_set():
                    raw = ws.recv()
                    if not raw:
                        break
                    last_msg = time.time()
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    event = msg.get('event')
                    args = msg.get('args', [])
                    if event == 'console output' and args:
                        line = args[0]
                        with self._ws_lock:
                            self._ws_buffer.append(line)
                    if time.time() - last_msg > 30:
                        self._alert_ws_dead("stale socket")
                        break
                try:
                    ws.close()
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"WebSocket connect error: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)

    def parse_player_list(self, logs: str) -> Tuple[Dict[str, Dict[str, str]], bool]:
        """
        Parse the latest snapshot from logs and return:
        - active_by_id: { account_id: { 'name': display_name, 'state': state } }
        - found_any_section: bool
        Rules:
        - When 'Connected Accounts' header appears we clear previous snapshot data.
        - Active players = Connected U Reserved, excluding entries with state 'SaidFarewell'.
        """
        connected: Dict[str, Tuple[str, str]] = {}
        reserved: Dict[str, Tuple[str, str]] = {}
        disconnected: Dict[str, Tuple[str, str]] = {}
        current_section: Optional[str] = None
        found_any_section = False

        for line in logs.splitlines():
            if 'Connected Accounts' in line:
                connected.clear(); reserved.clear(); disconnected.clear()
                current_section = 'connected'; found_any_section = True; continue
            if 'Reserved Accounts' in line:
                current_section = 'reserved'; found_any_section = True; continue
            if 'Disconnected Accounts' in line:
                current_section = 'disconnected'; found_any_section = True; continue

            if current_section in ('connected', 'reserved', 'disconnected'):
                if "Name '" in line and "AccountId" in line:
                    try:
                        # Name extraction
                        nstart = line.find("Name '") + len("Name '")
                        nend = line.find("'", nstart)
                        name = line[nstart:nend].strip()

                        # AccountId extraction
                        astart = line.find("AccountId '") + len("AccountId '")
                        aend = line.find("'", astart)
                        account_id = line[astart:aend].strip()

                        # State extraction (optional)
                        state = None
                        s_marker = "State '"
                        sidx = line.find(s_marker)
                        if sidx != -1:
                            sstart = sidx + len(s_marker)
                            send = line.find("'", sstart)
                            state = line[sstart:send].strip()

                        if current_section == 'connected':
                            connected[account_id] = (name, state)
                        elif current_section == 'reserved':
                            reserved[account_id] = (name, state)
                        else:
                            disconnected[account_id] = (name, state)
                    except Exception:
                        continue

        # Build active map from latest snapshot
        active_by_id: Dict[str, Dict[str, str]] = {}
        for d in (connected, reserved):
            for aid, (name, state) in d.items():
                if state and state.lower() == 'saidfarewell':
                    continue
                active_by_id[aid] = {'name': name, 'state': state or ''}

        if self.debug:
            logger.debug(f"parse_player_list found_any_section={found_any_section} connected={list(connected.keys())} reserved={list(reserved.keys())} disconnected={list(disconnected.keys())}")

        return active_by_id, found_any_section

    def set_cpu_profile(self, profile: str) -> bool:
        if not self.config['cpu_profile']['enabled']:
            return True
        try:
            cpu_path_template = self.config['cpu_profile']['cpu_freq_path'].replace('cpu0', 'cpu{}')
            sys_cpu_path = '/sys/devices/system/cpu'
            cpu_count = 0
            for cpu_dir in Path(sys_cpu_path).glob('cpu[0-9]*'):
                try:
                    int(cpu_dir.name.replace('cpu', ''))
                    cpu_count += 1
                except Exception:
                    continue
            success = True
            for i in range(cpu_count):
                cpu_freq_path = cpu_path_template.format(i)
                try:
                    with open(cpu_freq_path, "w") as f:
                        f.write(profile)
                except Exception as e:
                    logger.warning(f"Failed to set CPU {i} to {profile}: {e}")
                    success = False
            if success:
                self.state['cpu_profile'] = profile
            return success
        except Exception as e:
            logger.error(f"Error changing CPU profile: {e}")
            return False

    def send_discord_message(self, message: str) -> bool:
        webhook = self.config['discord'].get('webhook_url')
        if not webhook:
            logger.debug(f"Discord webhook not configured; would send: {message}")
            return False
        try:
            payload = {'content': message, 'username': 'Windrose Server Monitor'}
            resp = requests.post(webhook, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return False

    def check_and_update(self):
        logger.info("Checking server status")
        logs = self.get_server_logs()
        if not logs:
            logger.debug("No logs available this tick")
            return

        current_map, found_sections = self.parse_player_list(logs)
        if not found_sections:
            logger.info("No player-list snapshot found in logs; skipping tick")
            return

        prev_players = set(self.state.get('players', []))
        prev_meta = self.state.get('players_meta', {})

        curr_players = set(current_map.keys())

        new_players = curr_players - prev_players
        left_players = prev_players - curr_players

        # Build messages in order: joins -> leaves -> count
        messages: List[str] = []
        for aid in sorted(new_players):
            display = current_map[aid]['name']
            messages.append(f"🎮 **Player Joined**: {display}")

        for aid in sorted(left_players):
            display = prev_meta.get(aid, {}).get('name', 'Unknown')
            messages.append(f"👋 **Player Left**: {display}")

        prev_count = self.state.get('player_count', 0)
        current_count = len(curr_players)
        if current_count != prev_count:
            messages.append(f"📊 **Player Count**: {current_count} (was {prev_count})")

        # Debug logging of before/after
        if self.debug:
            logger.debug(f"previous_players={sorted(prev_players)}")
            logger.debug(f"current_players={sorted(curr_players)}")
            logger.debug(f"new_players={sorted(new_players)} left_players={sorted(left_players)}")

        # Send messages in strict order
        for msg in messages:
            self.send_discord_message(msg)
            # small sleep to preserve ordering on remote webhook
            time.sleep(0.15)

        # Update players_meta and state
        now = datetime.now(timezone.utc).isoformat()
        self.state['players'] = list(curr_players)
        for aid, info in current_map.items():
            self.state['players_meta'][aid] = {
                'name': info['name'],
                'state': info.get('state', ''),
                'last_seen': now
            }
        # Remove metadata for players that left (optional: keep history)
        for aid in list(prev_meta.keys()):
            if aid not in curr_players:
                # keep historical meta but mark last_seen if desired
                self.state['players_meta'][aid].setdefault('last_left', now)

        self.state['player_count'] = current_count
        self.state['last_update'] = now

        # CPU hysteresis
        if current_count > 0:
            self.state['performance_counter'] = self.state.get('performance_counter', 0) + 1
            self.state['balanced_counter'] = 0
            if self.state['performance_counter'] >= 2 and self.state.get('cpu_profile') != 'performance':
                logger.info("Switching to performance CPU profile")
                self.set_cpu_profile(self.config['cpu_profile']['performance_profile'])
        else:
            self.state['balanced_counter'] = self.state.get('balanced_counter', 0) + 1
            self.state['performance_counter'] = 0
            if self.state['balanced_counter'] >= 3 and self.state.get('cpu_profile') != 'balanced':
                logger.info("Switching to balanced CPU profile")
                self.set_cpu_profile(self.config['cpu_profile']['balanced_profile'])

        self._save_state()

    def run(self):
        logger.info("Starting monitor loop")
        try:
            while True:
                try:
                    self.check_and_update()
                except Exception as e:
                    logger.error(f"Error in check_and_update: {e}", exc_info=True)
                time.sleep(self.config['monitoring']['check_interval_seconds'])
        except KeyboardInterrupt:
            logger.info("Stopping monitor")
            self._ws_stop.set()

# If run as script, start monitor
if __name__ == '__main__':
    monitor = WindroseMonitor()
    monitor.run()
