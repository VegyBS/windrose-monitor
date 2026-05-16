#!/usr/bin/env python3
"""
Windrose Monitor - Debug/Test Script
Use this to test your configuration before running as a service
"""

import sys
import json
from pathlib import Path

def test_config(config_path: str):
    """Test if configuration file is valid"""
    print("Testing configuration file...")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print("  ✓ Config file is valid JSON")
        return config
    except FileNotFoundError:
        print(f"  ✗ Config file not found: {config_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"  ✗ Invalid JSON: {e}")
        return None

def test_pterodactyl_api(config: dict):
    """Test Pterodactyl API connectivity"""
    print("\nTesting Pterodactyl API...")
    
    try:
        import requests
    except ImportError:
        print("  ✗ requests module not installed")
        print("    Run: pip3 install requests")
        return False
    
    try:
        api_url = config['pterodactyl']['api_url']
        api_token = config['pterodactyl']['api_token']
        server_id = config['pterodactyl']['server_id']
        
        if not api_token or api_token == "YOUR_API_TOKEN_HERE":
            print("  ✗ API token not configured")
            return False
        
        headers = {'Authorization': f"Bearer {api_token}"}
        url = f"{api_url}/api/client/servers/{server_id}/logs"
        
        print(f"  Testing connection to: {api_url}")
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            print("  ✓ Pterodactyl API connection successful")
            data = response.json()
            logs = data.get('attributes', {}).get('content', '')
            print(f"  ✓ Retrieved {len(logs)} characters of logs")
            return True
        elif response.status_code == 401:
            print("  ✗ Authentication failed - check API token")
            return False
        elif response.status_code == 404:
            print("  ✗ Server not found - check server ID")
            return False
        else:
            print(f"  ✗ API error: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_discord_webhook(config: dict):
    """Test Discord webhook connectivity"""
    print("\nTesting Discord Webhook...")
    
    try:
        import requests
    except ImportError:
        print("  ✗ requests module not installed")
        return False
    
    try:
        webhook_url = config['discord']['webhook_url']
        
        if not webhook_url or webhook_url == "YOUR_WEBHOOK_URL":
            print("  ✗ Webhook URL not configured")
            return False
        
        payload = {
            'content': '🧪 Test message from Windrose Monitor setup',
            'username': 'Windrose Monitor'
        }
        
        print(f"  Sending test message...")
        response = requests.post(webhook_url, json=payload, timeout=5)
        
        if response.status_code == 204:
            print("  ✓ Discord webhook working")
            return True
        elif response.status_code == 404:
            print("  ✗ Webhook not found - check URL")
            return False
        else:
            print(f"  ✗ Webhook error: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_cpu_frequency_scaling():
    """Test CPU frequency scaling capability"""
    print("\nTesting CPU Frequency Scaling...")
    
    try:
        cpu_path = '/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference'
        
        with open(cpu_path, 'r') as f:
            current = f.read().strip()
        print(f"  ✓ CPU frequency scaling available")
        print(f"  Current profile: {current}")
        return True
    except FileNotFoundError:
        print("  ✗ CPU frequency scaling not available")
        print("    Your CPU might not support energy_performance_preference")
        print("    You can disable this in config.json")
        return False
    except PermissionError:
        print("  ⚠ CPU frequency scaling needs root access")
        print("    This will work when run via systemd service")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_state_file_permissions():
    """Test state file directory permissions"""
    print("\nTesting State File Permissions...")
    
    try:
        state_dir = Path('/var/lib/windrose-monitor')
        
        if not state_dir.exists():
            print(f"  ✗ State directory doesn't exist: {state_dir}")
            print(f"    Run: sudo mkdir -p {state_dir}")
            print(f"    Run: sudo chown windrose-monitor:windrose-monitor {state_dir}")
            return False
        
        test_file = state_dir / '.write_test'
        try:
            test_file.write_text('test')
            test_file.unlink()
            print(f"  ✓ State directory is writable")
            return True
        except PermissionError:
            print(f"  ✗ State directory is not writable")
            print(f"    Run: sudo chown windrose-monitor:windrose-monitor {state_dir}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("  Windrose Monitor - Configuration Test")
    print("=" * 60 + "\n")
    
    # Try different config paths
    config_paths = [
        '/etc/windrose-monitor/config.json',
        './config.json',
        Path(__file__).parent / 'config.json'
    ]
    
    config = None
    for path in config_paths:
        if Path(path).exists():
            config = test_config(str(path))
            if config:
                break
    
    if not config:
        print("\n✗ Could not find configuration file")
        print("  Try running from the installation directory")
        sys.exit(1)
    
    # Run tests
    tests = [
        ("Pterodactyl API", lambda: test_pterodactyl_api(config)),
        ("Discord Webhook", lambda: test_discord_webhook(config)),
        ("CPU Frequency Scaling", test_cpu_frequency_scaling),
        ("State File Permissions", test_state_file_permissions),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("  Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n  Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ Configuration is ready!")
        print("\n  Next steps:")
        print("  1. Review /etc/windrose-monitor/config.json")
        print("  2. Run: sudo systemctl start windrose-monitor")
        print("  3. Monitor: sudo journalctl -u windrose-monitor -f")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed - fix issues before deploying")
        print("\n  See error messages above for details")
        sys.exit(1)

if __name__ == '__main__':
    main()
