#!/usr/bin/env python3
"""
Emporia Vue Data Puller - Integrated with Home Assistant Energy Analysis

This script pulls Emporia Vue energy data and formats it to match
the Home Assistant data format for unified analysis.

Features:
- Pulls hourly data from Emporia Vue API
- Formats output to match HA sensor data structure
- Converts timestamps to Central Time
- Maps Emporia channels to friendly sensor names
- Supports date range selection
- Compatible with existing analysis workflow

Author: AI Assistant
Date: 2025-10-15
"""

import os
import json
import logging
import pandas as pd
import pytz
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import pyemvue
from pyemvue.enums import Scale, Unit


class EmporiaDataPuller:
    """Pull Emporia Vue data in HA-compatible format"""
    
    def __init__(self, config_file: str = "config/credentials.json"):
        self.config_file = config_file
        self.vue = None
        self.central_tz = pytz.timezone('US/Central')
        self.device_info = None
        self.channel_mappings = {}
        self.sensor_names = {}  # For storing CSV-based friendly names
        
        # Set up logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Load sensor names from CSV
        self.load_emporia_sensor_names()
        
    def test_connection(self) -> bool:
        """Test connection to Emporia Vue API"""
        try:
            self.vue = self.connect_to_emporia()
            if self.vue:
                devices = self.vue.get_devices()
                if devices:
                    print("✅ Successfully connected to Emporia Vue API")
                    print(f"📊 Found {len(devices)} device(s)")
                    for device in devices:
                        if device.device_name and device.device_name.strip():
                            print(f"   - {device.device_name} (ID: {device.device_gid})")
                    return True
                else:
                    print("❌ No devices found")
                    return False
            else:
                print("❌ Failed to connect to Emporia Vue API")
                return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def load_credentials(self) -> Optional[Dict[str, str]]:
        """Load Emporia Vue credentials"""
        try:
            if not os.path.exists(self.config_file):
                print(f"❌ Configuration file not found: {self.config_file}")
                return None
                
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            if 'emporia_vue' not in config:
                print("❌ Emporia Vue credentials not found in config file")
                return None
                
            return config['emporia_vue']
        except Exception as e:
            print(f"❌ Failed to load credentials: {e}")
            return None
    
    def load_emporia_sensor_names(self) -> bool:
        """Load Emporia sensor name mappings from CSV file"""
        try:
            # Get the base directory (where the script is located)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            emporia_csv_file = os.path.join(base_dir, 'data', 'emporia_sensors.csv')
            
            if not os.path.exists(emporia_csv_file):
                print(f"⚠️ Warning: Emporia sensors CSV file '{emporia_csv_file}' not found!")
                return False
            
            # Read the CSV file with sensor names
            import pandas as pd
            df = pd.read_csv(emporia_csv_file)
            
            # Clean up column names (remove spaces)
            df.columns = df.columns.str.strip()
            
            # Create the mapping dictionary
            for _, row in df.iterrows():
                entity_id = str(row['entity_id']).strip()
                name = str(row['name']).strip()
                self.sensor_names[entity_id] = name
            
            print(f"📋 Loaded {len(self.sensor_names)} Emporia sensor name mappings")
            return True
            
        except Exception as e:
            print(f"⚠️ Warning: Failed to load Emporia sensor names: {e}")
            return False
    
    def connect_to_emporia(self) -> Optional[pyemvue.PyEmVue]:
        """Connect to Emporia Vue"""
        creds = self.load_credentials()
        if not creds:
            return None
            
        try:
            vue = pyemvue.PyEmVue()
            vue.login(username=creds['email'], password=creds['password'])
            return vue
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return None
    
    def get_device_and_channels(self) -> bool:
        """Get device info and channel mappings"""
        if not self.vue:
            return False
            
        try:
            devices = self.vue.get_devices()
            self.device_info = [d for d in devices if d.device_name and d.device_name.strip()][0]
            
            print(f"📊 Using device: {self.device_info.device_name}")
            
            # Get current usage to discover channels
            usage_data = self.vue.get_device_list_usage(
                deviceGids=[str(self.device_info.device_gid)],
                instant=datetime.now(),
                scale='1H',
                unit='KilowattHours'
            )
            
            if self.device_info.device_gid not in usage_data:
                print("❌ No usage data found for device")
                return False
            
            usage_device = usage_data[self.device_info.device_gid]
            
            # Map channels to friendly names
            channel_count = 0
            for channel_key, channel_usage_obj in usage_device.channels.items():
                friendly_name = self.get_friendly_channel_name(channel_key, getattr(channel_usage_obj, 'name', ''))
                entity_id = f"sensor.emporia_{self.sanitize_name(friendly_name)}_today_s_consumption"
                
                self.channel_mappings[channel_key] = {
                    'entity_id': entity_id,
                    'friendly_name': friendly_name,
                    'original_name': getattr(channel_usage_obj, 'name', ''),
                    'channel_type': self.get_channel_type(channel_key, friendly_name)
                }
                channel_count += 1
            
            print(f"📋 Discovered {channel_count} Emporia channels")
            return True
            
        except Exception as e:
            print(f"❌ Failed to get device info: {e}")
            return False
    
    def get_friendly_channel_name(self, channel_num: str, channel_name: str) -> str:
        """Generate friendly names for Emporia channels"""
        if channel_num == 'TotalUsage':
            return "emporia_total_usage"
        elif channel_num == 'Balance':
            return "emporia_grid_balance"
        elif channel_num == '1,2,3':
            return "emporia_main_panel"
        elif channel_name:
            # Clean up the API name
            name_lower = channel_name.lower().strip()
            if 'solar' in name_lower:
                return f"emporia_solar_{self.sanitize_name(channel_name)}"
            elif name_lower == 'main':
                return "emporia_main"
            else:
                return f"emporia_{self.sanitize_name(channel_name)}"
        else:
            return f"emporia_circuit_{channel_num.replace(',', '_')}"
    
    def sanitize_name(self, name: str) -> str:
        """Convert name to valid entity ID format"""
        return name.lower().replace(' ', '_').replace('-', '_').replace('/', '_').replace('(', '').replace(')', '')
    
    def get_channel_type(self, channel_num: str, friendly_name: str) -> str:
        """Determine channel type"""
        if 'solar' in friendly_name.lower():
            return 'solar'
        elif channel_num in ['TotalUsage', '1,2,3', 'Main']:
            return 'main'
        elif channel_num == 'Balance':
            return 'grid'
        else:
            return 'circuit'
    
    def convert_to_central_time(self, utc_dt: datetime) -> str:
        """
        Convert UTC datetime to Central Time ISO string
        NOTE: Currently unused - Emporia data is already in Central time
        """
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
        
        central_dt = utc_dt.astimezone(self.central_tz)
        return central_dt.isoformat()
    
    def get_history_data(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get Emporia history data in HA-compatible format.
        
        Args:
            start_date: Start datetime
            end_date: End datetime
            
        Returns:
            List of records in HA format
        """
        if not self.vue or not self.device_info:
            print("❌ Not connected to Emporia Vue")
            return []
        
        print(f"🔄 Fetching Emporia data from {start_date} to {end_date}")
        print(f"📡 Device: {self.device_info.device_name}")
        print(f"🎯 Channels: {len(self.channel_mappings)}")
        
        all_records = []
        device_gid = str(self.device_info.device_gid)
        
        try:
            # Collect data hour by hour
            current_time = start_date.replace(minute=0, second=0, microsecond=0)
            total_hours = int((end_date - start_date).total_seconds() / 3600)
            processed_hours = 0
            
            while current_time < end_date:
                try:
                    # Get usage data for this hour
                    hourly_usage = self.vue.get_device_list_usage(
                        deviceGids=[device_gid],
                        instant=current_time,
                        scale='1H',
                        unit='KilowattHours'
                    )
                    
                    if int(device_gid) in hourly_usage:
                        usage_device = hourly_usage[int(device_gid)]
                        
                        if hasattr(usage_device, 'channels'):
                            for channel_num, channel_usage_obj in usage_device.channels.items():
                                if channel_num in self.channel_mappings:
                                    mapping = self.channel_mappings[channel_num]
                                    kwh_value = getattr(channel_usage_obj, 'usage', 0.0)
                                    
                                    # Get friendly name from CSV if available, otherwise use auto-generated
                                    entity_id = mapping['entity_id']
                                    friendly_name = self.sensor_names.get(entity_id, mapping['friendly_name'])
                                    
                                    # Convert to HA format
                                    record = {
                                        'entity_id': entity_id,
                                        'state': str(kwh_value) if kwh_value is not None else '0.0',
                                        'last_changed': current_time.isoformat(),
                                        'last_updated': current_time.isoformat(),
                                        'attributes': json.dumps({
                                            'unit_of_measurement': 'kWh',
                                            'device_class': 'energy',
                                            'friendly_name': friendly_name,
                                            'source': 'emporia_vue',
                                            'channel_type': mapping['channel_type'],
                                            'original_channel': channel_num
                                        })
                                    }
                                    all_records.append(record)
                
                except Exception as e:
                    self.logger.debug(f"Failed to get data for {current_time}: {e}")
                
                # Progress tracking
                processed_hours += 1
                if processed_hours % 24 == 0:
                    progress = (processed_hours / total_hours) * 100
                    print(f"⏰ Progress: {processed_hours}/{total_hours} hours ({progress:.1f}%)")
                
                # Move to next hour
                current_time += timedelta(hours=1)
            
            print(f"✅ Successfully retrieved Emporia data")
            print(f"📊 Total data points: {len(all_records)}")
            
            return all_records
            
        except Exception as e:
            print(f"❌ Error fetching Emporia data: {e}")
            return []
    
    def get_sensor_mappings(self) -> Dict[str, str]:
        """Get sensor mappings for CSV compatibility with friendly names from CSV"""
        mappings = {}
        for channel_data in self.channel_mappings.values():
            entity_id = channel_data['entity_id']
            # Use CSV-based name if available, otherwise use auto-generated friendly name
            friendly_name = self.sensor_names.get(entity_id, channel_data['friendly_name'])
            mappings[entity_id] = friendly_name
        return mappings
    
    def save_sensor_mappings_csv(self, filename: str = "emporia_sensors.csv") -> bool:
        """Save sensor mappings to CSV file (similar to ha_sensors.csv)"""
        try:
            with open(filename, 'w', newline='') as f:
                f.write("entity_id, name\n")
                for channel_data in self.channel_mappings.values():
                    f.write(f"{channel_data['entity_id']}, {channel_data['friendly_name']}\n")
            
            print(f"💾 Saved Emporia sensor mappings to {filename}")
            return True
        except Exception as e:
            print(f"❌ Failed to save sensor mappings: {e}")
            return False


def main():
    """Test function"""
    print("🔌 Emporia Vue Data Puller Test")
    print("=" * 50)
    
    puller = EmporiaDataPuller()
    
    # Test connection
    if not puller.test_connection():
        return
    
    # Get device info
    if not puller.get_device_and_channels():
        return
    
    # Save sensor mappings
    puller.save_sensor_mappings_csv()
    
    # Test data pull (last 24 hours)
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=24)
    
    print(f"\n🧪 Testing data pull for last 24 hours...")
    data = puller.get_history_data(start_date, end_date)
    
    if data:
        print(f"✅ Test successful! Retrieved {len(data)} records")
        
        # Show sample data
        print(f"\n📋 Sample records:")
        for i, record in enumerate(data[:3]):
            print(f"   {i+1}. {record['entity_id']}: {record['state']} kWh at {record['last_changed']}")
        
        if len(data) > 3:
            print(f"   ... and {len(data) - 3} more records")
    else:
        print("❌ Test failed - no data retrieved")


if __name__ == "__main__":
    main()