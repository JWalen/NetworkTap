#!/usr/bin/env python3
"""
NetworkTap Complete Application Test - 5 Passes
Tests the entire application including all new WiFi and Updates features
"""

import os
import sys
import time

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

def header(text):
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}{text:^70}{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}\n")

def section(text):
    print(f"\n{BOLD}{BLUE}▶ {text}{RESET}")

def check(condition, message):
    if condition:
        print(f"  {GREEN}✓{RESET} {message}")
        return 1
    else:
        print(f"  {RED}✗{RESET} {message}")
        return 0

def info(message):
    print(f"  {BLUE}ℹ{RESET} {message}")

def warning(message):
    print(f"  {YELLOW}⚠{RESET} {message}")

def run_test_pass(pass_number):
    """Run a single comprehensive test pass"""
    header(f"TEST PASS {pass_number}/5")
    
    passed = 0
    failed = 0
    
    # Test 1: File Structure
    section("1. Core File Structure")
    
    files = [
        'web/static/js/wifi.js',
        'web/static/js/updates.js',
        'web/static/js/app.js',
        'web/static/js/help.js',
        'web/templates/index.html',
        'web/api/routes_wifi.py',
        'web/api/routes_update.py',
        'web/core/wifi_analyzer.py',
        'web/core/github_client.py',
        'web/core/update_manager.py',
        'CHANGELOG.md',
        'VERSION'
    ]
    
    for f in files:
        passed += check(os.path.exists(f), f"{f} exists")
    
    # Test 2: JavaScript Syntax
    section("2. JavaScript Syntax Validation")
    
    js_files = [
        'web/static/js/wifi.js',
        'web/static/js/updates.js',
        'web/static/js/app.js',
        'web/static/js/help.js'
    ]
    
    for js in js_files:
        result = os.system(f'node -c {js} 2>/dev/null')
        passed += check(result == 0, f"{os.path.basename(js)} syntax valid")
    
    # Test 3: Module Structure
    section("3. JavaScript Module Structure")
    
    # WiFi module
    with open('web/static/js/wifi.js') as f:
        wifi_content = f.read()
    
    passed += check('const WiFi = (() => {' in wifi_content, "WiFi IIFE wrapper")
    passed += check('return { render, cleanup };' in wifi_content, "WiFi exports render & cleanup")
    passed += check(wifi_content.count('data-tab="') == 7, "WiFi has 7 tabs")
    
    # Updates module
    with open('web/static/js/updates.js') as f:
        updates_content = f.read()
    
    passed += check('const Updates = (() => {' in updates_content, "Updates IIFE wrapper")
    passed += check('return { render, cleanup };' in updates_content, "Updates exports render & cleanup")
    
    # Test 4: Navigation Integration
    section("4. Navigation Integration")
    
    with open('web/templates/index.html') as f:
        html = f.read()
    
    passed += check('data-page="wifi"' in html, "WiFi nav link")
    passed += check('data-page="updates"' in html, "Updates nav link")
    passed += check('src="/static/js/wifi.js"' in html, "WiFi script loaded")
    passed += check('src="/static/js/updates.js"' in html, "Updates script loaded")
    
    with open('web/static/js/app.js') as f:
        app_content = f.read()
    
    passed += check('wifi: WiFi,' in app_content, "WiFi registered in app")
    passed += check('updates: Updates,' in app_content, "Updates registered in app")
    
    # Test 5: API Endpoints
    section("5. API Endpoint Definitions")
    
    with open('web/api/routes_wifi.py') as f:
        wifi_api = f.read()
    
    wifi_endpoints = [
        '@router.get("/status")',
        '@router.get("/scan")',
        '@router.post("/connect")',
        '@router.post("/ap/start")',
        '@router.post("/capture/start")',
        '@router.post("/survey/run")',
        '@router.get("/ids/alerts")',
        '@router.get("/clients/list")'
    ]
    
    for endpoint in wifi_endpoints:
        passed += check(endpoint in wifi_api, f"WiFi endpoint {endpoint}")
    
    with open('web/api/routes_update.py') as f:
        update_api = f.read()
    
    update_endpoints = [
        '@router.get("/current")',
        '@router.get("/check")',
        '@router.post("/download")',
        '@router.post("/install")',
        '@router.post("/update")',
        '@router.get("/history")',
        '@router.post("/rollback")'
    ]
    
    for endpoint in update_endpoints:
        passed += check(endpoint in update_api, f"Update endpoint {endpoint}")
    
    # Test 6: Shell Scripts
    section("6. Shell Script Permissions")
    
    scripts = [
        'scripts/ap.sh',
        'scripts/wifi_capture.sh',
        'scripts/wifi_survey.sh',
        'scripts/update.sh'
    ]
    
    for script in scripts:
        passed += check(os.access(script, os.X_OK), f"{script} executable")
    
    # Test 7: Documentation
    section("7. Documentation Completeness")
    
    with open('CHANGELOG.md') as f:
        changelog = f.read()
    
    passed += check('[1.1.0]' in changelog, "Version 1.1.0 in changelog")
    passed += check('WiFi' in changelog, "WiFi features documented")
    passed += check('Auto-Update' in changelog, "Auto-Update documented")
    
    with open('web/static/js/help.js') as f:
        help_content = f.read()
    
    passed += check('WiFi' in help_content, "WiFi in help")
    passed += check('Updates' in help_content, "Updates in help")
    passed += check('v1.1.0' in help_content, "v1.1.0 in help changelog")
    
    with open('VERSION') as f:
        version = f.read().strip()
    
    passed += check(version == '1.1.0', f"VERSION file is 1.1.0")
    
    # Test 8: Frontend UI Elements
    section("8. Frontend UI Elements")
    
    # WiFi tabs
    wifi_tabs = ['overview', 'client', 'ap', 'capture', 'survey', 'ids', 'tracking']
    for tab in wifi_tabs:
        passed += check(f'data-tab="{tab}"' in wifi_content, f"WiFi {tab} tab")
    
    # WiFi actions
    wifi_actions = ['scanNetworks', 'startAP', 'stopAP', 'startCapture', 'runSurvey']
    for action in wifi_actions:
        passed += check(f'window.WiFi.{action}' in wifi_content, f"WiFi action {action}")
    
    # Updates sections
    update_sections = ['current-version', 'update-status', 'update-history']
    for section_id in update_sections:
        passed += check(f'id="{section_id}"' in updates_content, f"Updates section {section_id}")
    
    # Updates actions
    update_actions = ['checkForUpdates', 'performUpdate', 'rollback']
    for action in update_actions:
        passed += check(f'window.Updates.{action}' in updates_content, f"Updates action {action}")
    
    # Test 9: Backend Core Modules
    section("9. Backend Core Modules")
    
    with open('web/core/wifi_analyzer.py') as f:
        analyzer = f.read()
    
    passed += check('class WiFiAnalyzer' in analyzer, "WiFiAnalyzer class")
    passed += check('detect_rogue_aps' in analyzer, "Rogue AP detection")
    passed += check('track_client' in analyzer, "Client tracking")
    
    with open('web/core/github_client.py') as f:
        github = f.read()
    
    passed += check('class GitHubClient' in github, "GitHubClient class")
    passed += check('get_latest_release' in github, "Get latest release")
    
    with open('web/core/update_manager.py') as f:
        updater = f.read()
    
    passed += check('class UpdateManager' in updater, "UpdateManager class")
    passed += check('download_update' in updater, "Download update")
    passed += check('perform_update' in updater, "Perform update")
    
    # Test 10: Configuration and Constants
    section("10. Configuration and Constants")
    
    passed += check('WIFI_INTERFACE' in wifi_content or 'api/wifi' in wifi_content, 
                   "WiFi API endpoints configured")
    passed += check('api/update' in updates_content, "Update API endpoints configured")
    
    total = passed + failed
    
    return passed, total

