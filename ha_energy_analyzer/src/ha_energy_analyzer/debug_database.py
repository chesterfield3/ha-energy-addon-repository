#!/usr/bin/env python3
"""
Debug script for Home Assistant database access.
Use this to understand what data is available in the database.
"""

from ha_database_puller import HomeAssistantDatabasePuller
from datetime import datetime, timedelta
import sys
import os

def main():
    """Main debug function."""
    print("🔍 Home Assistant Database Debug Tool")
    print("=" * 50)
    
    # Database path - adjust as needed
    db_path = "/homeassistant/home-assistant_v2.db"
    
    print(f"📂 Database path: {db_path}")
    print(f"📁 File exists: {os.path.exists(db_path)}")
    
    # Initialize database puller
    db_puller = HomeAssistantDatabasePuller(db_path)
    
    if not db_puller.connect():
        print("❌ Failed to connect to database")
        return
    
    print("✅ Connected to database successfully")
    
    # Get basic database info
    print("\n📊 Database Information:")
    info = db_puller.get_database_info()
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Debug database contents
    print("\n🔍 Database Contents Analysis:")
    debug_info = db_puller.debug_database_contents()
    for key, value in debug_info.items():
        print(f"  {key}: {value}")
    
    # Check for energy-related entities
    print("\n⚡ Energy-related Entities:")
    energy_debug = db_puller.debug_database_contents('energy')
    for key, value in energy_debug.items():
        print(f"  {key}: {value}")
    
    # Check for sensor entities
    print("\n📊 Sensor Entities:")
    sensor_debug = db_puller.debug_database_contents('sensor.')
    for key, value in sensor_debug.items():
        print(f"  {key}: {value}")
    
    # Test a sample query if we found any entities
    sample_entities = debug_info.get('sample_statistic_ids', [])
    if sample_entities:
        print(f"\n🧪 Testing with sample entity: {sample_entities[0]}")
        
        # Test recent data (last 24 hours)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)
        
        # Try statistics first
        stats_data = db_puller.get_entity_statistics(
            sample_entities[0], 
            start_time, 
            end_time
        )
        print(f"📈 Statistics data points: {len(stats_data)}")
        if len(stats_data) > 0:
            print(f"   Sample record: {stats_data[0]}")
        
        # Test state entities too
        state_entities = debug_info.get('sample_entity_ids_states', [])
        if state_entities:
            print(f"\n🏠 Testing with sample state entity: {state_entities[0]}")
            
            # Test recent states
            states_data = db_puller.get_entity_states(
                state_entities[0], 
                start_time, 
                end_time
            )
            print(f"🔄 State data points: {len(states_data)}")
            if len(states_data) > 0:
                print(f"   Sample state: {states_data[0]}")
    else:
        print("\n⚠️ No sample entities found to test with")
    
    print("\n✅ Debug analysis complete!")
    print("\nTips:")
    print("- Check if your entity_id matches exactly what's in 'sample_statistic_ids' or 'sample_entity_ids_states'")
    print("- Verify your time range overlaps with 'states_time_range' or 'statistics_time_range'")
    print("- Try using entities from the samples above in your actual queries")

if __name__ == "__main__":
    main()