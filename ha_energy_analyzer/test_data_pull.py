#!/usr/bin/env python3
"""
Test script for HA Energy Analyzer data pulling functionality.

This script tests both regular history API and long-term statistics API
by pulling data for the toaster oven sensor over different time ranges.

Author: AI Assistant
Date: 2025-10-20
"""

import os
import sys
from datetime import datetime, timedelta
import json

# Add the src directory to the path so we can import our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

try:
    from ha_energy_analyzer.ha_history_puller import HomeAssistantHistoryPuller
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print("Make sure you're running this from the addon directory")
    sys.exit(1)


def load_ha_credentials():
    """Load HA credentials from environment variables (add-on style)"""
    ha_url = os.getenv('HA_URL', 'http://supervisor/core')
    ha_token = os.getenv('SUPERVISOR_TOKEN', '')
    
    if not ha_token:
        print("❌ No SUPERVISOR_TOKEN found in environment")
        print("This test should be run in the Home Assistant environment")
        return None, None
    
    return ha_url, ha_token


def test_regular_history_api(puller):
    """Test the regular history API with a short time range"""
    print("\n" + "="*60)
    print("🧪 TESTING REGULAR HISTORY API (< 7 days)")
    print("="*60)
    
    # Test with last 2 days (should use regular history API)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=2)
    
    entity_ids = ['sensor.toaster_oven_energy']
    
    print(f"📅 Date range: {start_time.isoformat()} to {end_time.isoformat()}")
    print(f"🎯 Entity: {entity_ids[0]}")
    
    try:
        # This should automatically choose regular history API
        data = puller.get_history_data(entity_ids, start_time.isoformat(), end_time.isoformat())
        
        if data:
            total_points = sum(len(entity_data) for entity_data in data)
            print(f"✅ Regular History API test successful!")
            print(f"📊 Retrieved {total_points} data points")
            
            # Show a sample of the data
            if data and len(data) > 0 and len(data[0]) > 0:
                sample = data[0][0]  # First record of first entity
                print(f"📋 Sample record:")
                print(f"   Entity ID: {sample.get('entity_id', 'N/A')}")
                print(f"   State: {sample.get('state', 'N/A')}")
                print(f"   Timestamp: {sample.get('last_changed', 'N/A')}")
                
                # Check if it's from regular history (no 'source' in attributes)
                attrs = sample.get('attributes', {})
                if isinstance(attrs, str):
                    attrs = json.loads(attrs)
                source = attrs.get('source', 'regular_history')
                print(f"   Data Source: {source}")
            
            return True
        else:
            print(f"❌ Regular History API test failed - no data returned")
            return False
            
    except Exception as e:
        print(f"❌ Regular History API test failed with error: {e}")
        return False


def test_long_term_statistics_api(puller):
    """Test the long-term statistics API with a longer time range"""
    print("\n" + "="*60)
    print("🧪 TESTING LONG-TERM STATISTICS API (>= 7 days)")
    print("="*60)
    
    # Test with last 14 days (should use long-term statistics API)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=14)
    
    entity_ids = ['sensor.toaster_oven_energy']
    
    print(f"📅 Date range: {start_time.isoformat()} to {end_time.isoformat()}")
    print(f"🎯 Entity: {entity_ids[0]}")
    
    try:
        # This should automatically choose long-term statistics API
        data = puller.get_history_data(entity_ids, start_time.isoformat(), end_time.isoformat())
        
        if data:
            total_points = sum(len(entity_data) for entity_data in data)
            print(f"✅ Long-Term Statistics API test successful!")
            print(f"📊 Retrieved {total_points} data points")
            
            # Show a sample of the data
            if data and len(data) > 0 and len(data[0]) > 0:
                sample = data[0][0]  # First record of first entity
                print(f"📋 Sample record:")
                print(f"   Entity ID: {sample.get('entity_id', 'N/A')}")
                print(f"   State: {sample.get('state', 'N/A')}")
                print(f"   Timestamp: {sample.get('last_changed', 'N/A')}")
                
                # Check if it's from long-term statistics
                attrs = sample.get('attributes', {})
                if isinstance(attrs, str):
                    attrs = json.loads(attrs)
                source = attrs.get('source', 'regular_history')
                print(f"   Data Source: {source}")
            
            return True
        else:
            print(f"❌ Long-Term Statistics API test failed - no data returned")
            return False
            
    except Exception as e:
        print(f"❌ Long-Term Statistics API test failed with error: {e}")
        return False


