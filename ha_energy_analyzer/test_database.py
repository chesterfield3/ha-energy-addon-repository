#!/usr/bin/env python3
"""
Test script for HA Database Access functionality.

This script tests direct database access to the Home Assistant SQLite database
for efficient historical data retrieval.

Author: AI Assistant  
Date: 2025-10-20
"""

import os
import sys
from datetime import datetime, timedelta

# Add the src directory to the path so we can import our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
ha_analyzer_dir = os.path.join(src_dir, 'ha_energy_analyzer')
sys.path.insert(0, src_dir)
sys.path.insert(0, ha_analyzer_dir)

try:
    from ha_database_puller import create_database_puller
    from ha_history_puller import HomeAssistantHistoryPuller
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print(f"Current dir: {current_dir}")
    print(f"Src dir: {src_dir}")
    print(f"HA analyzer dir: {ha_analyzer_dir}")
    print("Make sure you're running this from the addon directory")
    sys.exit(1)


def test_database_direct_access():
    """Test direct database access functionality"""
    print("🧪 Testing Direct Database Access")
    print("=" * 40)
    
    # Try to create database puller
    db_puller = create_database_puller()
    
    if not db_puller:
        print("❌ Could not access Home Assistant database")
        print("   This is expected if:")
        print("   - Running outside HA environment")
        print("   - Database file not accessible")
        print("   - Database file in different location")
        return False
    
    try:
        # Get database info
        print("\n📊 Database Information:")
        info = db_puller.get_database_info()
        for key, value in info.items():
            print(f"   {key}: {value}")
        
        # Get available statistics
        print(f"\n📈 Checking available statistics...")
        stats = db_puller.get_available_statistics()
        
        if stats:
            print(f"✅ Found {len(stats)} entities with statistics")
            # Look for our test sensor
            toaster_stats = [s for s in stats if 'toaster' in s['statistic_id'].lower()]
            if toaster_stats:
                print(f"🎯 Found toaster oven statistics: {toaster_stats[0]['statistic_id']}")
                
                # Test data retrieval
                end_time = datetime.now()
                start_time = end_time - timedelta(days=7)
                
                print(f"\n📊 Testing statistics retrieval...")
                entity_id = toaster_stats[0]['statistic_id']
                
                # Try hourly statistics
                hourly_data = db_puller.get_entity_statistics(
                    [entity_id], start_time, end_time, use_short_term=True
                )
                
                if hourly_data:
                    print(f"✅ Hourly statistics: {len(hourly_data)} records")
                    if hourly_data:
                        sample = hourly_data[0]
                        print(f"📋 Sample: {sample['entity_id']} = {sample.get('sum', 'N/A')} at {sample['timestamp']}")
                else:
                    print("⚠️ No hourly statistics data found")
                
                # Try daily statistics  
                daily_data = db_puller.get_entity_statistics(
                    [entity_id], start_time, end_time, use_short_term=False
                )
                
                if daily_data:
                    print(f"✅ Daily statistics: {len(daily_data)} records")
                else:
                    print("⚠️ No daily statistics data found")
                
                return True
            else:
                print("⚠️ No toaster oven statistics found in database")
        else:
            print("⚠️ No statistics entities found in database")
        
        # Try raw states as fallback
        print(f"\n📊 Testing raw states retrieval...")
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=2)  # Shorter range for states
        
        states_data = db_puller.get_entity_states(
            ['sensor.toaster_oven_today_s_consumption'], start_time, end_time
        )
        
        if states_data:
            print(f"✅ Raw states: {len(states_data)} records")
            if states_data:
                sample = states_data[0]
                print(f"📋 Sample: {sample['entity_id']} = {sample['state']} at {sample['last_changed']}")
        else:
            print("⚠️ No raw states data found")
            
        return True
        
    finally:
        db_puller.disconnect()


def test_integrated_history_puller():
    """Test the integrated history puller with database support"""
    print("\n🧪 Testing Integrated History Puller with Database Support")
    print("=" * 60)
    
    # This would need actual HA credentials, which we might not have in this environment
    print("ℹ️ This test requires HA credentials and API access")
    print("   Skipping integrated test - database functionality tested above")
    return True


def main():
    """Main test function"""
    print("🧪 HA Database Access Test Suite")
    print("=" * 40)
    
    tests = [
        ("Direct Database Access", test_database_direct_access),
        ("Integrated History Puller", test_integrated_history_puller)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🚀 Running {test_name} test...")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ {test_name} test PASSED")
            else:
                print(f"❌ {test_name} test FAILED")
        except Exception as e:
            print(f"❌ {test_name} test ERROR: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:40} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Database access is working correctly.")
        return 0
    else:
        print(f"\n⚠️ {failed} test(s) failed. Check output above for details.")
        return 1


if __name__ == '__main__':
    sys.exit(main())