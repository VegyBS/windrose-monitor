#!/usr/bin/env python3
"""
Windrose Server Monitor
Monitors player count, manages CPU profiles, and sends Discord notifications
"""

import json
import logging
import logging.handlers
import time
import requests
import os
import subprocess
import sys
import threading
import ssl
import base64
from collections import deque
try:
    import websocket
except Exception:
    websocket = None
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
from typing import Dict, List, Set, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create log directory if it doesn't exist
log_dir = Path('/var/log/windrose-monitor')
log_dir.mkdir(parents=True, exist_ok=True)

# Configure logging with timestamps
log_format = '%(asctime)s - %(levelname)s - %(message)s'
log_file = '/var/log/windrose-monitor/windrose-monitor.log'

# Set up file handler with rotation
file_handler = logging.handlers.RotatingFileHandler(
    log_file,
    maxBytes=10485760,  # 10MB
    backupCount=5
)
file_handler.setFormatter(logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S'))

# Set up console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S'))

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


class WindroseMonitor:
    def __init__(self, config_path: str = '/etc/windrose-monitor/config.json'):
        """Initialize the monitor with configuration"""
        self.config = self._load_config(config_path)
        self.state = self._load_state()
        self.api_session = requests.Session()
        self.api_session.headers.update({
            'Authorization': f"Bearer {self.config['pterodactyl']['api_token']}"
        })
        # WebSocket console buffer and listener
        self._ws_buffer = deque(maxlen=5000)
        self._ws_lock = threading.Lock()
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_stop = threading.Event()

        # Cached websocket token data to avoid hitting token endpoint repeatedly
        self._ws_token_data = None
        self._ws_token_expiry = 0

        # Start websocket listener thread if websocket-client is available
        if websocket is not None:
            if self._ws_thread is None or not self._ws_thread.is_alive():
                logger.info("websocket-client available, starting WebSocket listener thread")
                self._ws_thread = threading.Thread(target=self._ws_listener, daemon=True)
                self._ws_thread.start()
            else:
                logger.info("WebSocket listener thread already running; not starting another")
        else:
            logger.warning("websocket-client library not available; WebSocket log streaming disabled")
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from environment variables or JSON file
        
        Priority:
        1. Environment variables (.env file)
        2. config.json file (fallback)
        """
        config = {
            'pterodactyl': {
                'api_url': os.getenv('PTERODACTYL_API_URL', ''),
                'api_token': os.getenv('PTERODACTYL_API_TOKEN', ''),
                'server_id': os.getenv('PTERODACTYL_SERVER_ID', ''),
                # Optional websocket overrides (when running on same host or behind proxies)
                'websocket_origin': os.getenv('PTERODACTYL_WEBSOCKET_ORIGIN', ''),
                'websocket_host': os.getenv('PTERODACTYL_WEBSOCKET_HOST', '')
            },
            'discord': {
                'webhook_url': os.getenv('DISCORD_WEBHOOK_URL', '')
            },
            'monitoring': {
                'check_interval_seconds': int(os.getenv('CHECK_INTERVAL_SECONDS', '20')),
                'log_patterns': {
                    'reserved_accounts_header': 'Reserved Accounts',
                    'disconnected_accounts_header': 'Disconnected Accounts'
                }
            },
            'cpu_profile': {
                'enabled': os.getenv('CPU_PROFILE_ENABLED', 'true').lower() == 'true',
                'performance_profile': os.getenv('CPU_PROFILE_PERFORMANCE', 'performance'),
                'balanced_profile': os.getenv('CPU_PROFILE_BALANCED', 'balance_power'),
                'cpu_freq_path': os.getenv('CPU_FREQ_PATH', '/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference')
            },
            'state_file': os.getenv('STATE_FILE', '/var/lib/windrose-monitor/state.json'),
            'log_file': os.getenv('LOG_FILE', '/var/log/windrose-monitor/windrose-monitor.log')
        }
        
        # If env vars not fully populated, try loading from config file as fallback
        if not config['pterodactyl']['api_token'] and Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                    # Merge file config with env config (env takes precedence)
                    for section in file_config:
                        if section not in config or not config[section]:
                            config[section] = file_config[section]
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in config file: {e}")
        
        # Validate required fields
        if not config['pterodactyl']['api_token']:
            logger.error("Pterodactyl API token not configured (set PTERODACTYL_API_TOKEN env var or in config.json)")
            sys.exit(1)
        if not config['pterodactyl']['server_id']:
            logger.error("Pterodactyl server ID not configured (set PTERODACTYL_SERVER_ID env var or in config.json)")
            sys.exit(1)
        if not config['discord']['webhook_url']:
            logger.error("Discord webhook URL not configured (set DISCORD_WEBHOOK_URL env var or in config.json)")
            sys.exit(1)
        
        return config
    
    def _load_state(self) -> Dict:
        """Load state from JSON file"""
        state_file = Path(self.config.get('state_file', '/var/lib/windrose-monitor/state.json'))
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load state file: {e}")
                state = {}
        else:
            state = {}
        
        # Defaults
        state.setdefault('players', [])
        state.setdefault('player_count', 0)
        state.setdefault('last_update', None)
        state.setdefault('cpu_profile', 'balanced')
        state.setdefault('performance_counter', 0)
        state.setdefault('balanced_counter', 0)

        return state
    
    def _save_state(self):
        """Save state to JSON file"""
        state_file = Path(self.config.get('state_file', '/var/lib/windrose-monitor/state.json'))
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def _alert_ws_dead(self, reason: str):
        """Log when WebSocket dies or misbehaves (no Discord spam)."""
        msg = f"⚠️ **WebSocket Disconnected** — {reason}"
        logger.warning(msg)
        # Intentionally NOT sending to Discord to avoid spam
    
    def get_server_logs(self) -> Optional[str]:
        """Fetch server logs.

        Prefer the live WebSocket buffer; fall back to the HTTP logs endpoint if empty.
        """
        # If websocket is enabled, prefer websocket buffer and do not call legacy /logs endpoint.
        if websocket is not None:
            with self._ws_lock:
                if len(self._ws_buffer) > 0:
                    return "\n".join(list(self._ws_buffer))

            # If buffer empty, attempt to validate websocket token so we can show a helpful message
            token_data = self._get_websocket_token()
            if not token_data:
                logger.warning("WebSocket token unavailable — ensure PTERODACTYL_API_TOKEN is a Client API token with websocket.connect permission")
                return None

            logger.info("WebSocket token obtained; waiting for live console output to populate buffer")
            return None

        # Fallback: HTTP logs endpoint (legacy)
        try:
            url = f"{self.config['pterodactyl']['api_url']}/api/client/servers/{self.config['pterodactyl']['server_id']}/logs"
            response = self.api_session.get(url, timeout=10, headers={
                'Accept': 'Application/vnd.pterodactyl.v1+json'
            })
            response.raise_for_status()
            data = response.json()
            return data.get('attributes', {}).get('content', '')
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch logs from Pterodactyl API: {e}", exc_info=True)
            return None

    def _get_websocket_token(self) -> Optional[dict]:
        """Request a temporary websocket token and socket URL from the Panel."""
        try:
            if self._ws_token_data and self._ws_token_expiry and time.time() < (self._ws_token_expiry - 30):
                return self._ws_token_data

            url = f"{self.config['pterodactyl']['api_url']}/api/client/servers/{self.config['pterodactyl']['server_id']}/websocket"
            resp = self.api_session.get(url, timeout=10, headers={
                'Accept': 'Application/vnd.pterodactyl.v1+json'
            })
            resp.raise_for_status()
            data = resp.json().get('data')

            if data and isinstance(data, dict):
                logger.info(f"Obtained websocket token, socket URL: {data.get('socket')}")

            token = data.get('token') if data else None
            if token:
                try:
                    parts = token.split('.')
                    if len(parts) >= 2:
                        payload = parts[1]
                        padding = '=' * ((4 - len(payload) % 4) % 4)
                        decoded = base64.urlsafe_b64decode(payload + padding)
                        payload_json = json.loads(decoded)
                        exp = int(payload_json.get('exp', 0))
                        self._ws_token_expiry = exp
                        self._ws_token_data = data
                        logger.info(f"WebSocket token expires at {datetime.fromtimestamp(self._ws_token_expiry)}")
                except Exception:
                    self._ws_token_data = data
                    self._ws_token_expiry = 0

            return data

        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not obtain websocket token: {e}", exc_info=True)
            return None

    def _ws_listener(self):
        """Background thread: maintain websocket connection and buffer console output."""
        backoff = 1

        while not self._ws_stop.is_set():
            logger.info("Attempting WebSocket reconnect…")
            token_data = self._get_websocket_token()
            if not token_data:
                logger.info(f"Backoff now {backoff} seconds (no token)")
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue

            token = token_data.get('token')
            socket_url = token_data.get('socket')

            if not token or not socket_url:
                logger.info(f"Backoff now {backoff} seconds (missing token or socket URL)")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue

            # Use the WebSocket URL EXACTLY as returned by the API.
            logger.info(f"Connecting to WebSocket at {socket_url}")

            try:
                ws = websocket.create_connection(
                    socket_url,
                    timeout=15,
                    origin="https://panel.thedicecube.co.uk",
                    header=[f"Authorization: Bearer {token}"]
                )

                # Authenticate
                auth_msg = json.dumps({"event": "auth", "args": [token]})
                ws.send(auth_msg)
                logger.info("WebSocket connection established and auth message sent")

                backoff = 1
                last_msg = time.time()

                while not self._ws_stop.is_set():
                    try:
                        raw = ws.recv()
                        if not raw:
                            logger.warning("WebSocket recv returned empty payload — reconnecting")
                            break

                        last_msg = time.time()

                        try:
                            msg = json.loads(raw)
                        except Exception:
                            continue

                        event = msg.get('event')
                        args = msg.get('args', [])

                        if event == 'auth success':
                            logger.info("WebSocket auth success")
                            backoff = 1

                        elif event == 'jwt error':
                            logger.warning("WebSocket reported JWT error, refreshing token")
                            self._alert_ws_dead("JWT expired — refreshing token")
                            self._ws_token_data = None
                            self._ws_token_expiry = 0
                            break

                        elif event == 'console output' and args:
                            line = args[0]
                            with self._ws_lock:
                                self._ws_buffer.append(line)

                        # Stale socket detection
                        if time.time() - last_msg > 30:
                            logger.warning("WebSocket stale for 30s — reconnecting")
                            self._alert_ws_dead("No messages for 30 seconds (stale socket)")
                            break

                    except websocket.WebSocketConnectionClosedException:
                        logger.warning("WebSocket connection closed by remote")
                        break
                    except Exception as e:
                        logger.debug(f"WebSocket recv error: {e}", exc_info=True)
                        break

                try:
                    ws.close()
                    logger.info("WebSocket connection closed — cleaning up")
                except Exception:
                    pass

            except Exception as e:
                msg = str(e)
                logger.warning(f"WebSocket connection failed: {msg}")
                logger.error(f"WebSocket error: {msg}", exc_info=True)

                lower = msg.lower()
                if "ssl" in lower or "handshake" in lower:
                    self._alert_ws_dead("SSL handshake failure")
                    logger.warning("SSL handshake issue — retrying in 5 seconds")
                    time.sleep(5)
                    continue

                if '403' in msg or 'forbidden' in lower:
                    self._alert_ws_dead("403 Forbidden — check API token permissions")
                    logger.warning("WebSocket handshake forbidden — backing off 5 minutes")
                    time.sleep(300)
                    continue

                self._alert_ws_dead(f"Connection failed: {msg}")
                logger.info(f"Backoff now {backoff} seconds")
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
    
    def parse_player_list(self, logs: str) -> Set[str]:
        """Parse player list from logs
        
        Players are in BOTH Connected Accounts and Reserved Accounts sections.
        Disconnected Accounts are used to indicate players that have left and
        should not be counted if they are no longer in Connected/Reserved.
        
        Returns unique set of currently active players.
        """
        connected_players: Set[str] = set()
        reserved_players: Set[str] = set()
        disconnected_players: Set[str] = set()

        lines = logs.split('\n')
        current_section = None
        
        for line in lines:
            # Section detection
            if 'Connected Accounts' in line:
                current_section = 'connected'
                continue
            elif 'Reserved Accounts' in line:
                current_section = 'reserved'
                continue
            elif 'Disconnected Accounts' in line:
                current_section = 'disconnected'
                continue
            
            # Only parse lines inside known sections
            if current_section in ['connected', 'reserved', 'disconnected']:
                if "Name '" in line:
                    try:
                        start = line.find("Name '") + len("Name '")
                        end = line.find("'", start)
                        if start > len("Name '") - 1 and end > start:
                            player_name = line[start:end].strip()
                            if player_name:
                                if current_section == 'connected':
                                    connected_players.add(player_name)
                                elif current_section == 'reserved':
                                    reserved_players.add(player_name)
                                elif current_section == 'disconnected':
                                    disconnected_players.add(player_name)
                    except (ValueError, IndexError):
                        continue
        
        # Active players = Connected + Reserved
        active_players = connected_players | reserved_players

        # Disconnected list is historical; if someone appears ONLY in disconnected
        # and not in connected/reserved, they are already excluded by definition.
        # This logic ensures we never count purely disconnected players.
        return active_players
    
    def set_cpu_profile(self, profile: str) -> bool:
        """Set CPU performance profile
        
        Args:
            profile: 'performance' or 'balance_power'
        
        Returns:
            True if successful
        """
        if not self.config['cpu_profile']['enabled']:
            return True
        
        try:
            # Get all CPU cores
            cpu_path_template = self.config['cpu_profile']['cpu_freq_path'].replace('cpu0', 'cpu{}')
            
            # Find all available CPUs
            sys_cpu_path = '/sys/devices/system/cpu'
            cpu_count = 0
            for cpu_dir in Path(sys_cpu_path).glob('cpu[0-9]*'):
                cpu_num = cpu_dir.name.replace('cpu', '')
                try:
                    cpu_num = int(cpu_num)
                except ValueError:
                    continue
                cpu_count += 1
            
            # Write profile to each CPU
            success = True
            for i in range(cpu_count):
                cpu_freq_path = cpu_path_template.format(i)
                try:
                    # Use echo with sudo to write to the file
                    cmd = f"echo '{profile}' | sudo tee {cpu_freq_path} > /dev/null"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        logger.warning(f"Failed to set CPU {i} to {profile}: {result.stderr}")
                        success = False
                except Exception as e:
                    logger.warning(f"Error setting CPU {i} profile: {e}")
                    success = False
            
            if success:
                logger.info(f"CPU profile set to: {profile}")
                self.state['cpu_profile'] = profile
            return success
        except Exception as e:
            logger.error(f"Error changing CPU profile: {e}", exc_info=True)
            return False
    
    def send_discord_message(self, message: str) -> bool:
        """Send message to Discord webhook
        
        Args:
            message: Message to send
        
        Returns:
            True if successful
        """
        try:
            webhook_url = self.config['discord']['webhook_url']
            payload = {
                'content': message,
                'username': 'Windrose Server Monitor',
                'avatar_url': 'https://via.placeholder.com/32'
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Discord message: {e}", exc_info=True)
            return False
    
    def check_and_update(self):
        """Check for player changes and update state"""
        logger.info("Checking server status...")
        
        # Fetch logs
        logs = self.get_server_logs()
        if not logs:
            logger.warning("Could not fetch server logs")
            return
        
        # Parse current players
        current_players = self.parse_player_list(logs)
        previous_players = set(self.state.get('players', []))
        
        # Check for new players (log only, no Discord spam)
        new_players = current_players - previous_players
        if new_players:
            for player in new_players:
                msg = f"🎮 **Player Joined**: {player}"
                logger.info(msg)
                # No Discord message here to reduce spam
        
        # Check for disconnected players (log only, no Discord spam)
        left_players = previous_players - current_players
        if left_players:
            for player in left_players:
                msg = f"👋 **Player Left**: {player}"
                logger.info(msg)
                # No Discord message here to reduce spam
        
        # Update player count
        prev_count = self.state.get('player_count', 0)
        current_count = len(current_players)
        
        if current_count != prev_count:
            status_msg = f"📊 **Player Count**: {current_count} (was {prev_count})"
            logger.info(status_msg)
            # Only player count changes go to Discord
            self.send_discord_message(status_msg)
        
        # Update state
        self.state['players'] = list(current_players)
        self.state['player_count'] = current_count
        self.state['last_update'] = datetime.now().isoformat()
        
        # CPU profile hysteresis
        if current_count > 0:
            self.state['performance_counter'] = self.state.get('performance_counter', 0) + 1
            self.state['balanced_counter'] = 0

            if self.state['performance_counter'] >= 2 and self.state.get('cpu_profile') != 'performance':
                logger.info("Hysteresis: players present for 2 checks, switching to performance CPU profile")
                self.set_cpu_profile(self.config['cpu_profile']['performance_profile'])
        else:
            self.state['balanced_counter'] = self.state.get('balanced_counter', 0) + 1
            self.state['performance_counter'] = 0

            if self.state['balanced_counter'] >= 3 and self.state.get('cpu_profile') != 'balanced':
                logger.info("Hysteresis: no players for 3 checks, switching to balanced CPU profile")
                self.set_cpu_profile(self.config['cpu_profile']['balanced_profile'])
        
        # Save state
        self._save_state()
    
    def run(self):
        """Main monitoring loop"""
        logger.info("Starting Windrose Server Monitor")
        
        try:
            while True:
                try:
                    self.check_and_update()
                except Exception as e:
                    logger.error(f"Error during check: {e}", exc_info=True)
                
                time.sleep(self.config['monitoring']['check_interval_seconds'])
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


def main():
    monitor = WindroseMonitor()
    monitor.run()


if __name__ == '__main__':
    main()
