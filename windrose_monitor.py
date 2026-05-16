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
        self._ws_thread = None
        self._ws_stop = threading.Event()

        # Start websocket listener thread if websocket-client is available
        if websocket is not None:
            logger.info("websocket-client available, starting WebSocket listener thread")
            self._ws_thread = threading.Thread(target=self._ws_listener, daemon=True)
            self._ws_thread.start()
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
                'server_id': os.getenv('PTERODACTYL_SERVER_ID', '')
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
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load state file: {e}")
        
        return {
            'players': [],
            'player_count': 0,
            'last_update': None,
            'cpu_profile': 'balanced'
        }
    
    def _save_state(self):
        """Save state to JSON file"""
        state_file = Path(self.config.get('state_file', '/var/lib/windrose-monitor/state.json'))
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
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
            logger.error(f"Failed to fetch logs from Pterodactyl API: {e}")
            return None

    def _get_websocket_token(self) -> Optional[dict]:
        """Request a temporary websocket token and socket URL from the Panel."""
        try:
            url = f"{self.config['pterodactyl']['api_url']}/api/client/servers/{self.config['pterodactyl']['server_id']}/websocket"
            resp = self.api_session.get(url, timeout=10, headers={
                'Accept': 'Application/vnd.pterodactyl.v1+json'
            })
            resp.raise_for_status()
            data = resp.json().get('data')
            if data and isinstance(data, dict):
                socket = data.get('socket')
                try:
                    host = urlparse(socket).netloc if socket else 'unknown'
                except Exception:
                    host = 'unknown'
                logger.info(f"Obtained websocket token, socket host: {host}")
            return data
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not obtain websocket token: {e}")
            return None

    def _ws_listener(self):
        """Background thread: maintain websocket connection and buffer console output."""
        backoff = 1
        while not self._ws_stop.is_set():
            token_data = self._get_websocket_token()
            if not token_data:
                # If token endpoint is rate-limiting, back off longer
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue

            token = token_data.get('token')
            socket_url = token_data.get('socket')
            if not token or not socket_url:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue

            headers = [f"Authorization: Bearer {token}", f"Origin: {self.config['pterodactyl']['api_url']}"]
            # Some Wings setups require the pterodactyl subprotocol during handshake
            headers.append('Sec-WebSocket-Protocol: pterodactyl')

            try:
                # Use websocket-client to connect
                try:
                    host = urlparse(socket_url).netloc
                except Exception:
                    host = socket_url
                logger.info(f"Connecting to WebSocket at {host} (requesting subprotocol 'pterodactyl')")
                # Request the 'pterodactyl' subprotocol explicitly; many Wings nodes expect it
                ws = websocket.create_connection(
                    socket_url,
                    timeout=15,
                    header=headers,
                    sslopt={"cert_reqs": ssl.CERT_REQUIRED},
                    subprotocols=['pterodactyl']
                )
                # Authenticate
                auth_msg = json.dumps({"event": "auth", "args": [token]})
                ws.send(auth_msg)
                logger.info("WebSocket connection established and auth message sent")

                backoff = 1
                while not self._ws_stop.is_set():
                    try:
                        raw = ws.recv()
                        if not raw:
                            break
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
                        elif event == 'jwt error':
                            logger.warning('WebSocket reported JWT error, refreshing token')
                            break
                    except websocket.WebSocketConnectionClosedException:
                        break
                    except Exception as e:
                        logger.debug(f"WebSocket recv error: {e}")
                        break

                try:
                    ws.close()
                except Exception:
                    pass
            except Exception as e:
                # If handshake returned 403, the panel denied the websocket connection.
                msg = str(e)
                logger.warning(f"WebSocket connection failed: {msg}")
                # If forbidden, likely permissions/token issue — back off longer to avoid repeated failures
                if '403' in msg or 'Forbidden' in msg:
                    logger.warning('WebSocket handshake forbidden: token may lack websocket.connect permission or Origin/subprotocol mismatch. Backing off 5 minutes.')
                    time.sleep(300)
                else:
                    time.sleep(backoff)
                backoff = min(backoff * 2, 300)
    
    def parse_player_list(self, logs: str) -> Set[str]:
        """Parse player list from logs
        
        Players are in BOTH Connected Accounts and Reserved Accounts sections.
        Disconnected Accounts is historical and should be ignored.
        
        Returns unique set of currently active players.
        """
        players = set()
        lines = logs.split('\n')
        
        current_section = None
        
        for i, line in enumerate(lines):
            # Check which section we're in
            if 'Connected Accounts' in line:
                current_section = 'connected'
                continue
            elif 'Reserved Accounts' in line:
                current_section = 'reserved'
                continue
            elif 'Disconnected Accounts' in line:
                # Stop processing - we don't care about historical disconnects
                break
            
            # Only parse Connected and Reserved sections
            if current_section in ['connected', 'reserved']:
                # Look for player name in format: "Name 'PlayerName'"
                if "Name '" in line:
                    try:
                        # Extract player name from "Name 'PlayerName'."
                        start = line.find("Name '") + len("Name '")
                        end = line.find("'", start)
                        if start > len("Name '") - 1 and end > start:
                            player_name = line[start:end].strip()
                            if player_name:  # Only add non-empty names
                                players.add(player_name)
                    except (ValueError, IndexError):
                        continue
        
        return players
    
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
            logger.error(f"Error changing CPU profile: {e}")
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
            logger.error(f"Failed to send Discord message: {e}")
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
        
        # Check for new players
        new_players = current_players - previous_players
        if new_players:
            for player in new_players:
                msg = f"🎮 **Player Joined**: {player}"
                logger.info(msg)
                self.send_discord_message(msg)
        
        # Check for disconnected players
        left_players = previous_players - current_players
        if left_players:
            for player in left_players:
                msg = f"👋 **Player Left**: {player}"
                logger.info(msg)
                self.send_discord_message(msg)
        
        # Update player count
        prev_count = self.state.get('player_count', 0)
        current_count = len(current_players)
        
        if current_count != prev_count:
            status_msg = f"📊 **Player Count**: {current_count} (was {prev_count})"
            logger.info(status_msg)
            self.send_discord_message(status_msg)
        
        # Update state
        self.state['players'] = list(current_players)
        self.state['player_count'] = current_count
        self.state['last_update'] = datetime.now().isoformat()
        
        # Manage CPU profile
        if current_count > 0 and self.state.get('cpu_profile') != 'performance':
            logger.info("Players detected, switching to performance CPU profile")
            self.set_cpu_profile(self.config['cpu_profile']['performance_profile'])
        elif current_count == 0 and self.state.get('cpu_profile') != 'balanced':
            logger.info("No players, switching to balanced CPU profile")
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