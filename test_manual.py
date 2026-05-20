#!/usr/bin/env python3
"""
Manual test script to trigger a single check cycle
Usage: sudo -u windrose-monitor python test_manual.py
"""
import sys
import os
from pathlib import Path

# Ensure we load the same config
os.environ.setdefault('STATE_FILE', '/var/lib/windrose-monitor/state.json')
os.environ.setdefault('LOG_FILE', '/var/log/windrose-monitor.log')

from windrose_monitor import WindroseMonitor


def main():
    print("=== Manual Windrose Monitor Test ===\n")
    monitor = WindroseMonitor()
    print("1. Fetching server logs...")
    logs = monitor.get_server_logs()
    if logs:
        print(f" ✓ Retrieved {len(logs)} characters of logs")
        print(f" Last 500 chars:\n{logs[-500:]}")
    else:
        print(" ✗ No logs available")
        print("\n2. Parsing player list...")
    if logs:
        current_map, found_sections = monitor.parse_player_list(logs)
        print(f" ✓ Found sections: {found_sections}")
        print(f" ✓ Current players: {len(current_map)}")
    for aid, info in current_map.items():
        print(f" - {info['name']} (ID: {aid}, State: {info.get('state', 'N/A')})")
        print("\n3. Current state:")
        print(f" Players tracked: {len(monitor.state.get('players', []))}")
        print(f" CPU profile: {monitor.state.get('cpu_profile')}")
        print(f" Last update: {monitor.state.get('last_update')}")
        print("\n4. Running single check cycle...")
    try:
        monitor.check_and_update()
        print(" ✓ Check completed successfully")
    except Exception as e:
        print(f" ✗ Check failed: {e}")
    import traceback
    traceback.print_exc()
    print("\n5. WebSocket status:")
    if monitor._ws_thread and monitor._ws_thread.is_alive():
        print(" ✓ WebSocket thread running")
        with monitor._ws_lock:
            print(f" Buffer size: {len(monitor._ws_buffer)}/{monitor._ws_buffer.maxlen}")
    else:
        print(" ✗ WebSocket thread not running")


if __name__ == '__main__':
    main()
