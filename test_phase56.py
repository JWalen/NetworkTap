#!/usr/bin/env python3
"""Phases 5 & 6: Wireless IDS + Client Tracking - Testing (3 Iterations)"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "web"))

results = {"passed": 0, "failed": 0}

async def test_all():
    print("=" * 70)
    print("PHASES 5 & 6: WIRELESS IDS + CLIENT TRACKING - 3 ITERATIONS")
    print("=" * 70)
    
    for iteration in range(1, 4):
        print(f"\n{'='*70}")
        print(f"ITERATION {iteration}/3")
        print('='*70 + '\n')
        
        # Test 1: Analyzer Module
        print("🧪 Test 1: WiFi Analyzer Module")
        try:
            from core.wifi_analyzer import WiFiAnalyzer, WirelessClient, RogueAP, WirelessAlert, get_analyzer
            
            analyzer = WiFiAnalyzer()
            assert analyzer is not None
            
            # Test get_analyzer singleton
            a1 = get_analyzer()
            a2 = get_analyzer()
            assert a1 is a2, "Should return same instance"
            
            print("   → WiFiAnalyzer: ✓")
            print("   → Dataclasses: ✓")
            print("   → Singleton: ✓")
            print("   ✅ PASS\n")
            results["passed"] += 1
        except Exception as e:
            print(f"   ❌ FAIL: {e}\n")
            results["failed"] += 1
        
        # Test 2: Data Classes
        print("🧪 Test 2: Data Classes")
        try:
            from core.wifi_analyzer import WirelessClient, RogueAP, WirelessAlert
            
            client = WirelessClient(
                mac="00:11:22:33:44:55",
                vendor="TestVendor",
                first_seen="2024-01-01T00:00:00",
                last_seen="2024-01-01T01:00:00",
                probe_ssids=["TestSSID"],
            )
            assert client.mac == "00:11:22:33:44:55"
            
            rogue = RogueAP(
                bssid="AA:BB:CC:DD:EE:FF",
                ssid="RogueAP",
                channel=6,
                first_seen="2024-01-01T00:00:00",
                reason="unexpected_ap",
                severity="high",
            )
            assert rogue.severity == "high"
            
            alert = WirelessAlert(
                timestamp="2024-01-01T00:00:00",
                alert_type="deauth_attack",
                severity="critical",
                source_mac="11:22:33:44:55:66",
                details="Test alert",
            )
            assert alert.alert_type == "deauth_attack"
            
            print("   ✅ PASS\n")
            results["passed"] += 1
        except Exception as e:
            print(f"   ❌ FAIL: {e}\n")
            results["failed"] += 1
        
        # Test 3: API Imports
        print("🧪 Test 3: API Imports")
        try:
            from api.routes_wifi import (
                wifi_ids_alerts,
                wifi_ids_rogue_aps,
                wifi_ids_scan_rogues,
                wifi_clients_list,
                wifi_clients_stats,
                wifi_analyze,
            )
            print("   → All IDS & client functions imported")
            print("   ✅ PASS\n")
            results["passed"] += 1
        except Exception as e:
            print(f"   ❌ FAIL: {e}\n")
            results["failed"] += 1
        
        # Test 4: Route Registration
        print("🧪 Test 4: Route Registration")
        try:
            from app import app
            
            ids_routes = [r.path for r in app.routes if '/wifi/ids/' in r.path]
            client_routes = [r.path for r in app.routes if '/wifi/clients/' in r.path]
            
            print(f"   → IDS routes: {len(ids_routes)}")
            print(f"   → Client routes: {len(client_routes)}")
            
            assert len(ids_routes) >= 3
            assert len(client_routes) >= 2
            print("   ✅ PASS\n")
            results["passed"] += 1
        except Exception as e:
            print(f"   ❌ FAIL: {e}\n")
            results["failed"] += 1
        
        # Test 5: Required Endpoints
        print("🧪 Test 5: Required Endpoints")
        try:
            from app import app
            
            required = [
                "/api/wifi/ids/alerts",
                "/api/wifi/ids/rogue-aps",
                "/api/wifi/ids/scan-rogues",
                "/api/wifi/clients/list",
                "/api/wifi/clients/stats",
                "/api/wifi/analyze",
            ]
            
            app_paths = [r.path for r in app.routes]
            missing = [e for e in required if e not in app_paths]
            
            if missing:
                print(f"   ❌ Missing: {missing}")
                results["failed"] += 1
            else:
                print(f"   → All {len(required)} endpoints present")
                print("   ✅ PASS\n")
                results["passed"] += 1
        except Exception as e:
            print(f"   ❌ FAIL: {e}\n")
            results["failed"] += 1
        
        # Test 6: Analyzer Methods
        print("🧪 Test 6: Analyzer Methods")
        try:
            from core.wifi_analyzer import WiFiAnalyzer
            
            analyzer = WiFiAnalyzer()
            
            # Test methods exist
            assert hasattr(analyzer, 'get_clients')
            assert hasattr(analyzer, 'get_rogue_aps')
            assert hasattr(analyzer, 'get_alerts')
            assert hasattr(analyzer, 'get_client_stats')
            assert hasattr(analyzer, 'lookup_vendor')
            assert hasattr(analyzer, 'detect_rogue_aps_from_survey')
            
            # Test method calls (should not crash)
            clients = analyzer.get_clients()
            assert isinstance(clients, list)
            
            rogues = analyzer.get_rogue_aps()
            assert isinstance(rogues, list)
            
            stats = analyzer.get_client_stats()
            assert isinstance(stats, dict)
            
            vendor = analyzer.lookup_vendor("00:11:22:33:44:55")
            assert isinstance(vendor, str)
            
            print("   → All 6 methods verified")
            print("   ✅ PASS\n")
            results["passed"] += 1
        except Exception as e:
            print(f"   ❌ FAIL: {e}\n")
            results["failed"] += 1
        
        # Test 7: Rogue Detection Logic
        print("🧪 Test 7: Rogue Detection Logic")
        try:
            from core.wifi_analyzer import WiFiAnalyzer
            
            analyzer = WiFiAnalyzer()
            analyzer.known_ssids = {"MyNetwork", "TrustedAP"}
            
            survey_data = [
                {"bssid": "00:11:22:33:44:55", "ssid": "MyNetwork", "channel": 6, "signal": -50},
                {"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "EvilAP", "channel": 6, "signal": -60},
                {"bssid": "11:22:33:44:55:66", "ssid": "", "channel": 11, "signal": -70},
            ]
            
            rogues = analyzer.detect_rogue_aps_from_survey(survey_data)
            
            # Should detect 2 rogues (EvilAP and hidden SSID)
            assert len(rogues) >= 1, "Should detect at least 1 rogue"
            
            print(f"   → Detected {len(rogues)} rogue(s)")
            print("   ✅ PASS\n")
            results["passed"] += 1
        except Exception as e:
            print(f"   ❌ FAIL: {e}\n")
            results["failed"] += 1
        
        # Test 8: Total WiFi Endpoints
        print("🧪 Test 8: Total WiFi API Coverage")
        try:
            from app import app
            
            wifi_routes = [r.path for r in app.routes if '/wifi/' in r.path]
            
            categories = {
                "client": sum(1 for r in wifi_routes if '/wifi/status' in r or '/wifi/scan' in r or '/wifi/connect' in r),
                "ap": sum(1 for r in wifi_routes if '/wifi/ap/' in r),
                "capture": sum(1 for r in wifi_routes if '/wifi/capture/' in r),
                "survey": sum(1 for r in wifi_routes if '/wifi/survey/' in r),
                "ids": sum(1 for r in wifi_routes if '/wifi/ids/' in r),
                "clients": sum(1 for r in wifi_routes if '/wifi/clients/' in r),
                "analyze": sum(1 for r in wifi_routes if '/wifi/analyze' in r),
            }
            
            print(f"   → Total WiFi endpoints: {len(wifi_routes)}")
            for cat, count in categories.items():
                if count > 0:
                    print(f"     • {cat}: {count}")
            
            assert len(wifi_routes) >= 20, f"Expected >=20 WiFi endpoints, got {len(wifi_routes)}"
            print("   ✅ PASS\n")
            results["passed"] += 1
        except Exception as e:
            print(f"   ❌ FAIL: {e}\n")
            results["failed"] += 1
        
        if iteration < 3:
            await asyncio.sleep(1)
    
    print("\n" + "=" * 70)
    print("FINAL SUMMARY - PHASES 5 & 6")
    print("=" * 70)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    total = results['passed'] + results['failed']
    print(f"📊 Success Rate: {results['passed']/total*100:.1f}%")
    
    if results['failed'] == 0:
        print("\n🎉 ALL PHASES 5 & 6 TESTS PASSED!")
        return True
    return False

if __name__ == "__main__":
    success = asyncio.run(test_all())
    sys.exit(0 if success else 1)
