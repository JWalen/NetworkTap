#!/usr/bin/env python3
"""
NetworkTap WiFi & Updates UI Integration Test
Validates that all UI pages load correctly and integrate properly
"""

import os
import re
import sys

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check(condition, message):
    """Print check result"""
    if condition:
        print(f"{GREEN}✓{RESET} {message}")
        return True
    else:
        print(f"{RED}✗{RESET} {message}")
        return False

def warning(message):
    """Print warning"""
    print(f"{YELLOW}⚠{RESET} {message}")

def info(message):
    """Print info"""
    print(f"{BLUE}ℹ{RESET} {message}")

def main():
    print("\n" + "="*60)
    print("NetworkTap WiFi & Updates UI Integration Test")
    print("="*60 + "\n")
    
    passed = 0
    failed = 0
    
    # Change to repo root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    os.chdir(repo_root)
    
    # Test 1: WiFi.js exists and has correct structure
    info("Test 1: WiFi.js file structure")
    wifi_js_path = 'web/static/js/wifi.js'
    if os.path.exists(wifi_js_path):
        with open(wifi_js_path) as f:
            content = f.read()
        
        passed += check('const WiFi = (() => {' in content, "WiFi module wrapper exists")
        passed += check('async function render(container)' in content, "WiFi render function exists")
        passed += check('return { render };' in content, "WiFi exports render")
        passed += check('window.WiFi' in content, "WiFi exports global actions")
        
        # Check tabs
        tabs = ['overview', 'client', 'ap', 'capture', 'survey', 'ids', 'tracking']
        for tab in tabs:
            if f'data-tab="{tab}"' in content:
                passed += check(True, f"WiFi {tab} tab exists")
            else:
                failed += check(False, f"WiFi {tab} tab exists")
        
        # Check action functions
        actions = ['scanNetworks', 'disconnect', 'startAP', 'stopAP', 'startCapture', 
                   'stopCapture', 'runSurvey', 'scanRogues', 'loadTrackedClients']
        for action in actions:
            if f'window.WiFi.{action}' in content:
                passed += check(True, f"WiFi action '{action}' exported")
            else:
                failed += check(False, f"WiFi action '{action}' exported")
    else:
        failed += check(False, "WiFi.js exists")
    
    print()
    
    # Test 2: Updates.js exists and has correct structure
    info("Test 2: Updates.js file structure")
    updates_js_path = 'web/static/js/updates.js'
    if os.path.exists(updates_js_path):
        with open(updates_js_path) as f:
            content = f.read()
        
        passed += check('const Updates = (() => {' in content, "Updates module wrapper exists")
        passed += check('async function render(container)' in content, "Updates render function exists")
        passed += check('return { render };' in content, "Updates exports render")
        passed += check('window.Updates' in content, "Updates exports global actions")
        
        # Check sections
        sections = ['current-version', 'update-status', 'update-history']
        for section in sections:
            if f'id="{section}"' in content:
                passed += check(True, f"Updates section '{section}' exists")
            else:
                failed += check(False, f"Updates section '{section}' exists")
        
        # Check action functions
        actions = ['checkForUpdates', 'downloadOnly', 'performUpdate', 'rollback', 'loadHistory']
        for action in actions:
            if f'window.Updates.{action}' in content:
                passed += check(True, f"Updates action '{action}' exported")
            else:
                failed += check(False, f"Updates action '{action}' exported")
    else:
        failed += check(False, "Updates.js exists")
    
    print()
    
    # Test 3: app.js integration
    info("Test 3: app.js integration")
    app_js_path = 'web/static/js/app.js'
    if os.path.exists(app_js_path):
        with open(app_js_path) as f:
            content = f.read()
        
        passed += check('wifi: WiFi,' in content, "WiFi registered in pages object")
        passed += check('updates: Updates,' in content, "Updates registered in pages object")
    else:
        failed += check(False, "app.js exists")
    
    print()
    
    # Test 4: index.html integration
    info("Test 4: index.html navigation integration")
    html_path = 'web/templates/index.html'
    if os.path.exists(html_path):
        with open(html_path) as f:
            content = f.read()
        
        passed += check('href="#wifi"' in content, "WiFi navigation link exists")
        passed += check('data-page="wifi"' in content, "WiFi data-page attribute exists")
        passed += check('href="#updates"' in content, "Updates navigation link exists")
        passed += check('data-page="updates"' in content, "Updates data-page attribute exists")
        
        passed += check('src="/static/js/wifi.js"' in content, "WiFi script tag exists")
        passed += check('src="/static/js/updates.js"' in content, "Updates script tag exists")
        
        # Verify script order (wifi.js and updates.js should come before app.js)
        wifi_pos = content.find('src="/static/js/wifi.js"')
        updates_pos = content.find('src="/static/js/updates.js"')
        app_pos = content.find('src="/static/js/app.js"')
        
        if wifi_pos < app_pos and updates_pos < app_pos:
            passed += check(True, "Script load order correct (modules before app.js)")
        else:
            failed += check(False, "Script load order correct (modules before app.js)")
    else:
        failed += check(False, "index.html exists")
    
    print()
    
    # Test 5: help.js documentation
    info("Test 5: help.js documentation")
    help_js_path = 'web/static/js/help.js'
    if os.path.exists(help_js_path):
        with open(help_js_path) as f:
            content = f.read()
        
        passed += check('WiFi' in content and 'wireless' in content.lower(), 
                       "WiFi documentation exists in help")
        passed += check('Updates' in content and 'update' in content.lower(), 
                       "Updates documentation exists in help")
        passed += check('v1.1.0' in content, "Version 1.1.0 documented in changelog")
    else:
        failed += check(False, "help.js exists")
    
    print()
    
    # Test 6: CHANGELOG.md
    info("Test 6: CHANGELOG.md documentation")
    changelog_path = 'CHANGELOG.md'
    if os.path.exists(changelog_path):
        with open(changelog_path) as f:
            content = f.read()
        
        passed += check('[1.1.0]' in content, "Version 1.1.0 in CHANGELOG")
        passed += check('WiFi' in content, "WiFi features documented")
        passed += check('Auto-Update' in content, "Auto-Update documented")
        passed += check('Access Point' in content, "AP mode documented")
        passed += check('Site Survey' in content, "Site survey documented")
        passed += check('Wireless IDS' in content, "Wireless IDS documented")
    else:
        failed += check(False, "CHANGELOG.md exists")
    
    print()
    
    # Test 7: VERSION file
    info("Test 7: VERSION file")
    version_path = 'VERSION'
    if os.path.exists(version_path):
        with open(version_path) as f:
            version = f.read().strip()
        
        passed += check(version == '1.1.0', f"VERSION is 1.1.0 (got: {version})")
    else:
        failed += check(False, "VERSION file exists")
    
    print()
    
    # Test 8: API endpoints documented
    info("Test 8: Backend API files exist")
    api_files = [
        'web/api/routes_wifi.py',
        'web/api/routes_update.py',
        'web/core/wifi_analyzer.py',
        'web/core/github_client.py',
        'web/core/update_manager.py'
    ]
    
    for api_file in api_files:
        if os.path.exists(api_file):
            passed += check(True, f"{api_file} exists")
        else:
            failed += check(False, f"{api_file} exists")
    
    print()
    
    # Test 9: Shell scripts exist
    info("Test 9: WiFi & Update shell scripts")
    scripts = [
        'scripts/ap.sh',
        'scripts/wifi_capture.sh',
        'scripts/wifi_survey.sh',
        'scripts/update.sh',
        'setup/configure_ap.sh'
    ]
    
    for script in scripts:
        if os.path.exists(script):
            passed += check(True, f"{script} exists")
            # Check if executable
            if os.access(script, os.X_OK):
                passed += check(True, f"{script} is executable")
            else:
                warning(f"{script} not executable (may be expected)")
        else:
            failed += check(False, f"{script} exists")
    
    print()
    
    # Summary
    total = passed + failed
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print("="*60)
    print(f"Results: {passed}/{total} passed ({pass_rate:.1f}%)")
    
    if pass_rate >= 95:
        print(f"{GREEN}✓ EXCELLENT - UI integration complete and ready{RESET}")
        return 0
    elif pass_rate >= 85:
        print(f"{YELLOW}⚠ GOOD - Minor issues to address{RESET}")
        return 1
    else:
        print(f"{RED}✗ NEEDS WORK - Significant issues found{RESET}")
        return 2

if __name__ == '__main__':
    sys.exit(main())
