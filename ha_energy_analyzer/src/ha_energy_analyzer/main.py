#!/usr/bin/env python3
"""
Main interface for Home Assistant History Data Puller

This script provides a user-friendly interface to pull historical data
from Home Assistant with pre-defined date ranges and custom options.

Author: AI Assistant
Date: 2025-10-15
"""

import os
import sys
import csv
import json
import pandas as pd
from datetime import datetime, timedelta
import pytz
from typing import Optional, Tuple, Dict, List, Any

# Try to import holidays library for holiday detection
try:
    import holidays
    HOLIDAYS_AVAILABLE = True
except ImportError:
    HOLIDAYS_AVAILABLE = False
    holidays = None

# Handle imports for both direct execution and module import
try:
    from .ha_history_puller import HomeAssistantHistoryPuller
    from .data_analysis import EnergyDataAnalyzer
    from .emporia_data_puller import EmporiaDataPuller
except ImportError:
    # If relative imports fail, try absolute imports for direct execution
    from ha_history_puller import HomeAssistantHistoryPuller
    from data_analysis import EnergyDataAnalyzer
    from emporia_data_puller import EmporiaDataPuller


class HAHistoryMain:
    """Main interface for HA History Puller"""
    
    def __init__(self):
        """Initialize with default configuration"""
        # Get path to base directory from the src/ha_energy_analyzer directory
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.csv_file = os.path.join(self.base_dir, 'data', 'ha_sensors.csv')
        
        # Load credentials from config file
        self.ha_url, self.ha_token = self.load_ha_credentials()
        self.puller: Optional[HomeAssistantHistoryPuller] = None
        self.emporia_puller: Optional[EmporiaDataPuller] = None
        
        self.central_tz = pytz.timezone('US/Central')
        self.sensor_names: Dict[str, Dict[str, str]] = {}
        self.emporia_available = False
    
    def load_ha_credentials(self) -> Tuple[str, str]:
        """
        Load Home Assistant credentials from config file
        
        Returns:
            Tuple of (url, token)
        """
        try:
            credentials_path = os.path.join(self.base_dir, 'config', 'credentials.json')
            
            # Check if credentials file exists
            if not os.path.exists(credentials_path):
                print(f"⚠️ Credentials file not found: {credentials_path}")
                print("Using environment variables or defaults...")
                return (
                    os.getenv('HA_URL', 'http://homeassistant.local:8123'),
                    os.getenv('HA_TOKEN', '')
                )
            
            # Load credentials from JSON file
            with open(credentials_path, 'r', encoding='utf-8') as f:
                credentials = json.load(f)
            
            ha_config = credentials.get('home_assistant', {})
            ha_url = ha_config.get('url', os.getenv('HA_URL', 'http://homeassistant.local:8123'))
            ha_token = ha_config.get('token', os.getenv('HA_TOKEN', ''))
            
            if not ha_token:
                print("❌ Warning: No Home Assistant token found in credentials.json or environment!")
                print("Please add your HA token to config/credentials.json")
            
            return ha_url, ha_token
            
        except Exception as e:
            print(f"❌ Error loading HA credentials: {e}")
            print("Using environment variables or defaults...")
            return (
                os.getenv('HA_URL', 'http://homeassistant.local:8123'),
                os.getenv('HA_TOKEN', '')
            )
    
    def print_header(self):
        """Print application header"""
        print("\n" + "=" * 60)
        print("🏠 HOME ASSISTANT HISTORY DATA PULLER")
        print("=" * 60)
        print(f"🔗 HA URL: {self.ha_url}")
        print(f"📄 CSV File: {self.csv_file}")
        print("=" * 60)
    
    def initialize_puller(self) -> bool:
        """Initialize and test HA connection"""
        print("\n🔄 Initializing Home Assistant connection...")
        
        if not self.ha_token or self.ha_token == 'your_token_here':
            print("❌ Error: Home Assistant token not configured!")
            print("   Please set the HA_TOKEN environment variable or update the script.")
            return False
        
        self.puller = HomeAssistantHistoryPuller(self.ha_url, self.ha_token)
        
        if not self.puller.test_connection():
            return False
        
        # Check if CSV file exists
        if not os.path.exists(self.csv_file):
            print(f"❌ Error: CSV file '{self.csv_file}' not found!")
            print("   Please make sure your CSV file is in the current directory.")
            return False
        
        # Load sensor name mappings
        self.load_sensor_names()
        
        # Initialize Emporia puller (optional)
        self.initialize_emporia()
        
        return True
    
    def load_sensor_names(self) -> bool:
        """Load sensor name mapping and upstream sensor information from CSV file"""
        try:
            if not os.path.exists(self.csv_file):
                print(f"⚠️ Warning: CSV file '{self.csv_file}' not found for sensor names!")
                return False
            
            # Read the CSV file with sensor names
            df = pd.read_csv(self.csv_file)
            
            # Clean up column names (remove spaces)
            df.columns = df.columns.str.strip()
            
            # Create the mapping dictionary with full sensor information
            for _, row in df.iterrows():
                entity_id = str(row['entity_id']).strip()
                name = str(row['name']).strip()
                upstream_sensor = str(row.get('upstream_sensor', 'none')).strip()
                
                self.sensor_names[entity_id] = {
                    'name': name,
                    'upstream_sensor': upstream_sensor
                }
            
            print(f"📋 Loaded {len(self.sensor_names)} sensor name mappings")
            return True
            
        except Exception as e:
            print(f"⚠️ Warning: Failed to load sensor names: {e}")
            return False
    
    def convert_to_central_time(self, timestamp_str: str) -> str:
        """
        Convert UTC timestamp string to Central Time.
        
        Args:
            timestamp_str: UTC timestamp string from HA
            
        Returns:
            str: Central Time timestamp string
        """
        try:
            if not timestamp_str:
                return timestamp_str
            
            # Parse the UTC timestamp
            if timestamp_str.endswith('Z'):
                # Handle Z suffix for UTC
                utc_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            elif '+' in timestamp_str or timestamp_str.endswith('00:00'):
                # Handle ISO format with timezone
                utc_dt = datetime.fromisoformat(timestamp_str)
            else:
                # Assume UTC if no timezone info
                utc_dt = datetime.fromisoformat(timestamp_str).replace(tzinfo=pytz.UTC)
            
            # Convert to Central Time
            central_dt = utc_dt.astimezone(self.central_tz)
            
            # Return as ISO format string
            return central_dt.isoformat()
            
        except Exception as e:
            print(f"⚠️ Warning: Failed to convert timestamp '{timestamp_str}': {e}")
            return timestamp_str
    
    def get_timezone_offset_hours(self, dt):
        """
        Get the current timezone offset from UTC in hours for a given datetime.
        Accounts for both timezone and daylight savings time.
        
        Args:
            dt: datetime object to check offset for
            
        Returns:
            int: Offset hours from UTC (negative for timezones behind UTC)
        """
        try:
            # Ensure datetime has timezone info
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.UTC)
            
            # Convert to Central Time to get the actual offset
            central_dt = dt.astimezone(self.central_tz)
            offset_seconds = central_dt.utcoffset().total_seconds()
            offset_hours = int(offset_seconds / 3600)
            
            return offset_hours
        except Exception as e:
            print(f"⚠️ Warning: Failed to get timezone offset: {e}")
            return -5  # Default to CDT offset
    
    def adjust_datetime_for_service_request(self, dt, service_type, is_end_date=False):
        """
        Adjust datetime for service API requests to account for timezone differences.
        
        Args:
            dt: datetime object to adjust
            service_type: 'ha' or 'emporia'
            is_end_date: True if this is an end date, False for start date
            
        Returns:
            datetime: Adjusted datetime for API request
        """
        try:
            # Get current timezone offset (includes DST)
            offset_hours = self.get_timezone_offset_hours(dt)
            
            if service_type == 'emporia':
                # Emporia expects UTC but we want CDT data
                # If we're at CDT (-5), request data 5 hours later in UTC to get correct CDT time
                adjusted_dt = dt + timedelta(hours=abs(offset_hours))
                print(f"🔧 Emporia request: Adjusting {dt} by +{abs(offset_hours)} hours -> {adjusted_dt}")
                return adjusted_dt
                
            elif service_type == 'ha':
                # HA needs the 2-hour sensor reset offset plus 2-hour alignment offset
                # We request data starting earlier to account for sensor reset behavior 
                # AND the later 2-hour alignment adjustment that shifts HA data back
                # Total: -2 hours (sensor reset) + 2 hours (to compensate for later -2 alignment) = 0 hours
                adjusted_dt = dt  # No net adjustment needed
                
                # Add 1 hour to end date to capture the missing last hour
                if is_end_date:
                    adjusted_dt = dt + timedelta(hours=1)
                    print(f"🔧 HA request (end): Adding 1 hour to {dt} -> {adjusted_dt} (to capture last hour)")
                else:
                    print(f"🔧 HA request (start): Using original time {dt} (accounts for later -2hr alignment)")
                
                return adjusted_dt
                
            return dt
            
        except Exception as e:
            print(f"⚠️ Warning: Failed to adjust datetime for {service_type}: {e}")
            return dt
    
    def fetch_emporia_data_with_protection(self, start_date, end_date):
        """
        Fetch Emporia data with timeout protection and automatic chunking for large requests
        
        Args:
            start_date: Start datetime for data request
            end_date: End datetime for data request
            
        Returns:
            Combined emporia data or None if failed
        """
        import threading
        import time
        from datetime import timedelta
        
        try:
            # Ensure timezone consistency
            if start_date.tzinfo is not None:
                start_date = start_date.replace(tzinfo=None)
            if end_date.tzinfo is not None:
                end_date = end_date.replace(tzinfo=None)
            
            # Check if emporia_puller is available
            if not self.emporia_puller:
                print("❌ Emporia puller not available")
                return None
            
            # Hard-coded Emporia service start date - never request data before this
            from datetime import datetime
            emporia_service_start = datetime(2025, 9, 27)
            
            # Adjust start_date if it's before Emporia service started
            if start_date.replace(tzinfo=None) < emporia_service_start:
                original_start = start_date
                start_date = start_date.replace(year=2025, month=9, day=27, hour=0, minute=0, second=0, microsecond=0)
                print(f"🔧 Adjusted Emporia start date from {original_start} to {start_date} (service started Sept 27, 2025)")
            
            # Also ensure end_date is not before service start
            if end_date.replace(tzinfo=None) < emporia_service_start:
                print(f"⚠️ End date {end_date} is before Emporia service start. No data available.")
                return None
            
            # Calculate duration
            duration = end_date - start_date
            total_hours = duration.total_seconds() / 3600
            
            # If request is longer than 48 hours, chunk it
            if total_hours > 48:
                print(f"🔧 Large request detected ({total_hours:.1f} hours). Chunking into smaller pieces...")
                return self.fetch_emporia_data_chunked(start_date, end_date)
            
            print(f"🔄 Fetching Emporia data from {start_date} to {end_date}")
            
            # Use threading to implement timeout
            from typing import Any, Dict
            result: Dict[str, Any] = {'data': None}
            exception: Dict[str, Any] = {'error': None}
            
            def fetch_data():
                try:
                    if self.emporia_puller:
                        result['data'] = self.emporia_puller.get_history_data(start_date, end_date)
                except Exception as e:
                    exception['error'] = e
            
            # Start the fetch in a separate thread
            fetch_thread = threading.Thread(target=fetch_data)
            fetch_thread.daemon = True
            fetch_thread.start()
            
            # Wait for completion with timeout (5 minutes)
            fetch_thread.join(timeout=300)
            
            if fetch_thread.is_alive():
                print("⚠️ Emporia request timed out. Trying chunked approach...")
                return self.fetch_emporia_data_chunked(start_date, end_date)
            
            if exception['error']:
                raise exception['error']
                
            return result['data']
            
        except Exception as e:
            print(f"❌ Error fetching Emporia data: {e}")
            print("⚠️ Trying chunked approach as fallback...")
            return self.fetch_emporia_data_chunked(start_date, end_date)
    
    def fetch_emporia_data_chunked(self, start_date, end_date, chunk_hours=24):
        """
        Fetch Emporia data in smaller chunks to avoid timeouts
        
        Args:
            start_date: Start datetime
            end_date: End datetime  
            chunk_hours: Hours per chunk (default 24)
            
        Returns:
            Combined data from all chunks
        """
        try:
            from datetime import timedelta, datetime
            
            # Check if emporia_puller is available
            if not self.emporia_puller:
                print("❌ Emporia puller not available")
                return None
            
            # Hard-coded Emporia service start date - never request data before this
            emporia_service_start = datetime(2025, 9, 27)
            
            # Adjust start_date if it's before Emporia service started
            if start_date.replace(tzinfo=None) < emporia_service_start:
                original_start = start_date
                start_date = start_date.replace(year=2025, month=9, day=27, hour=0, minute=0, second=0, microsecond=0)
                print(f"🔧 Adjusted chunked Emporia start date from {original_start} to {start_date} (service started Sept 27, 2025)")
            
            # Also ensure end_date is not before service start
            if end_date.replace(tzinfo=None) < emporia_service_start:
                print(f"⚠️ End date {end_date} is before Emporia service start. No data available.")
                return None
            
            print(f"📊 Chunking Emporia request into {chunk_hours}-hour segments...")
            
            # Ensure timezone consistency for comparisons
            if start_date.tzinfo is not None:
                start_date = start_date.replace(tzinfo=None)
            if end_date.tzinfo is not None:
                end_date = end_date.replace(tzinfo=None)
            
            all_data = []
            current_start = start_date
            chunk_count = 0
            
            while current_start < end_date:
                chunk_end = min(current_start + timedelta(hours=chunk_hours), end_date)
                chunk_count += 1
                
                print(f"   📦 Chunk {chunk_count}: {current_start} to {chunk_end}")
                
                try:
                    chunk_data = self.emporia_puller.get_history_data(current_start, chunk_end)
                    if chunk_data:
                        all_data.extend(chunk_data)
                        print(f"   ✅ Retrieved {len(chunk_data)} records")
                    else:
                        print(f"   ⚠️ No data returned for chunk {chunk_count}")
                        
                except Exception as e:
                    print(f"   ❌ Error in chunk {chunk_count}: {e}")
                    # Continue with next chunk rather than failing completely
                
                current_start = chunk_end
            
            print(f"✅ Chunked retrieval complete: {len(all_data)} total records from {chunk_count} chunks")
            return all_data if all_data else None
            
        except Exception as e:
            print(f"❌ Chunked fetch failed: {e}")
            return None

    def correct_service_data_timestamps(self, data, service_type):
        """
        Correct timestamps in data returned from services to match local time.
        
        Args:
            data: Data returned from service (list or DataFrame)
            service_type: 'ha' or 'emporia'
            
        Returns:
            Data with corrected timestamps
        """
        try:
            if service_type == 'emporia':
                # Emporia returns UTC timestamps but represents CDT events
                # Need to subtract timezone offset to get correct local time
                print(f"🔧 Correcting Emporia timestamps to local time")
                for record in data:
                    if isinstance(record, dict):
                        for time_field in ['last_changed', 'last_updated']:
                            if time_field in record:
                                original_time = record[time_field]
                                if original_time:
                                    # Parse UTC time and convert to local
                                    utc_dt = pd.to_datetime(original_time)
                                    offset_hours = self.get_timezone_offset_hours(utc_dt)
                                    local_dt = utc_dt + timedelta(hours=offset_hours)
                                    record[time_field] = local_dt.strftime('%Y-%m-%dT%H:%M:%S')
                                    
            elif service_type == 'ha':
                # HA timestamps should be corrected for the sensor reset behavior
                # The 2-hour offset was applied to the request, now adjust the response timestamps
                print(f"🔧 Correcting HA timestamps for sensor reset behavior")
                for entity_data in data:
                    for record in entity_data:
                        for time_field in ['last_changed', 'last_updated']:
                            if time_field in record:
                                original_time = record[time_field]
                                if original_time:
                                    # Adjust timestamp forward by 1 hour to account for sensor reset request offset
                                    dt = pd.to_datetime(original_time)
                                    corrected_dt = dt + timedelta(hours=1)
                                    record[time_field] = corrected_dt.strftime('%Y-%m-%dT%H:%M:%S%z')
                                    
            return data
            
        except Exception as e:
            print(f"⚠️ Warning: Failed to correct {service_type} timestamps: {e}")
            return data
    
    def initialize_emporia(self):
        """Initialize Emporia Vue connection (optional)"""
        try:
            print("🔌 Checking Emporia Vue connection...")
            
            # In add-on environment, try environment variables first
            emporia_email = os.getenv('EMPORIA_EMAIL')
            emporia_password = os.getenv('EMPORIA_PASSWORD')
            
            if emporia_email and emporia_password:
                print("🔧 Using Emporia credentials from environment variables")
                # Create a temporary credentials dict for the puller
                temp_config = {
                    'emporia_vue': {
                        'email': emporia_email,
                        'password': emporia_password
                    }
                }
                # Initialize with environment variables
                self.emporia_puller = EmporiaDataPuller()
                # Override the load_credentials method temporarily
                self.emporia_puller.load_credentials = lambda: temp_config['emporia_vue']
            else:
                # Fall back to config file
                config_path = os.path.join(self.base_dir, 'config', 'credentials.json')
                self.emporia_puller = EmporiaDataPuller(config_path)
            
            if self.emporia_puller.test_connection():
                if self.emporia_puller.get_device_and_channels():
                    self.emporia_available = True
                    print("✅ Emporia Vue integration available")
                    
                    # Load Emporia sensor mappings
                    emporia_mappings = self.emporia_puller.get_sensor_mappings()
                    # Convert Emporia mappings to new dictionary format
                    for entity_id, name in emporia_mappings.items():
                        self.sensor_names[entity_id] = {
                            'name': name,
                            'upstream_sensor': 'none'  # Emporia sensors don't have upstream devices
                        }
                    print(f"📋 Added {len(emporia_mappings)} Emporia sensor mappings")
                else:
                    print("⚠️ Emporia Vue connected but no channels found")
                    self.emporia_available = False
            else:
                print("⚠️ Emporia Vue not available - continuing with HA only")
                self.emporia_available = False
                
        except Exception as e:
            print(f"⚠️ Emporia Vue initialization failed: {e}")
            self.emporia_available = False
    
    def get_data_source_preference(self) -> str:
        """Ask user which data sources to include"""
        if not self.emporia_available:
            print("ℹ️ Only Home Assistant data available")
            return 'ha_only'
        
        print("\n📊 Data Source Options:")
        print("-" * 25)
        print("  1. Home Assistant only")
        print("  2. Emporia Vue only")
        print("  3. Both HA and Emporia (combined)")
        
        while True:
            choice = input("\nChoose data sources (1-3) [default: 3]: ").strip()
            if not choice:
                return 'both'
            elif choice == '1':
                return 'ha_only'
            elif choice == '2':
                return 'emporia_only'
            elif choice == '3':
                return 'both'
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
    
    def get_date_range_options(self) -> dict:
        """Get predefined date range options"""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return {
            '1': {
                'name': 'Today (so far)',
                'start': today_start,
                'end': now
            },
            '2': {
                'name': 'Yesterday (full day)',
                'start': today_start - timedelta(days=1),
                'end': today_start
            },
            '3': {
                'name': 'Last 24 hours',
                'start': now - timedelta(hours=24),
                'end': now
            },
            '4': {
                'name': 'Last 7 days',
                'start': today_start - timedelta(days=7),
                'end': now
            },
            '5': {
                'name': 'Last 30 days',
                'start': today_start - timedelta(days=30),
                'end': now
            },
            '6': {
                'name': 'This month',
                'start': today_start.replace(day=1),
                'end': now
            },
            '7': {
                'name': 'Last month',
                'start': (today_start.replace(day=1) - timedelta(days=1)).replace(day=1),
                'end': today_start.replace(day=1)
            }
        }
    
    def display_date_options(self):
        """Display available date range options"""
        options = self.get_date_range_options()
        
        print("\n📅 Available Date Ranges:")
        print("-" * 40)
        
        for key, option in options.items():
            start_str = option['start'].strftime('%Y-%m-%d %H:%M')
            end_str = option['end'].strftime('%Y-%m-%d %H:%M')
            print(f"  {key}. {option['name']}")
            print(f"     {start_str} → {end_str}")
            print()
        
        print("  8. Custom date range")
        print("  9. Incremental update (append new data only)")
        print("  0. Exit")
    
    def get_custom_date_range(self) -> Optional[Tuple[datetime, datetime]]:
        """Get custom date range from user"""
        print("\n📅 Custom Date Range")
        print("-" * 25)
        
        # Helper function to parse date input
        def parse_date_input(prompt: str) -> Optional[datetime]:
            while True:
                date_str = input(prompt).strip()
                if not date_str:
                    return None
                
                # Try different date formats
                formats = [
                    '%Y-%m-%d',
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M',
                    '%m/%d/%Y',
                    '%m/%d/%Y %H:%M:%S',
                    '%m/%d/%Y %H:%M'
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
                
                print("❌ Invalid date format. Please try again.")
                print("   Supported formats: YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, MM/DD/YYYY, etc.")
        
        start_date = parse_date_input("Enter start date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS): ")
        if not start_date:
            return None
        
        end_date = parse_date_input("Enter end date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS): ")
        if not end_date:
            return None
        
        if start_date >= end_date:
            print("❌ Error: Start date must be before end date!")
            return None
        
        return start_date, end_date
    
    def get_latest_timestamp_from_analysis(self) -> Optional[datetime]:
        """
        Read the energy_analysis.csv file and find the most recent timestamp
        
        Returns:
            datetime: Most recent timestamp found, or None if file doesn't exist/is empty
        """
        try:
            analysis_csv = os.path.join(self.base_dir, 'output', 'energy_analysis.csv')
            
            if not os.path.exists(analysis_csv):
                print(f"📄 No existing energy_analysis.csv found at {analysis_csv}")
                return None
            
            import pandas as pd
            df = pd.read_csv(analysis_csv)
            
            if df.empty:
                print(f"📄 Existing energy_analysis.csv is empty")
                return None
            
            # Find the datetime column
            if 'datetime' not in df.columns:
                print(f"❌ No 'datetime' column found in energy_analysis.csv")
                return None
            
            # Parse timestamps and find the latest
            df['datetime'] = pd.to_datetime(df['datetime'])
            latest_timestamp = df['datetime'].max()
            
            print(f"📅 Found latest data timestamp: {latest_timestamp}")
            return latest_timestamp.to_pydatetime()
            
        except Exception as e:
            print(f"❌ Error reading energy_analysis.csv: {e}")
            return None
    
    def merge_with_existing_analysis(self, new_df, output_filename: str) -> bool:
        """
        Merge new analysis data with existing energy_analysis.csv, removing overlaps
        and keeping new data preferentially
        
        Args:
            new_df: New DataFrame to merge
            output_filename: Base filename for archiving the new portion
            
        Returns:
            bool: True if successful
        """
        try:
            import pandas as pd
            
            analysis_csv = os.path.join(self.base_dir, 'output', 'energy_analysis.csv')
            
            # If no existing file, just save the new data
            if not os.path.exists(analysis_csv):
                print(f"📄 No existing energy_analysis.csv, creating new one")
                if self.save_hourly_data_to_csv(new_df, analysis_csv):
                    print(f"✅ Created new energy_analysis.csv with {len(new_df)} records")
                    return True
                return False
            
            # Read existing data
            print(f"📊 Loading existing energy_analysis.csv...")
            existing_df = pd.read_csv(analysis_csv)
            print(f"📊 Existing data: {len(existing_df)} records")
            print(f"📊 New data: {len(new_df)} records")
            
            # Convert datetime columns to datetime objects for comparison
            existing_df['datetime'] = pd.to_datetime(existing_df['datetime'])
            new_df['datetime'] = pd.to_datetime(new_df['datetime'])
            
            # Find overlapping datetimes and remove them from existing data
            # Keep new data preferentially as requested
            overlapping_datetimes = set(new_df['datetime'].unique())
            filtered_existing = existing_df[~existing_df['datetime'].isin(overlapping_datetimes)]
            
            print(f"🔧 Removed {len(existing_df) - len(filtered_existing)} overlapping records from existing data")
            
            # Combine existing (non-overlapping) + new data
            merged_df = pd.concat([filtered_existing, new_df], ignore_index=True)
            
            # Sort by datetime for proper chronological order
            merged_df = merged_df.sort_values(['datetime', 'entity_id']).reset_index(drop=True)
            
            # Convert datetime back to string format for CSV output
            merged_df['datetime'] = merged_df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"🔧 Merged dataset: {len(filtered_existing)} existing + {len(new_df)} new = {len(merged_df)} total")
            
            # Save the merged data
            if self.save_hourly_data_to_csv(merged_df, analysis_csv):
                print(f"✅ Updated energy_analysis.csv with merged data")
                
                # Also archive the new portion with timestamp
                archive_dir = os.path.join(self.base_dir, 'archive')
                os.makedirs(archive_dir, exist_ok=True)
                archive_csv = os.path.join(archive_dir, f"{output_filename}.csv")
                
                # Convert new_df datetime back to string for archiving
                new_df_copy = new_df.copy()
                new_df_copy['datetime'] = new_df_copy['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
                
                if self.save_hourly_data_to_csv(new_df_copy, archive_csv):
                    print(f"✅ Archived incremental data to: {archive_csv}")
                
                return True
            else:
                print(f"❌ Failed to save merged data")
                return False
                
        except Exception as e:
            print(f"❌ Error merging with existing analysis: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_to_csv(self, history_data: Dict, output_file: str) -> bool:
        """
        Save history data to CSV file with sensor names and Central Time.
        
        Args:
            history_data: Dictionary containing history data from HA API
            output_file: Path to output CSV file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            all_records = []
            
            # Process each entity's data
            for entity_data in history_data:
                for record in entity_data:
                    entity_id = record.get('entity_id', '')
                    
                    # Get sensor name from mapping
                    sensor_mapping = self.sensor_names.get(entity_id, {})
                    sensor_name = sensor_mapping.get('name', entity_id.replace('sensor.', '').replace('_', ' ')) if isinstance(sensor_mapping, dict) else sensor_mapping
                    
                    # Convert timestamps to Central Time
                    last_changed_utc = record.get('last_changed', '')
                    last_updated_utc = record.get('last_updated', '')
                    
                    last_changed_central = self.convert_to_central_time(last_changed_utc)
                    last_updated_central = self.convert_to_central_time(last_updated_utc)
                    
                    # Clean up the record
                    clean_record = {
                        'entity_id': entity_id,
                        'sensor_name': sensor_name,
                        'state': record.get('state', ''),
                        'last_changed': last_changed_central,
                        'last_updated': last_updated_central,
                        'attributes': json.dumps(record.get('attributes', {}))
                    }
                    all_records.append(clean_record)
            
            # Create DataFrame and save to CSV
            df = pd.DataFrame(all_records)
            
            if not df.empty:
                # Sort by datetime first, then by sensor name
                df = df.sort_values(['last_changed', 'sensor_name'])
                df.to_csv(output_file, index=False)
                print(f"💾 Saved {len(df)} records to {output_file}")
                print(f"🕐 Timestamps converted to Central Time")
                print(f"🏷️ Added sensor names from {self.csv_file}")
                return True
            else:
                print("⚠️ No data to save")
                return False
                
        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")
            return False
    
    def save_to_json(self, history_data: Dict, output_file: str) -> bool:
        """
        Save history data to JSON file with sorted records.
        
        Args:
            history_data: Dictionary containing history data from HA API
            output_file: Path to output JSON file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Sort records within each entity by timestamp
            sorted_history_data = []
            for entity_data in history_data:
                # Sort each entity's records by last_changed timestamp
                sorted_entity_data = sorted(entity_data, key=lambda x: x.get('last_changed', ''))
                sorted_history_data.append(sorted_entity_data)
            
            # Sort entities by entity_id for consistent ordering
            sorted_history_data.sort(key=lambda entity_list: entity_list[0].get('entity_id', '') if entity_list else '')
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(sorted_history_data, f, indent=2, ensure_ascii=False)
            
            total_points = sum(len(entity_data) for entity_data in sorted_history_data)
            print(f"💾 Saved {total_points} records to {output_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving to JSON: {e}")
            return False
    
    def get_output_format(self) -> str:
        """Get output format preference from user"""
        print("\n💾 Output Format Options:")
        print("-" * 25)
        print("  1. CSV only")
        print("  2. JSON only")
        print("  3. Both CSV and JSON")
        
        while True:
            choice = input("\nChoose output format (1-3) [default: 1]: ").strip()
            if not choice:
                return 'csv'
            elif choice == '1':
                return 'csv'
            elif choice == '2':
                return 'json'
            elif choice == '3':
                return 'both'
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
    
    def get_analysis_preference(self) -> bool:
        """Ask user if they want to analyze the data"""
        print("\n🔬 Data Analysis Options:")
        print("-" * 25)
        print("  Perform energy consumption analysis?")
        print("  - Convert cumulative to hourly consumption")
        print("  - Generate statistical reports")
        print("  - Create visualization plots")
        print("  - Export analyzed data to CSV")
        
        while True:
            choice = input("\nPerform analysis? (y/N): ").strip().lower()
            if choice in ['y', 'yes']:
                return True
            elif choice in ['n', 'no', '']:
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    
    def analyze_data(self, csv_file: str, output_filename: str) -> bool:
        """
        Analyze the pulled data using the energy data analyzer.
        
        Args:
            csv_file: Path to the CSV file with raw HA data
            output_filename: Base filename for analysis outputs
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"\n🔬 Starting data analysis...")
            print(f"📁 Analyzing data from: {csv_file}")
            
            # Initialize analyzer with sensor names file
            analyzer = EnergyDataAnalyzer(csv_file, self.csv_file)
            
            # Load data
            if not analyzer.load_data():
                print("❌ Failed to load data for analysis!")
                return False
            
            print("🔄 Processing consumption data...")
            
            # Analyze all sensors
            hourly_data = analyzer.analyze_all_sensors()
            
            if not hourly_data:
                print("❌ No hourly consumption data generated!")
                return False
            
            # Save hourly analysis to CSV
            analysis_csv = os.path.join(self.base_dir, 'output', f"{output_filename}_analysis.csv")
            if analyzer.save_hourly_data(analysis_csv):
                print(f"✅ Analysis data saved to: {analysis_csv}")
            
            # Generate plots
            print("📊 Creating visualization plots...")
            plots_dir = os.path.join(self.base_dir, 'output', f"{output_filename}_plots")
            if analyzer.create_consumption_plots(plots_dir):
                print(f"✅ Plots saved to: {plots_dir}/")
            
            # Generate summary report
            print("📋 Generating summary report...")
            report = analyzer.generate_summary_report()
            report_file = os.path.join(self.base_dir, 'output', f"{output_filename}_report.txt")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"✅ Summary report saved to: {report_file}")
            
            # Show key statistics
            print("\n" + "=" * 50)
            print("📊 KEY ANALYSIS RESULTS")
            print("=" * 50)
            
            total_sensors = len(hourly_data)
            total_hours = sum(len(df) for df in hourly_data.values())
            
            print(f"🏷️ Sensors analyzed: {total_sensors}")
            print(f"⏰ Total hourly records: {total_hours}")
            
            # Calculate total consumption across all sensors
            total_consumption = 0
            for sensor_id, df in hourly_data.items():
                sensor_total = df['hourly_consumption'].sum()
                total_consumption += sensor_total
                print(f"   📊 {sensor_id}: {sensor_total:.3f} kWh")
            
            print(f"\n💡 TOTAL CONSUMPTION: {total_consumption:.3f} kWh")
            print("=" * 50)
            
            return True
            
        except Exception as e:
            print(f"❌ Error during analysis: {e}")
            return False
    
    def generate_output_filename(self, start_date: datetime, end_date: datetime) -> str:
        """Generate output filename based on date range with current timestamp"""
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')
        # Include full date and time for better file identification
        current_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if start_str == end_str:
            return f"ha_history_{start_str}_{current_timestamp}"
        else:
            return f"ha_history_{start_str}_to_{end_str}_{current_timestamp}"
    
    def confirm_operation(self, start_date: datetime, end_date: datetime, 
                         output_format: str, output_filename: str, analyze: bool = False) -> bool:
        """Ask user to confirm the operation"""
        print("\n📋 Operation Summary:")
        print("-" * 30)
        print(f"🔗 HA URL: {self.ha_url}")
        print(f"📄 CSV File: {self.csv_file}")
        print(f"📅 Start Date: {start_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 End Date: {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Duration: {end_date - start_date}")
        print(f"🔧 HA Sensor Offset: -2 hours (corrects for midnight reset)")
        print(f"💾 Output Format: {output_format.upper()}")
        print(f"📁 Output File: {output_filename}")
        print(f"🔬 Analysis: {'YES' if analyze else 'NO'}")
        
        if analyze:
            print("\n📊 Analysis will include:")
            print("   - Hourly consumption conversion")
            print("   - Statistical reports")
            print("   - Visualization plots")
            print(f"   - Analysis CSV: {output_filename}_analysis.csv")
            print(f"   - Summary report: {output_filename}_report.txt")
            print(f"   - Plots directory: {output_filename}_plots/")
        
        while True:
            confirm = input("\n✅ Proceed with data retrieval? (y/N/1/0): ").strip().lower()
            if confirm in ['y', 'yes', '1']:
                return True
            elif confirm in ['n', 'no', '', '0']:
                return False
            else:
                print("Please enter 'y'/'1' for yes or 'n'/'0' for no.")
    
    def analyze_ha_data_internal(self, ha_raw_data, output_filename: str, original_start_date = None, original_end_date = None, apply_ha_offset: bool = True):
        """
        Internal method to analyze HA data and return processed DataFrame
        
        Args:
            ha_raw_data: Raw HA API data
            output_filename: Base filename for temporary files
            original_start_date: Original requested start date (before offset correction)
            original_end_date: Original requested end date
            
        Returns:
            pandas.DataFrame with analyzed HA data or None if failed
        """
        try:
            # Create temporary HA-only file for analysis
            ha_temp_filename = f"{output_filename}_ha_temp"
            ha_csv_file = os.path.join(self.base_dir, 'output', f"{ha_temp_filename}.csv")
            
            # Save HA data temporarily
            if self.save_to_csv(ha_raw_data, ha_csv_file):
                print(f"🔬 Analyzing HA data...")
                
                # Create analyzer instance
                analyzer = EnergyDataAnalyzer(ha_csv_file, self.csv_file)
                
                # Load the data first
                if not analyzer.load_data():
                    print("❌ Failed to load HA data for analysis")
                    return None
                
                # Get the analyzed data as DataFrame
                sensor_data = analyzer.analyze_all_sensors()
                
                # Combine all sensor DataFrames into one
                if sensor_data:
                    import pandas as pd
                    combined_df = pd.concat(sensor_data.values(), ignore_index=True)
                    
                    # Remove timezone info from timestamps (timezone corrections will be handled centrally)
                    if original_start_date is not None and 'datetime' in combined_df.columns:
                        print(f"🔧 Removing timezone offset from HA timestamps")
                        combined_df['datetime'] = pd.to_datetime(combined_df['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    print(f"✅ HA analysis completed: {len(combined_df)} hourly records")
                    
                    # Clean up temporary file
                    try:
                        os.remove(ha_csv_file)
                    except:
                        pass
                    
                    return combined_df
                else:
                    print("❌ No analyzed data returned")
                    return None
            else:
                print("❌ Could not create temporary HA file for analysis")
                return None
                
        except Exception as e:
            print(f"❌ HA analysis failed: {e}")
            return None
    
    def convert_emporia_to_hourly_format(self, emporia_data):
        """
        Convert Emporia data to match the analyzed HA data format
        
        Args:
            emporia_data: List of Emporia records in HA-compatible format
            
        Returns:
            pandas.DataFrame matching HA analyzed format
        """
        try:
            import pandas as pd
            from datetime import datetime
            
            hourly_records = []
            
            for record in emporia_data:
                # Emporia data is already hourly consumption, so we create cumulative
                # by summing previous hours (this is an approximation for display consistency)
                
                # Extract timestamp and convert to datetime object
                timestamp_str = record.get('last_changed', record.get('last_updated', ''))
                if timestamp_str:
                    # Parse timestamp (timezone corrections will be handled centrally)
                    timestamp = pd.to_datetime(timestamp_str)
                    
                    # Extract sensor name from attributes or use entity_id as fallback
                    entity_id = record.get('entity_id', '')
                    sensor_name = ''
                    
                    # Try to get friendly name from attributes
                    attributes_str = record.get('attributes', '{}')
                    try:
                        import json
                        attributes = json.loads(attributes_str)
                        sensor_name = attributes.get('friendly_name', '')
                    except:
                        pass
                    
                    # If no sensor name found, use entity_id or sensor_names mapping
                    if not sensor_name:
                        sensor_mapping = self.sensor_names.get(entity_id, {})
                        sensor_name = sensor_mapping.get('name', entity_id.replace('sensor.', '').replace('_', ' ')) if isinstance(sensor_mapping, dict) else sensor_mapping
                    
                    # Create record matching HA analyzed format
                    hourly_record = {
                        'datetime': timestamp.strftime('%Y-%m-%d %H:%M:%S'),  # Remove timezone offset for consistency
                        'entity_id': entity_id,
                        'sensor_name': sensor_name,
                        'cumulative_consumption': float(record.get('state', 0)),  # Emporia gives hourly, treat as cumulative
                        'hourly_consumption': float(record.get('state', 0)),  # Same value for Emporia
                        'data_method': 'emporia_direct'  # Mark as direct from Emporia
                    }
                    hourly_records.append(hourly_record)
            
            if hourly_records:
                df = pd.DataFrame(hourly_records)
                return df
            else:
                return None
                
        except Exception as e:
            print(f"❌ Emporia conversion failed: {e}")
            return None
    
    def apply_upstream_device_adjustments(self, combined_df):
        """
        Subtract HA device consumption from their upstream Emporia devices
        
        Args:
            combined_df: Combined DataFrame with HA and Emporia data
            
        Returns:
            DataFrame with upstream device adjustments applied
        """
        try:
            import pandas as pd
            
            # Load sensor mappings to get upstream device information
            if not hasattr(self, 'sensor_names') or not self.sensor_names:
                return combined_df
            
            print("🔧 Applying upstream device adjustments...")
            
            # Create a copy to avoid modifying the original
            adjusted_df = combined_df.copy()
            
            # Get unique timestamps
            timestamps = sorted(adjusted_df['datetime'].unique())
            adjustments_made = 0
            
            for timestamp in timestamps:
                hour_data = adjusted_df[adjusted_df['datetime'] == timestamp]
                
                # Process each HA sensor that has an upstream device
                for entity_id, mapping in self.sensor_names.items():
                    if isinstance(mapping, dict) and 'upstream_sensor' in mapping:
                        upstream_device = mapping['upstream_sensor']
                        
                        # Skip if no upstream device or upstream device is 'none'
                        if not upstream_device or upstream_device.lower() == 'none':
                            continue
                        
                        # Find the HA device consumption for this hour
                        ha_device_data = hour_data[
                            (hour_data['entity_id'] == entity_id) & 
                            (hour_data['data_source'] == 'Home Assistant')
                        ]
                        
                        if ha_device_data.empty:
                            continue
                        
                        ha_consumption = ha_device_data['hourly_consumption'].iloc[0]
                        
                        # Find the corresponding Emporia upstream device by friendly name
                        upstream_device_data = hour_data[
                            (hour_data['sensor_name'] == upstream_device) & 
                            (hour_data['data_source'] == 'Emporia')
                        ]
                        
                        if upstream_device_data.empty:
                            continue
                        
                        # Subtract HA device consumption from upstream Emporia device
                        upstream_index = upstream_device_data.index[0]
                        original_consumption = adjusted_df.loc[upstream_index, 'hourly_consumption']
                        new_consumption = original_consumption - ha_consumption
                        
                        adjusted_df.loc[upstream_index, 'hourly_consumption'] = new_consumption
                        
                        # Also adjust cumulative consumption
                        adjusted_df.loc[upstream_index, 'cumulative_consumption'] = adjusted_df.loc[upstream_index, 'cumulative_consumption'] - ha_consumption
                        
                        # Mark as adjusted
                        current_method = adjusted_df.loc[upstream_index, 'data_method']
                        adjusted_df.loc[upstream_index, 'data_method'] = f"{current_method}_adjusted"
                        
                        adjustments_made += 1
                        
                        emporia_sensor_name = upstream_device_data['sensor_name'].iloc[0]
                        ha_sensor_name = mapping.get('name', entity_id)
                        print(f"   📉 {timestamp}: {emporia_sensor_name} -= {ha_consumption:.3f} kWh (from {ha_sensor_name})")
            
            if adjustments_made > 0:
                print(f"✅ Applied {adjustments_made} upstream device adjustments")
            else:
                print("ℹ️ No upstream device adjustments needed")
            
            return adjusted_df
            
        except Exception as e:
            print(f"❌ Upstream device adjustment failed: {e}")
            import traceback
            traceback.print_exc()
            return combined_df
    
    def add_consumption_analysis(self, combined_df):
        """
        Filter out unwanted sensors and add consumption analysis rows
        
        Args:
            combined_df: Combined DataFrame with HA and Emporia data
            
        Returns:
            DataFrame with filtered data and analysis rows added
        """
        try:
            import pandas as pd
            
            # Filter out unwanted sensors
            filtered_df = combined_df[
                ~combined_df['entity_id'].isin([
                    'sensor.emporia_emporia_grid_balance_today_s_consumption',
                    'sensor.emporia_emporia_total_usage_today_s_consumption'
                ])
            ].copy()
            
            print(f"🔧 Filtered out grid_balance and total_usage sensors")
            print(f"📊 Data after filtering: {len(filtered_df)} records")
            
            # Get unique timestamps for analysis
            timestamps = sorted(filtered_df['datetime'].unique())
            analysis_rows = []
            negative_untracked_hours = []
            
            for timestamp in timestamps:
                # Get data for this timestamp
                hour_data = filtered_df[filtered_df['datetime'] == timestamp]
                
                # Calculate total_consumption (main_panel + solar)
                main_panel = hour_data[hour_data['sensor_name'] == 'main_panel']['hourly_consumption'].sum()
                solar = hour_data[hour_data['sensor_name'] == 'solar']['hourly_consumption'].sum()
                total_consumption = main_panel + solar
                
                # Calculate total_individual_sensors (all sensors except main_panel and solar)
                individual_sensors = hour_data[
                    ~hour_data['sensor_name'].isin(['main_panel', 'solar'])
                ]['hourly_consumption'].sum()
                
                # Calculate untracked
                untracked = total_consumption - individual_sensors
                
                # Check for negative untracked values
                if untracked < 0:
                    negative_untracked_hours.append({
                        'timestamp': timestamp,
                        'untracked': untracked,
                        'total_consumption': total_consumption,
                        'individual_sensors': individual_sensors
                    })
                
                # Create analysis rows with all required columns
                base_row = {
                    'datetime': timestamp,
                    'cumulative_consumption': 0,
                    'hourly_consumption': 0,
                    'data_method': 'calculated',
                    'data_source': 'Analysis',
                    'source': 'analysis'
                }
                
                # Total consumption row
                total_row = base_row.copy()
                total_row.update({
                    'entity_id': 'analysis.total_consumption',
                    'sensor_name': 'total_consumption',
                    'cumulative_consumption': total_consumption,
                    'hourly_consumption': total_consumption
                })
                analysis_rows.append(total_row)
                
                # Total individual sensors row
                individual_row = base_row.copy()
                individual_row.update({
                    'entity_id': 'analysis.total_individual_sensors',
                    'sensor_name': 'total_individual_sensors',
                    'cumulative_consumption': individual_sensors,
                    'hourly_consumption': individual_sensors
                })
                analysis_rows.append(individual_row)
                
                # Untracked row
                untracked_row = base_row.copy()
                untracked_row.update({
                    'entity_id': 'analysis.untracked',
                    'sensor_name': 'untracked',
                    'cumulative_consumption': untracked,
                    'hourly_consumption': untracked
                })
                analysis_rows.append(untracked_row)
            
            # Add analysis rows to the DataFrame
            if analysis_rows:
                analysis_df = pd.DataFrame(analysis_rows)
                result_df = pd.concat([filtered_df, analysis_df], ignore_index=True)
                print(f"📊 Added {len(analysis_rows)} analysis records")
            else:
                result_df = filtered_df
            
            # Add row_type column to distinguish between total and individual sensors
            result_df['row_type'] = result_df['sensor_name'].apply(
                lambda x: 'Total' if x in ['main_panel', 'total_consumption', 'total_individual_sensors'] 
                else 'Individual'
            )
            
            # Add peak_hours column (True for 7:00 AM to 8:59 PM on weekdays, excluding US holidays)
            result_df['peak_hours'] = result_df['datetime'].apply(
                lambda x: self._is_peak_hour(x)
            )
            
            # Ensure source column exists for all rows
            if 'source' not in result_df.columns:
                result_df['source'] = result_df.apply(
                    lambda row: 'analysis' if row['sensor_name'] in ['total_consumption', 'total_individual_sensors', 'untracked']
                    else 'sensor', axis=1
                )
            
            # Report negative untracked hours
            if negative_untracked_hours:
                print(f"\n⚠️ Found {len(negative_untracked_hours)} hours with negative untracked consumption:")
                for hour in negative_untracked_hours:
                    print(f"   {hour['timestamp']}: untracked={hour['untracked']:.4f} kWh")
                    print(f"      (total={hour['total_consumption']:.4f}, individual={hour['individual_sensors']:.4f})")
                print("   This may indicate a time offset issue between data sources.")
            else:
                print(f"✅ No negative untracked consumption detected")
            
            return result_df
            
        except Exception as e:
            print(f"❌ Error during analysis: {e}")
            import traceback
            print(f"📊 Error details:")
            traceback.print_exc()
            return combined_df
    
    def _is_peak_hour(self, datetime_str):
        """
        Determine if a given datetime string represents a peak hour (7:00 AM to 8:59 PM)
        Excludes weekends and US holidays
        
        Args:
            datetime_str: Datetime string in format 'YYYY-MM-DD HH:MM:SS'
            
        Returns:
            bool: True if between 07:00 and 20:59 on weekdays (non-holidays), False otherwise
        """
        try:
            from datetime import datetime
            
            # Parse the datetime string
            dt = datetime.strptime(str(datetime_str), '%Y-%m-%d %H:%M:%S')
            
            # Check if it's a weekend (Saturday = 5, Sunday = 6)
            if dt.weekday() >= 5:  # Saturday or Sunday
                return False
            
            # Check if it's a US holiday
            if HOLIDAYS_AVAILABLE and holidays:
                try:
                    us_holidays = holidays.country_holidays('US', years=dt.year)
                    if dt.date() in us_holidays:
                        return False
                except Exception as e:
                    # Handle other potential errors with holidays library
                    print(f"⚠️ Error using holidays library ({e}), using weekday-only peak detection")
            elif not HOLIDAYS_AVAILABLE:
                # Only show this warning once per session
                if not hasattr(self, '_holidays_warning_shown'):
                    print("⚠️ holidays library not available, using weekday-only peak detection")
                    self._holidays_warning_shown = True
            
            hour = dt.hour
            # Peak hours: 7:00 AM (07:00) to 8:59 PM (20:59) on weekdays only
            return 7 <= hour <= 20
        except Exception:
            # If parsing fails, assume non-peak for safety
            return False
    
    def save_hourly_data_to_csv(self, hourly_df, output_file: str) -> bool:
        """
        Save hourly DataFrame to CSV file
        
        Args:
            hourly_df: pandas DataFrame with hourly consumption data
            output_file: Path to output CSV file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if hourly_df is not None and not hourly_df.empty:
                # Create a copy to avoid modifying the original
                df_copy = hourly_df.copy()
                
                # Convert ALL potentially categorical columns to string
                # This is more robust than trying to detect categorical types
                for col in df_copy.columns:
                    if col not in ['cumulative_consumption', 'hourly_consumption']:  # Skip numeric columns
                        df_copy[col] = df_copy[col].astype(str)
                
                # Sort by datetime first, then by sensor name (or entity_id if no sensor_name)
                sort_columns = ['datetime']
                if 'sensor_name' in df_copy.columns:
                    sort_columns.append('sensor_name')
                else:
                    sort_columns.append('entity_id')
                
                sorted_df = df_copy.sort_values(sort_columns)
                sorted_df.to_csv(output_file, index=False)
                print(f"💾 Saved {len(sorted_df)} hourly records to {output_file}")
                return True
            else:
                print("⚠️ No hourly data to save")
                return False
                
        except Exception as e:
            print(f"❌ Error saving hourly data to CSV: {e}")
            return False
    
    def save_hourly_data_to_json(self, hourly_df, output_file: str) -> bool:
        """
        Save hourly DataFrame to JSON file
        
        Args:
            hourly_df: pandas DataFrame with hourly consumption data
            output_file: Path to output JSON file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if hourly_df is not None and not hourly_df.empty:
                # Create a copy to avoid modifying the original
                df_copy = hourly_df.copy()
                
                # Convert ALL potentially categorical columns to string
                # This is more robust than trying to detect categorical types
                for col in df_copy.columns:
                    if col not in ['cumulative_consumption', 'hourly_consumption']:  # Skip numeric columns
                        df_copy[col] = df_copy[col].astype(str)
                
                # Sort by datetime first, then by sensor name (or entity_id if no sensor_name)
                sort_columns = ['datetime']
                if 'sensor_name' in df_copy.columns:
                    sort_columns.append('sensor_name')
                else:
                    sort_columns.append('entity_id')
                
                sorted_df = df_copy.sort_values(sort_columns)
                
                # Convert sorted DataFrame to JSON
                sorted_df.to_json(output_file, orient='records', date_format='iso', indent=2)
                print(f"💾 Saved {len(sorted_df)} hourly records to {output_file}")
                return True
            else:
                print("⚠️ No hourly data to save")
                return False
                
        except Exception as e:
            print(f"❌ Error saving hourly data to JSON: {e}")
            return False

    def pull_data(self, start_date: datetime, end_date: datetime, 
                  output_format: str, output_filename: str, analyze: bool = False, data_sources: str = 'both', apply_ha_offset: bool = True, ha_pull_offset_only: bool = False, is_incremental: bool = False):
        """Pull data from selected sources
        
        Args:
            apply_ha_offset: If True, applies both pull offset and timestamp adjustment
            ha_pull_offset_only: If True, only applies pull offset (no timestamp adjustment)
            is_incremental: If True, merge with existing data instead of overwriting
        """
        print(f"\n🔄 Starting data retrieval...")
        print(f"📊 Data sources: {data_sources}")
        print(f"⏰ This may take a few moments for large date ranges...")
        
        ha_analyzed_df = None  # Will hold analyzed HA data as DataFrame
        print(f"\n🔄 Starting data pull operation...")
        print(f"📊 Data sources requested: {data_sources}")
        print(f"📅 Date range: {start_date} to {end_date}")
        print(f"🔄 Incremental mode: {is_incremental}")
        
        emporia_hourly_df = None  # Will hold Emporia data in matching format
        ha_raw_data = None  # Keep raw HA data for analysis
        
        # Pull Home Assistant data
        if data_sources in ['ha_only', 'both']:
            print(f"\n🏠 === STARTING HOME ASSISTANT DATA PULL ===")
            if not self.puller:
                print("❌ HA puller not initialized!")
                return {'data_pull': False, 'analysis': None}
            
            print(f"🏠 Pulling Home Assistant data...")
            
            # Get sensor list
            print(f"📋 Loading sensor list from: {self.csv_file}")
            sensors = self.puller.get_sensor_list_from_csv(self.csv_file)
            if not sensors:
                print("❌ No HA sensors found in CSV file!")
                if data_sources == 'ha_only':
                    return {'data_pull': False, 'analysis': None}
            else:
                print(f"✅ Found {len(sensors)} HA sensors")
                # Adjust datetime for HA API request (timezone + DST + sensor reset)
                adjusted_start = self.adjust_datetime_for_service_request(start_date, 'ha', is_end_date=False)
                adjusted_end = self.adjust_datetime_for_service_request(end_date, 'ha', is_end_date=True)
                
                # Fetch HA history data
                ha_raw_data = self.puller.get_history_data(
                    sensors,
                    adjusted_start.isoformat(),
                    adjusted_end.isoformat()
                )
                
                if ha_raw_data:
                    ha_record_count = sum(len(entity_data) for entity_data in ha_raw_data)
                    print(f"✅ Retrieved {ha_record_count} HA records")
                    
                    # Correct HA timestamps for timezone/DST and sensor reset behavior
                    ha_raw_data = self.correct_service_data_timestamps(ha_raw_data, 'ha')
                    
                    # Save raw HA data to archive
                    archive_dir = os.path.join(self.base_dir, 'archive')
                    os.makedirs(archive_dir, exist_ok=True)
                    ha_raw_csv_file = os.path.join(archive_dir, f"{output_filename}_ha_raw.csv")
                    ha_raw_json_file = os.path.join(archive_dir, f"{output_filename}_ha_raw.json")
                    
                    if self.save_to_csv(ha_raw_data, ha_raw_csv_file):
                        print(f"💾 Saved raw HA data to: {ha_raw_csv_file}")
                    if self.save_to_json(ha_raw_data, ha_raw_json_file):
                        print(f"💾 Saved raw HA data to: {ha_raw_json_file}")
                    
                    # Also save to output folder without timestamps for easy access
                    output_dir = os.path.join(self.base_dir, 'output')
                    os.makedirs(output_dir, exist_ok=True)
                    ha_raw_csv_current = os.path.join(output_dir, "ha_raw_current.csv")
                    ha_raw_json_current = os.path.join(output_dir, "ha_raw_current.json")
                    
                    if self.save_to_csv(ha_raw_data, ha_raw_csv_current):
                        print(f"💾 Saved current HA raw data to: {ha_raw_csv_current}")
                    if self.save_to_json(ha_raw_data, ha_raw_json_current):
                        print(f"💾 Saved current HA raw data to: {ha_raw_json_current}")
                    
                    # Analyze HA data if requested
                    if analyze:
                        # Timezone corrections are now handled centrally, no additional adjustments needed
                        ha_analyzed_df = self.analyze_ha_data_internal(ha_raw_data, output_filename, start_date, end_date, False)
                        if ha_analyzed_df is None:
                            print("❌ HA analysis failed!")
                            if data_sources == 'ha_only':
                                return {'data_pull': False, 'analysis': False}
                else:
                    print("❌ Failed to retrieve HA history data!")
                    if data_sources == 'ha_only':
                        return {'data_pull': False, 'analysis': None}
        
        # Pull Emporia data
        print(f"\n🔌 === STARTING EMPORIA VUE DATA PULL ===")
        if data_sources in ['emporia_only', 'both']:
            print(f"🔌 Checking Emporia availability...")
            print(f"   emporia_available: {self.emporia_available}")
            print(f"   emporia_puller: {self.emporia_puller is not None}")
            
            if not self.emporia_available or not self.emporia_puller:
                print("⚠️ Emporia not available but requested - continuing with HA data only")
                if data_sources == 'emporia_only':
                    return {'data_pull': False, 'analysis': None}
                # For 'both', continue with HA data only
            else:
                print(f"🔌 Pulling Emporia Vue data...")
                
                # Adjust datetime for Emporia API request (timezone + DST)
                adjusted_start = self.adjust_datetime_for_service_request(start_date, 'emporia', is_end_date=False)
                adjusted_end = self.adjust_datetime_for_service_request(end_date, 'emporia', is_end_date=False)
                
                # Add timeout and chunking protection for Emporia requests
                emporia_history_data = self.fetch_emporia_data_with_protection(adjusted_start, adjusted_end)
                
                if emporia_history_data:
                    print(f"✅ Retrieved {len(emporia_history_data)} Emporia records")
                    
                    # Correct Emporia timestamps for timezone/DST differences
                    emporia_history_data = self.correct_service_data_timestamps(emporia_history_data, 'emporia')
                    
                    # Save raw Emporia data to archive
                    archive_dir = os.path.join(self.base_dir, 'archive')
                    os.makedirs(archive_dir, exist_ok=True)
                    emporia_raw_csv_file = os.path.join(archive_dir, f"{output_filename}_emporia_raw.csv")
                    emporia_raw_json_file = os.path.join(archive_dir, f"{output_filename}_emporia_raw.json")
                    
                    # Convert Emporia data to CSV format
                    try:
                        import pandas as pd
                        emporia_df = pd.DataFrame(emporia_history_data)
                        emporia_df.to_csv(emporia_raw_csv_file, index=False)
                        print(f"💾 Saved raw Emporia data to: {emporia_raw_csv_file}")
                    except Exception as e:
                        print(f"❌ Error saving Emporia CSV: {e}")
                    
                    # Save Emporia data as JSON
                    try:
                        import json
                        with open(emporia_raw_json_file, 'w') as f:
                            json.dump(emporia_history_data, f, indent=2, default=str)
                        print(f"💾 Saved raw Emporia data to: {emporia_raw_json_file}")
                    except Exception as e:
                        print(f"❌ Error saving Emporia JSON: {e}")
                    
                    # Also save to output folder without timestamps for easy access
                    output_dir = os.path.join(self.base_dir, 'output')
                    os.makedirs(output_dir, exist_ok=True)
                    emporia_raw_csv_current = os.path.join(output_dir, "emporia_raw_current.csv")
                    emporia_raw_json_current = os.path.join(output_dir, "emporia_raw_current.json")
                    
                    try:
                        import pandas as pd
                        emporia_df = pd.DataFrame(emporia_history_data)
                        emporia_df.to_csv(emporia_raw_csv_current, index=False)
                        print(f"💾 Saved current Emporia raw data to: {emporia_raw_csv_current}")
                    except Exception as e:
                        print(f"❌ Error saving current Emporia CSV: {e}")
                    
                    try:
                        import json
                        with open(emporia_raw_json_current, 'w') as f:
                            json.dump(emporia_history_data, f, indent=2, default=str)
                        print(f"💾 Saved current Emporia raw data to: {emporia_raw_json_current}")
                    except Exception as e:
                        print(f"❌ Error saving current Emporia JSON: {e}")
                    
                    # Convert Emporia data to analyzed format to match HA
                    emporia_hourly_df = self.convert_emporia_to_hourly_format(emporia_history_data)
                    if emporia_hourly_df is not None:
                        print(f"🔄 Converted to {len(emporia_hourly_df)} Emporia hourly records")
                    else:
                        print("❌ Failed to convert Emporia data to hourly format!")
                        if data_sources == 'emporia_only':
                            return {'data_pull': False, 'analysis': None}
                else:
                    print("❌ Failed to retrieve Emporia history data!")
                    if data_sources == 'emporia_only':
                        return {'data_pull': False, 'analysis': None}
        
        # Check if we have any data
        if ha_analyzed_df is None and emporia_hourly_df is None:
            print("❌ No data retrieved from any source!")
            return {'data_pull': False, 'analysis': None}
        
        # Union analyzed HA and Emporia hourly data
        combined_df = None
        if ha_analyzed_df is not None and emporia_hourly_df is not None:
            import pandas as pd
            # Add data source column to distinguish between HA and Emporia data
            ha_analyzed_df = ha_analyzed_df.copy()
            emporia_hourly_df = emporia_hourly_df.copy()
            
            # Apply 2-hour offset to HA data for alignment (subtract 2 hours)
            print("🔧 Applying 2-hour offset to HA data for alignment")
            ha_analyzed_df['datetime'] = pd.to_datetime(ha_analyzed_df['datetime']) - pd.Timedelta(hours=2)
            ha_analyzed_df['datetime'] = ha_analyzed_df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            print(f"⏰ HA timestamps shifted back by 2 hours (e.g., 08:00 → 06:00)")
            
            ha_analyzed_df['data_source'] = 'Home Assistant'
            ha_analyzed_df['source'] = 'sensor'  # Mark as sensor data
            emporia_hourly_df['data_source'] = 'Emporia'
            emporia_hourly_df['source'] = 'sensor'  # Mark as sensor data
            combined_df = pd.concat([ha_analyzed_df, emporia_hourly_df], ignore_index=True)
            print(f"📊 Combined hourly data: {len(ha_analyzed_df)} HA + {len(emporia_hourly_df)} Emporia = {len(combined_df)} total")
        elif ha_analyzed_df is not None:
            import pandas as pd
            combined_df = ha_analyzed_df.copy()
            
            # Apply 2-hour offset to HA data for alignment (subtract 2 hours)
            print("🔧 Applying 2-hour offset to HA-only data for alignment")
            combined_df['datetime'] = pd.to_datetime(combined_df['datetime']) - pd.Timedelta(hours=2)
            combined_df['datetime'] = combined_df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            print(f"⏰ HA timestamps shifted back by 2 hours (e.g., 08:00 → 06:00)")
            
            combined_df['data_source'] = 'Home Assistant'
            combined_df['source'] = 'sensor'  # Mark as sensor data
            print(f"📊 HA-only hourly data: {len(combined_df)} records")
        elif emporia_hourly_df is not None:
            combined_df = emporia_hourly_df.copy()
            combined_df['data_source'] = 'Emporia'
            combined_df['source'] = 'sensor'  # Mark as sensor data
            print(f"📊 Emporia-only hourly data: {len(combined_df)} records")
        
        # Apply upstream device adjustments and add consumption analysis
        if combined_df is not None:
            combined_df = self.apply_upstream_device_adjustments(combined_df)
            combined_df = self.add_consumption_analysis(combined_df)
        
        # Save combined data
        success = False
        saved_csv_file = None
        
        if output_format in ['csv', 'both']:
            # Save archived version with timestamp
            archive_dir = os.path.join(self.base_dir, 'archive')
            os.makedirs(archive_dir, exist_ok=True)
            archive_csv_file = os.path.join(archive_dir, f"{output_filename}.csv")
            
            if is_incremental:
                # For incremental updates, merge with existing data
                if self.merge_with_existing_analysis(combined_df, output_filename):
                    success = True
                    print(f"✅ Incremental data merged successfully")
            else:
                # For regular pulls, save both archived and latest
                if self.save_hourly_data_to_csv(combined_df, archive_csv_file):
                    success = True
                    saved_csv_file = archive_csv_file
                    print(f"✅ Archived CSV data saved to: {archive_csv_file}")
                    
                    # Also save as latest version
                    latest_csv_file = os.path.join(self.base_dir, 'output', "energy_analysis.csv")
                    if self.save_hourly_data_to_csv(combined_df, latest_csv_file):
                        print(f"✅ Latest CSV data saved to: {latest_csv_file}")
        
        if output_format in ['json', 'both']:
            # Save archived version with timestamp
            archive_dir = os.path.join(self.base_dir, 'archive')
            os.makedirs(archive_dir, exist_ok=True)
            archive_json_file = os.path.join(archive_dir, f"{output_filename}.json")
            
            if not is_incremental:
                # For regular pulls, save both archived and latest JSON
                if self.save_hourly_data_to_json(combined_df, archive_json_file):
                    success = True
                    print(f"✅ Archived JSON data saved to: {archive_json_file}")
                    
                    # Also save as latest version
                    latest_json_file = os.path.join(self.base_dir, 'output', "energy_analysis.json")
                    if self.save_hourly_data_to_json(combined_df, latest_json_file):
                        print(f"✅ Latest JSON data saved to: {latest_json_file}")
            else:
                # For incremental, JSON merging is handled separately (CSV is primary)
                if self.save_hourly_data_to_json(combined_df, archive_json_file):
                    print(f"✅ Archived incremental JSON data saved to: {archive_json_file}")
        
        # Analysis was already done on HA data during processing
        analysis_result = True if analyze and ha_analyzed_df is not None else None
        if analyze and ha_analyzed_df is None and emporia_hourly_df is not None:
            print(f"ℹ️ Analysis not performed - Emporia data is already in hourly format")
            analysis_result = False
        
        return {'data_pull': success, 'analysis': analysis_result}
    
    def run(self):
        """Main application loop"""
        self.print_header()
        
        # Initialize connection
        if not self.initialize_puller():
            input("\nPress Enter to exit...")
            return 1
        
        while True:
            self.display_date_options()
            
            try:
                choice = input("\n🎯 Select an option (0-9): ").strip()
                
                if choice == '0':
                    print("\n👋 Goodbye!")
                    return 0
                
                elif choice in ['1', '2', '3', '4', '5', '6', '7']:
                    # Predefined date range
                    options = self.get_date_range_options()
                    selected = options[choice]
                    start_date = selected['start']
                    end_date = selected['end']
                    
                    print(f"\n📅 Selected: {selected['name']}")
                    
                elif choice == '8':
                    # Custom date range
                    date_range = self.get_custom_date_range()
                    if not date_range:
                        continue
                    start_date, end_date = date_range
                
                elif choice == '9':
                    # Incremental update - calculate dates and treat like custom range
                    latest_timestamp = self.get_latest_timestamp_from_analysis()
                    if latest_timestamp is None:
                        print(f"📄 No existing data found. Please run a full data pull first.")
                        print(f"💡 Tip: Use a regular date range option (1-8) for your first data pull")
                        continue
                    
                    # Adjust timestamp backwards by 6 hours for overlap buffer
                    start_date = latest_timestamp - timedelta(hours=6)
                    end_date = datetime.now()
                    
                    print(f"\n📅 Incremental update range:")
                    print(f"   Latest data: {latest_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   Start (6hr overlap): {start_date.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   End: {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
                
                else:
                    print("❌ Invalid choice. Please select 0-9.")
                    continue
                
                # Use default settings (no prompts)
                data_sources = 'both'  # Always pull from both HA and Emporia
                output_format = 'both'  # Always output both CSV and JSON
                analyze = True  # Always perform analysis
                is_incremental = (choice == '9')  # Track if this is an incremental update
                
                # Generate output filename
                if is_incremental:
                    output_filename = f"incremental_update_{start_date.strftime('%Y%m%d_%H%M%S')}_to_{end_date.strftime('%Y%m%d_%H%M%S')}"
                else:
                    output_filename = self.generate_output_filename(start_date, end_date)
                
                print(f"\n🔄 Starting data retrieval...")
                print(f"📊 Data sources: Both (HA + Emporia)")
                print(f"💾 Output formats: Both (CSV + JSON)")
                print(f"🔬 Analysis: Enabled")
                if is_incremental:
                    print(f"� Mode: Incremental update (will merge with existing data)")
                print(f"�📁 Output filename: {output_filename}")
                
                # Pull the data
                result = self.pull_data(start_date, end_date, output_format, output_filename, analyze, data_sources, True, False, is_incremental)
                
                # Handle results and exit
                if isinstance(result, dict):
                    # New detailed result format
                    if result['data_pull']:
                        print(f"\n🎉 Data retrieval completed successfully!")
                        if result['analysis'] is True:
                            print(f"🔬 Energy analysis completed successfully!")
                        elif result['analysis'] is False:
                            print(f"⚠️ Energy analysis failed, but raw data is available.")
                    else:
                        print(f"\n❌ Data retrieval failed!")
                else:
                    # Legacy boolean result (backward compatibility)
                    if result:
                        print(f"\n🎉 Data retrieval completed successfully!")
                    else:
                        print(f"\n❌ Data retrieval failed!")
                
                # Exit after completion (no more prompts)
                print(f"\n👋 Data pull complete. Goodbye!")
                return 0
            
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                return 0
            except Exception as e:
                print(f"\n❌ An error occurred: {e}")
                continue


def main():
    """Entry point for the application"""
    app = HAHistoryMain()
    return app.run()


if __name__ == '__main__':
    sys.exit(main())