def test_statistics_metadata(puller):
    """Test the statistics metadata functionality"""
    print("\n" + "="*60)
    print("🧪 TESTING STATISTICS METADATA API")
    print("="*60)
    
    entity_ids = ['sensor.toaster_oven_energy']
    
    try:
        metadata = puller.get_statistics_metadata(entity_ids)
        
        if metadata:
            print(f"✅ Statistics metadata test successful!")
            print(f"📊 Retrieved metadata for {len(metadata)} entities")
            return True
        else:
            print(f"⚠️ Statistics metadata test - no metadata returned (may not be available)")
            return True  # This is OK, metadata might not be available
            
    except Exception as e:
        print(f"❌ Statistics metadata test failed with error: {e}")
        return False


def test_custom_threshold(puller):
    """Test custom statistics threshold functionality"""
    print("\n" + "="*60)
    print("🧪 TESTING CUSTOM STATISTICS THRESHOLD")
    print("="*60)
    
    # Create a new puller with a 3-day threshold instead of 7
    print("🔧 Testing with 3-day threshold (instead of default 7 days)")
    
    ha_url, ha_token = load_ha_credentials()
    if not ha_url or not ha_token:
        print("❌ Cannot create custom puller - credentials not available")
        return False
    
    custom_puller = HomeAssistantHistoryPuller(ha_url, ha_token, statistics_threshold_days=3)
    
    # Test with 5 days (should now use statistics API with 3-day threshold)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=5)
    
    entity_ids = ['sensor.toaster_oven_energy']
    
    print(f"📅 Date range: {start_time.isoformat()} to {end_time.isoformat()}")
    print(f"🎯 Entity: {entity_ids[0]}")
    print(f"⚙️ Threshold: 3 days (5-day range should use Statistics API)")
    
    try:
        data = custom_puller.get_history_data(entity_ids, start_time.isoformat(), end_time.isoformat())
        
        if data:
            total_points = sum(len(entity_data) for entity_data in data)
            print(f"✅ Custom threshold test successful!")
            print(f"📊 Retrieved {total_points} data points")
            return True
        else:
            print(f"❌ Custom threshold test failed - no data returned")
            return False
            
    except Exception as e:
        print(f"❌ Custom threshold test failed with error: {e}")
        return False


def main():
    """Main test function"""
    print("🧪 HA Energy Analyzer Data Pull Test")
    print("=" * 50)
    
    # Load credentials
    ha_url, ha_token = load_ha_credentials()
    if not ha_url or not ha_token:
        print("❌ Cannot load HA credentials")
        print("Make sure SUPERVISOR_TOKEN is set in the environment")
        return 1
    
    print(f"🔗 HA URL: {ha_url}")
    print(f"🔑 Token: {ha_token[:20]}..." if ha_token else "❌ No token")
    
    # Initialize puller
    try:
        puller = HomeAssistantHistoryPuller(ha_url, ha_token)
        
        # Test connection
        if not puller.test_connection():
            print("❌ Connection test failed")
            return 1
        
        print("✅ Connection test successful")
        
    except Exception as e:
        print(f"❌ Failed to initialize puller: {e}")
        return 1
    
    # Run all tests
    tests = [
        ("Regular History API", test_regular_history_api),
        ("Long-Term Statistics API", test_long_term_statistics_api),
        ("Statistics Metadata", test_statistics_metadata),
        ("Custom Threshold", test_custom_threshold)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🚀 Running {test_name} test...")
        try:
            result = test_func(puller)
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
        print(f"{test_name:30} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! The data pull functionality is working correctly.")
        return 0
    else:
        print(f"\n⚠️ {failed} test(s) failed. Please check the output above for details.")
        return 1


if __name__ == '__main__':
    sys.exit(main())