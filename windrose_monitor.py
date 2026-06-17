#!/usr/bin/env python3
"""
Windrose Server Monitor with Enhanced Debugging
- Parser returns found_sections and uses AccountId as canonical id
- players_meta persisted in state
- Debug mode with log persistence and snapshots
- WebSocket health metrics
- Systemd notification support
"""

import json
import logging
import logging.handlers
import time
import requests
import os
import threading
import base64
import socket
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    import websocket
except ImportError:
    websocket = None
except Exception:
    websocket = None

# Basic logging setup
logger = logging.getLogger("windrose-monitor")
logger.setLevel(logging.DEBUG)

log_dir = Path(os.getenv("LOG_DIR", "/var/log/windrose-monitor"))
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "windrose-monitor.log"
log_format = "%(asctime)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

if not logger.handlers:
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    fh.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(fh)
    logger.addHandler(ch)

if websocket is None:
    logger.warning("websocket-client not installed; falling back to HTTP logs")


class WindroseMonitor:
    """ """

    def __init__(self, config_path: str = "/etc/windrose-monitor/config.json"):
        self.config = self._load_config(config_path)
        self.state = self._load_state()
        self.api_session = requests.Session()
        token = self.config["pterodactyl"]["api_token"]
        if token:
            self.api_session.headers.update({"Authorization": f"Bearer {token}"})
            self._ws_buffer = deque(maxlen=int(os.getenv("WS_BUFFER_LINES", "10000")))
            self._ws_lock = threading.Lock()
            self._ws_thread: Optional[threading.Thread] = None
            self._ws_stop = threading.Event()
            self._ws_token_data = None
            self._ws_token_expiry = 0
            self._ws_last_msg_time = 0
            self.debug = os.getenv("DEBUG_MONITOR", "false").lower() == "true"
            self._mock_mode = os.getenv("MOCK_API", "false").lower() == "true"
            # Setup debug logging for raw console output
            self._debug_enabled = (
                os.getenv("DEBUG_SAVE_LOGS", "false").lower() == "true"
            )
        if self._debug_enabled:
            debug_log_dir = Path(
                os.getenv("DEBUG_LOG_DIR", "/var/log/windrose-monitor/debug")
            )
            debug_log_dir.mkdir(parents=True, exist_ok=True)
            self._debug_log_file = debug_log_dir / "raw_console_output.log"
            self._debug_log_handler = logging.handlers.RotatingFileHandler(
                self._debug_log_file, maxBytes=50 * 1024 * 1024, backupCount=3
            )
            self._debug_log_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(message)s")
            )
            debug_logger = logging.getLogger("windrose-debug")
            debug_logger.setLevel(logging.DEBUG)
            debug_logger.addHandler(self._debug_log_handler)
            self._debug_logger = debug_logger
            logger.info(f"Debug logging enabled: {self._debug_log_file}")
        else:
            self._debug_logger = None
            # Setup snapshot directory
            self._snapshots_enabled = (
                os.getenv("DEBUG_SNAPSHOTS_ENABLED", "false").lower() == "true"
            )
        if self._snapshots_enabled:
            self._snapshot_dir = Path(
                os.getenv("DEBUG_SNAPSHOTS_DIR", "/var/log/windrose-monitor/snapshots")
            )
            self._snapshot_dir.mkdir(parents=True, exist_ok=True)
            self._snapshot_keep = int(os.getenv("DEBUG_SNAPSHOTS_KEEP", "20"))
            logger.info(f"Snapshot debugging enabled: {self._snapshot_dir}")

        if websocket is not None and not self._mock_mode:
            if self._ws_thread is None or not self._ws_thread.is_alive():
                logger.info("Starting WebSocket listener thread")
                self._ws_thread = threading.Thread(
                    target=self._ws_listener, daemon=True
                )
                self._ws_thread.start()
        else:
            if self._mock_mode:
                logger.info("Running in MOCK_API mode for testing")
            else:
                logger.warning(
                    "websocket-client not available; falling back to HTTP logs"
                )

            self._notify_systemd("STATUS=Initializing...")

    def _load_config(self, config_path: str) -> Dict:
        """
        Load configuration from environment with optional override from a JSON file.
        """
        cfg = {
            "pterodactyl": {
                "api_url": os.getenv("PTERODACTYL_API_URL", ""),
                "api_token": os.getenv("PTERODACTYL_API_TOKEN", ""),
                "server_id": os.getenv("PTERODACTYL_SERVER_ID", ""),
                "websocket_origin": os.getenv("PTERODACTYL_WEBSOCKET_ORIGIN", ""),
                "websocket_host": os.getenv("PTERODACTYL_WEBSOCKET_HOST", ""),
            },
            "discord": {"webhook_url": os.getenv("DISCORD_WEBHOOK_URL", "")},
            "monitoring": {
                "check_interval_seconds": int(os.getenv("CHECK_INTERVAL_SECONDS", "20"))
            },
            "state_file": os.getenv(
                "STATE_FILE", "/var/lib/windrose-monitor/state.json"
            ),
        }

        # If the API token is missing, allow reading a config file to fill values
        try:
            if not cfg["pterodactyl"]["api_token"] and Path(config_path).exists():
                with open(config_path, "r") as f:
                    file_cfg = json.load(f)
                    self._merge_dicts(cfg, file_cfg)
        except Exception:
            logger.warning("Failed to read config file; using environment variables")

        if not cfg["discord"].get("webhook_url"):
            logger.error("DISCORD_WEBHOOK_URL not configured")

        return cfg

    def _merge_dicts(self, base: dict, override: dict) -> dict:
        """
        Recursively merge override into base. Override values replace base values.
        """
        for key, override_val in override.items():
            if isinstance(override_val, dict) and isinstance(base.get(key), dict):
                self._merge_dicts(base[key], override_val)
            else:
                base[key] = override_val
        return base

    def _load_state(self) -> Dict:
        """ """
        state_file = Path(
            self.config.get("state_file", "/var/lib/windrose-monitor/state.json")
        )
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
            except Exception:
                logger.warning("State file invalid; starting fresh")
                state = {}
        else:
            state = {}
            state.setdefault("players", [])
            state.setdefault("players_meta", {})
            state.setdefault("player_count", 0)
            state.setdefault("last_update", None)
            state.setdefault("empty_snapshot_counter", 0)
            logger.debug(
                f"Loaded state from {state_file}: players={len(state.get('players', []))} last_update={state.get('last_update')}"
            )
            return state

    def _save_state(self):
        """ """
        state_file = Path(
            self.config.get("state_file", "/var/lib/windrose-monitor/state.json")
        )
        state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = state_file.with_suffix(".tmp")
        try:
            with open(tmp_file, "w") as f:
                json.dump(self.state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
                os.replace(tmp_file, state_file)
                logger.debug(f"State saved to {state_file}")
        except Exception as e:
            logger.error(f"Failed to save state atomically: {e}")
        finally:
            try:
                if tmp_file.exists():
                    os.remove(tmp_file)
            except Exception as cleanup_err:
                logger.debug(
                    f"Failed to remove temporary state file {tmp_file}: {cleanup_err}"
                )

    def _notify_systemd(self, message: str):
        """Send notification to systemd

        Args:
          message: str:

        Returns:

        """
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            notify_socket = os.getenv("NOTIFY_SOCKET")
            if notify_socket:
                sock.sendto(message.encode(), notify_socket)
                sock.close()
        except Exception:
            pass

    def _alert_ws_dead(self, reason: str):
        """

        Args:
          reason: str:

        Returns:

        """
        logger.warning(f"WebSocket issue: {reason}")

    def get_server_logs(self) -> Optional[str]:
        """ """
        if self._mock_mode:
            return """
                [2026-05-20 10:30:00] Server Status Update
                Connected Accounts
                1. Name 'TestPlayer'. AccountId 'TEST123'. State 'ReadyToPlay'. NetAddress '192.168.1.1'
                Reserved Accounts
                Disconnected Accounts
                """
        if websocket is not None:
            with self._ws_lock:
                if len(self._ws_buffer) > 0:
                    return "\n".join(list(self._ws_buffer))
                token_data = self._get_websocket_token()
                if not token_data:
                    logger.debug("WebSocket token unavailable")
                    return None
            return None

        try:
            url = f"{self.config['pterodactyl']['api_url']}/api/client/servers/{self.config['pterodactyl']['server_id']}/logs"
            resp = self.api_session.get(
                url,
                timeout=10,
                headers={"Accept": "Application/vnd.pterodactyl.v1+json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("attributes", {}).get("content", "")
        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
            return None

    def _get_websocket_token(self) -> Optional[dict]:
        """ """
        try:
            margin = int(os.getenv("WS_TOKEN_REFRESH_MARGIN", "60"))
            if (
                self._ws_token_data
                and self._ws_token_expiry
                and time.time() < (self._ws_token_expiry - margin)
            ):
                return self._ws_token_data
            url = f"{self.config['pterodactyl']['api_url']}/api/client/servers/{self.config['pterodactyl']['server_id']}/websocket"
            resp = self.api_session.get(
                url,
                timeout=10,
                headers={"Accept": "Application/vnd.pterodactyl.v1+json"},
            )
            resp.raise_for_status()
            data = resp.json().get("data")
            token = data.get("token") if data else None
            if token:
                try:
                    parts = token.split(".")
                    if len(parts) >= 2:
                        payload = parts[1]
                        padding = "=" * ((4 - len(payload) % 4) % 4)
                        decoded = base64.urlsafe_b64decode(payload + padding)
                        payload_json = json.loads(decoded)
                        exp = int(payload_json.get("exp", 0))
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
        """ """
        backoff = 1
        while not self._ws_stop.is_set():
            token_data = self._get_websocket_token()
            if not token_data:
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue
            token = token_data.get("token")
            socket_url = token_data.get("socket")
            if not token or not socket_url:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            try:
                logger.debug(f"Connecting to WebSocket at {socket_url}")
                ws = websocket.create_connection(
                    socket_url,
                    timeout=15,
                    origin=self.config["pterodactyl"].get("websocket_origin", ""),
                    header=[f"Authorization: Bearer {token}"],
                )
                auth_msg = json.dumps({"event": "auth", "args": [token]})
                ws.send(auth_msg)
                last_msg = time.time()
                self._ws_last_msg_time = last_msg
                backoff = 1
                last_health_log = time.time()
                while not self._ws_stop.is_set():
                    margin = int(os.getenv("WS_TOKEN_REFRESH_MARGIN", "60"))
                    if self._ws_token_expiry and time.time() > (
                        self._ws_token_expiry - margin
                    ):
                        logger.info(
                            "WebSocket token expiring soon; reconnecting to refresh token"
                        )
                        break
                try:
                    raw = ws.recv()
                except Exception as e:
                    logger.debug(f"WebSocket recv error: {e}")
                with self._ws_lock:
                    buffer_size = len(self._ws_buffer)
                    logger.info(
                        f"WebSocket disconnected after {time.time() - last_msg:.1f}s idle. Buffer size: {buffer_size}"
                    )
                    break
                if not raw:
                    break
                last_msg = time.time()
                self._ws_last_msg_time = last_msg
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                event = msg.get("event")
                args = msg.get("args", [])
                if event == "console output" and args:
                    line = args[0]
                    with self._ws_lock:
                        self._ws_buffer.append(line)
                    if self._debug_logger:
                        self._debug_logger.debug(f"WS: {line}")
                        # Periodic health logging
                        if time.time() - last_health_log >= 300:  # Every 5 minutes
                            with self._ws_lock:
                                buffer_usage = (
                                    len(self._ws_buffer) / self._ws_buffer.maxlen * 100
                                )
                                logger.info(
                                    f"WebSocket health: buffer {buffer_usage:.1f}% full, last message {time.time() - last_msg:.1f}s ago"
                                )
                                last_health_log = time.time()
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
        """Parse the latest snapshot from logs and return:
        - active_by_id: { account_id: { 'name': display_name, 'state': state } }
        - found_any_section: bool

        Args:
          logs: str:

        Returns:

        """
        if not logs:
            return {}, False
        last_idx = logs.rfind("Connected Accounts")
        if last_idx == -1:
            last_idx = logs.rfind("Reserved Accounts")
        if last_idx == -1:
            last_idx = logs.rfind("Disconnected Accounts")
        if last_idx == -1:
            logger.debug("No player list sections found in logs")
            return {}, False

        sublogs = logs[last_idx:]
        connected: Dict[str, Tuple[str, str]] = {}
        reserved: Dict[str, Tuple[str, str]] = {}
        disconnected: Dict[str, Tuple[str, str]] = {}
        current_section: Optional[str] = None
        found_any_section = False

        for line in sublogs.splitlines():
            if "Connected Accounts" in line:
                connected.clear()
                reserved.clear()
                disconnected.clear()
                current_section = "connected"
                found_any_section = True
                continue
            if "Reserved Accounts" in line:
                current_section = "reserved"
                found_any_section = True
                continue
            if "Disconnected Accounts" in line:
                current_section = "disconnected"
                found_any_section = True
                continue

            if current_section in ("connected", "reserved", "disconnected"):
                if "Name '" in line and "AccountId" in line:
                    try:
                        nstart = line.find("Name '") + len("Name '")
                        nend = line.find("'", nstart)
                        name = line[nstart:nend].strip()

                        astart = line.find("AccountId '") + len("AccountId '")
                        aend = line.find("'", astart)
                        account_id = line[astart:aend].strip()

                        state = None
                        s_marker = "State '"
                        sidx = line.find(s_marker)
                        if sidx != -1:
                            sstart = sidx + len(s_marker)
                            send = line.find("'", sstart)
                            state = line[sstart:send].strip()

                        if current_section == "connected":
                            connected[account_id] = (name, state)
                        elif current_section == "reserved":
                            reserved[account_id] = (name, state)
                        else:
                            disconnected[account_id] = (name, state)
                    except Exception:
                        logger.debug(
                            f"Failed to parse line in section {current_section}: {line}"
                        )
                continue

        active_by_id: Dict[str, Dict[str, str]] = {}
        for d in (connected, reserved):
            for aid, (name, state) in d.items():
                if state and state.lower() == "saidfarewell":
                    continue
                active_by_id[aid] = {"name": name, "state": state or ""}

                if self.debug:
                    logger.debug(
                        f"parse_player_list found_any_section={found_any_section} connected={list(connected.keys())} reserved={list(reserved.keys())} disconnected={list(disconnected.keys())}"
                    )

        return active_by_id, found_any_section

    def _save_snapshot(self, logs: str, current_map: Dict, found_sections: bool):
        """Save parsed player snapshot for debugging

        Args:
          logs: str:
          current_map: Dict:
          found_sections: bool:

        Returns:

        """
        if not self._snapshots_enabled or not logs:
            return
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            snapshot_file = self._snapshot_dir / f"snapshot_{timestamp}.json"
            snapshot_data = {
                "timestamp": timestamp,
                "found_sections": found_sections,
                "current_map": current_map,
                "player_count": len(current_map),
                "raw_logs_excerpt": logs[-2000:] if len(logs) > 2000 else logs,
            }
            with open(snapshot_file, "w") as f:
                json.dump(snapshot_data, f, indent=2)
                # Keep only last N snapshots
                snapshots = sorted(self._snapshot_dir.glob("snapshot_*.json"))
            for old_snap in snapshots[: -self._snapshot_keep]:
                old_snap.unlink()
                logger.debug(f"Saved snapshot: {snapshot_file}")
        except Exception as e:
            logger.warning(f"Failed to save debug snapshot: {e}")

    def send_discord_message(self, message: str) -> bool:
        """

        Args:
          message: str:

        Returns:

        """
        webhook = self.config["discord"].get("webhook_url")
        if not webhook:
            logger.debug(f"Discord webhook not configured; would send: {message}")
            return False
        try:
            payload = {"content": message, "username": "Windrose Server Monitor"}
            resp = requests.post(webhook, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return False

    def check_and_update(self):
        """ """
        logger.info("Checking server status")
        logs = self.get_server_logs()
        if not logs:
            logger.debug("No logs available this tick")
            return

        current_map, found_sections = self.parse_player_list(logs)
        # Save snapshot for debugging
        self._save_snapshot(logs, current_map, found_sections)
        if not found_sections:
            logger.info("No player-list snapshot found in logs; skipping tick")
            return

        prev_players = set(self.state.get("players", []))
        prev_meta = self.state.get("players_meta", {})
        curr_players = set(current_map.keys())

        # Tolerate transient empty snapshots
        if len(curr_players) == 0 and len(prev_players) > 0:
            cnt = self.state.get("empty_snapshot_counter", 0) + 1
            self.state["empty_snapshot_counter"] = cnt
            if cnt < 2:
                logger.warning(
                    f"Transient empty snapshot detected (count={cnt}); deferring leave notification"
                )
                self._save_state()
                return
            else:
                logger.warning(
                    "Empty snapshot persisted for 2 consecutive ticks; accepting as real"
                )
                self.state["empty_snapshot_counter"] = 0
        else:
            if self.state.get("empty_snapshot_counter"):
                self.state["empty_snapshot_counter"] = 0

                new_players = curr_players - prev_players
                left_players = prev_players - curr_players

                messages: List[str] = []
                for aid in sorted(new_players):
                    display = current_map[aid]["name"]
                    messages.append(f"🎮 **Player Joined**: {display}")

                for aid in sorted(left_players):
                    display = prev_meta.get(aid, {}).get("name", "Unknown")
                    messages.append(f"👋 **Player Left**: {display}")

                prev_count = self.state.get("player_count", 0)
                current_count = len(curr_players)
                if current_count != prev_count:
                    messages.append(
                        f"📊 **Player Count**: {current_count} (was {prev_count})"
                    )

        if self.debug:
            logger.debug(f"previous_players={sorted(prev_players)}")
            logger.debug(f"current_players={sorted(curr_players)}")
            logger.debug(
                f"new_players={sorted(new_players)} left_players={sorted(left_players)}"
            )

        for msg in messages:
            self.send_discord_message(msg)
            time.sleep(0.15)

            now = datetime.now(timezone.utc).isoformat()
            self.state["players"] = list(curr_players)
            for aid, info in current_map.items():
                self.state["players_meta"][aid] = {
                    "name": info["name"],
                    "state": info.get("state", ""),
                    "last_seen": now,
                }
            for aid in list(prev_meta.keys()):
                if aid not in curr_players:
                    self.state["players_meta"][aid].setdefault("last_left", now)

        self.state["player_count"] = current_count
        self.state["last_update"] = now

        self._save_state()

    def run(self):
        """ """
        logger.info("Starting monitor loop")
        self._notify_systemd("READY=1\nSTATUS=Monitor active, tracking players...")
        try:
            while True:
                try:
                    self.check_and_update()
                    # Update systemd status
                    status_msg = f"STATUS=Active | Players: {self.state.get('player_count', 0)}"
                    self._notify_systemd(status_msg)
                    self._notify_systemd("WATCHDOG=1")
                except Exception as e:
                    logger.error(f"Error in check_and_update: {e}", exc_info=True)
                    self._notify_systemd(f"STATUS=Error in last cycle: {str(e)[:50]}")
                    time.sleep(self.config["monitoring"]["check_interval_seconds"])
        except KeyboardInterrupt:
            logger.info("Stopping monitor")
            self._notify_systemd("STOPPING=1")
            self._ws_stop.set()


if __name__ == "__main__":
    monitor = WindroseMonitor()
    monitor.run()