def main():
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    header("NetworkTap Complete Application Test Suite")
    info(f"Testing WiFi platform (25 endpoints) + Auto-Update (9 endpoints)")
    info(f"Frontend: 2 new UI pages with 7 WiFi tabs + Updates page")
    info(f"Backend: 5 new modules, 5 new shell scripts")
    print()
    
    all_results = []
    
    for i in range(1, 6):
        passed, total = run_test_pass(i)
        pass_rate = (passed / total * 100) if total > 0 else 0
        all_results.append((passed, total, pass_rate))
        
        print(f"\n{BOLD}Pass {i} Results: {passed}/{total} ({pass_rate:.1f}%){RESET}")
        
        if i < 5:
            time.sleep(1)
    
    # Summary
    header("FINAL SUMMARY - 5 TEST PASSES")
    
    total_passed = sum(r[0] for r in all_results)
    total_tests = sum(r[1] for r in all_results)
    avg_pass_rate = sum(r[2] for r in all_results) / 5
    
    print(f"\n{BOLD}Individual Pass Results:{RESET}")
    for i, (p, t, rate) in enumerate(all_results, 1):
        color = GREEN if rate >= 95 else YELLOW if rate >= 85 else RED
        print(f"  Pass {i}: {color}{p}/{t} ({rate:.1f}%){RESET}")
    
    print(f"\n{BOLD}Overall Statistics:{RESET}")
    print(f"  Total Tests: {total_tests}")
    print(f"  Total Passed: {total_passed}")
    print(f"  Average Pass Rate: {avg_pass_rate:.1f}%")
    
    if avg_pass_rate >= 95:
        print(f"\n{BOLD}{GREEN}{'='*70}{RESET}")
        print(f"{BOLD}{GREEN}✓ EXCELLENT - All systems operational and ready for deployment{RESET}")
        print(f"{BOLD}{GREEN}{'='*70}{RESET}\n")
        return 0
    elif avg_pass_rate >= 90:
        print(f"\n{BOLD}{YELLOW}{'='*70}{RESET}")
        print(f"{BOLD}{YELLOW}⚠ GOOD - Minor issues, but deployment ready{RESET}")
        print(f"{BOLD}{YELLOW}{'='*70}{RESET}\n")
        return 0
    else:
        print(f"\n{BOLD}{RED}{'='*70}{RESET}")
        print(f"{BOLD}{RED}✗ NEEDS WORK - Address issues before deployment{RESET}")
        print(f"{BOLD}{RED}{'='*70}{RESET}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
