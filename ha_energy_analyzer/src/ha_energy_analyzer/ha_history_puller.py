#!/usr/bin/env python3
"""
Home Assistant History Data Puller

This script pulls historical data from Home Assistant for sensors listed in a CSV file.
It allows you to specify start and end dates for the data retrieval.

Requirements:
- Home Assistant instance accessible via API
- Long-lived access token for authentication
- CSV file with sensor entity_ids

Author: AI Assistant
Date: 2025-10-15
"""

import csv
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse
import os
from urllib.parse import urljoin

# Try to import the database puller
try:
    from .ha_database_puller import create_database_puller
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    create_database_puller = None
    print("ℹ️ Database puller not available - using API-only mode")


class HomeAssistantHistoryPuller:
    """Class to handle Home Assistant history data retrieval."""
    
    def __init__(self, ha_url: str, token: str, statistics_threshold_days: int = 10, enable_database_access: bool = True):
        """
        Initialize the Home Assistant connection with API-first approach.
        
        Args:
            ha_url: URL of your Home Assistant instance (e.g., 'http://homeassistant.local:8123')
            token: Long-lived access token for API authentication
            statistics_threshold_days: Days threshold for switching to long-term statistics API (default: 10)
                                     Data typically moves to long-term storage after 9-10 days
            enable_database_access: If True, will use database only for data older than 10 days (API-first for accuracy)
        """
        self.ha_url = ha_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        self.statistics_threshold_days = statistics_threshold_days
        self.enable_database_access = enable_database_access
        self.database_puller = None
        
        # Try to initialize database access if enabled
        if self.enable_database_access:
            self._try_initialize_database()
    
    def _try_initialize_database(self):
        """Try to initialize direct database access."""
        if not DATABASE_AVAILABLE or not create_database_puller:
            print("ℹ️ Database access not available - using API-only mode")
            return
        
        try:
            self.database_puller = create_database_puller()
            if self.database_puller:
                print("✅ Database access initialized successfully")
            else:
                print("⚠️ Database access failed - falling back to API-only mode")
        except Exception as e:
            print(f"⚠️ Database initialization error: {e} - using API-only mode")
            self.database_puller = None
    
    def _get_database_history(self, entity_ids: List[str], start_dt: datetime, end_dt: datetime) -> Optional[List[List[Dict]]]:
        """
        Get history data using direct database access.
        
        Args:
            entity_ids: List of entity IDs
            start_dt: Start datetime
            end_dt: End datetime
            
        Returns:
            History data in API format or None if failed
        """
        if not self.database_puller:
            return None
        
        try:
            # Try statistics first (more efficient for energy sensors)
            duration = end_dt - start_dt
            
            if duration.days >= 1:
                # For longer periods, try hourly statistics
                print("📊 Trying database hourly statistics...")
                stats_data = self.database_puller.get_entity_statistics(
                    entity_ids, start_dt, end_dt, use_short_term=True
                )
                
                if stats_data:
                    converted_data = self.database_puller.convert_to_history_format(stats_data, 'statistics')
                    if converted_data:
                        print(f"✅ Database statistics successful: {sum(len(e) for e in converted_data)} records")
                        return converted_data
            
            # Fall back to raw states if statistics not available
            print("📊 Trying database raw states...")
            states_data = self.database_puller.get_entity_states(entity_ids, start_dt, end_dt)
            
            if states_data:
                converted_data = self.database_puller.convert_to_history_format(states_data, 'states')
                if converted_data:
                    print(f"✅ Database states successful: {sum(len(e) for e in converted_data)} records")
                    return converted_data
            
            return None
            
        except Exception as e:
            print(f"❌ Database history error: {e}")
            return None
        
    def test_connection(self) -> bool:
        """
        Test the connection to Home Assistant API.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        # Fix URL joining for supervisor endpoints
        if '/core' in self.ha_url:
            test_url = f"{self.ha_url}/api/"
        else:
            test_url = urljoin(self.ha_url, '/api/')
            
        try:
            print(f"🔍 Testing connection to: {test_url}")
            print(f"🔑 Using token: {self.headers['Authorization'][:20]}...")
            
            response = requests.get(
                test_url,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            print("✅ Successfully connected to Home Assistant API")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to Home Assistant API: {e}")
            print(f"🔍 Full URL attempted: {test_url}")
            return False
    
    def get_sensor_list_from_csv(self, csv_file: str) -> List[str]:
        """
        Extract unique sensor entity IDs from CSV file.
        
        Args:
            csv_file: Path to CSV file containing sensor data
            
        Returns:
            List of unique sensor entity IDs
        """
        sensors = set()
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'entity_id' in row:
                        sensors.add(row['entity_id'])
            
            sensor_list = list(sensors)
            print(f"📋 Found {len(sensor_list)} unique sensors in CSV file:")
            for sensor in sensor_list:
                print(f"   - {sensor}")
                
            return sensor_list
            
        except FileNotFoundError:
            print(f"❌ CSV file not found: {csv_file}")
            return []
        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
            return []
    
    def get_history_data(self, entity_ids: List[str], start_time: str, end_time: str) -> List[List[Dict]]:
        """
        Retrieve history data from Home Assistant using API-first approach for accuracy.
        
        Strategy (prioritizes data accuracy):
        - Regular history API: For recent data (< 10 days) 
        - Long-term statistics API: For older data (>= 10 days)
        - Database access: Only for very old data (> 10 days old) as fallback/supplement
        - Hybrid approach: Combines API (recent) + database (old) when needed
        
        Args:
            entity_ids: List of entity IDs to retrieve data for
            start_time: Start time in ISO format (e.g., '2025-10-15T00:00:00')
            end_time: End time in ISO format (e.g., '2025-10-15T23:59:59')
            
        Returns:
            List containing the history data for each entity
        """
        # Calculate the time span to determine optimal API
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            duration = end_dt - start_dt
            days_span = duration.days
            
            print(f"🔄 Fetching history data from {start_time} to {end_time}")
            print(f"⏱️ Duration: {days_span} days, {duration.seconds // 3600} hours")
            
            # Check if we need hybrid approach (mix of database + API)
            days_from_now = (datetime.now() - start_dt).days
            api_cutoff_days = 10  # Use API for last 10 days, database only for older
            
            if days_from_now > api_cutoff_days and days_span > api_cutoff_days:
                # Use hybrid approach: database for old data, API for recent data
                print(f"🔄 Using Hybrid Approach: Database for data older than {api_cutoff_days} days, API for recent data")
                return self.get_hybrid_history_data(entity_ids, start_dt, end_dt, api_cutoff_days)
            
            # PRIORITY 1: Use API methods for recent data (last 10 days) - ensures accuracy
            elif days_span >= self.statistics_threshold_days:
                print(f"📊 Using Long-Term Statistics API (optimal for {days_span}+ day periods, threshold: {self.statistics_threshold_days} days)")
                return self.get_long_term_statistics(entity_ids, start_time, end_time)
            else:
                print(f"📊 Using Regular History API (optimal for {days_span} day periods, threshold: {self.statistics_threshold_days} days)")
                return self.get_regular_history(entity_ids, start_time, end_time)
                
        except Exception as e:
            print(f"⚠️ Error parsing dates, falling back to regular history API: {e}")
            return self.get_regular_history(entity_ids, start_time, end_time)
    
    def get_hybrid_history_data(self, entity_ids: List[str], start_dt: datetime, end_dt: datetime, api_cutoff_days: int) -> List[List[Dict]]:
        """
        Retrieve history data using a hybrid approach:
        - Database for data older than cutoff_days 
        - API for recent data (last cutoff_days)
        
        Args:
            entity_ids: List of entity IDs to retrieve data for
            start_dt: Start datetime
            end_dt: End datetime  
            api_cutoff_days: Days from now to use API (database used for older)
            
        Returns:
            Combined history data from both sources
        """
        print(f"🔄 Hybrid approach: API for last {api_cutoff_days} days, database for older data")
        
        # Calculate cutoff point
        now = datetime.now()
        api_cutoff_dt = now - timedelta(days=api_cutoff_days)
        
        all_data = []
        
        # Part 1: Get old data from database (if available and needed)
        if start_dt < api_cutoff_dt and self.database_puller:
            old_end_dt = min(api_cutoff_dt, end_dt)
            print(f"📊 Fetching old data from database: {start_dt.isoformat()} to {old_end_dt.isoformat()}")
            
            try:
                db_data = self._get_database_history(entity_ids, start_dt, old_end_dt)
                if db_data:
                    all_data.extend(db_data)
                    print(f"✅ Database portion: {sum(len(e) for e in db_data)} records")
                else:
                    print("⚠️ Database returned no data for old portion")
            except Exception as e:
                print(f"⚠️ Database error for old data: {e}")
        
        # Part 2: Get recent data from API  
        if end_dt > api_cutoff_dt:
            api_start_dt = max(api_cutoff_dt, start_dt)
            api_start_str = api_start_dt.isoformat()
            api_end_str = end_dt.isoformat()
            
            print(f"📊 Fetching recent data from API: {api_start_str} to {api_end_str}")
            
            # Determine which API to use for recent data
            recent_days = (end_dt - api_start_dt).days
            if recent_days >= self.statistics_threshold_days:
                api_data = self.get_long_term_statistics(entity_ids, api_start_str, api_end_str)
            else:
                api_data = self.get_regular_history(entity_ids, api_start_str, api_end_str)
            
            if api_data:
                all_data.extend(api_data)
                print(f"✅ API portion: {sum(len(e) for e in api_data)} records")
            else:
                print("⚠️ API returned no data for recent portion")
        
        if not all_data:
            print("❌ No data retrieved from either source")
            return []
        
        print(f"✅ Hybrid approach successful: {sum(len(e) for e in all_data)} total records")
        return all_data
    
    def get_regular_history(self, entity_ids: List[str], start_time: str, end_time: str) -> List[List[Dict]]:
        """
        Retrieve history data using the regular /api/history/period endpoint.
        Best for recent data (< 7 days) with high resolution.
        
        Args:
            entity_ids: List of entity IDs to retrieve data for  
            start_time: Start time in ISO format
            end_time: End time in ISO format
            
        Returns:
            Dictionary containing the history data response
        """
        # Construct the API URL
        if '/core' in self.ha_url:
            url = f"{self.ha_url}/api/history/period/{start_time}"
        else:
            url = urljoin(self.ha_url, '/api/history/period/' + start_time)
        
        # Parameters for the request
        params = {
            'filter_entity_id': ','.join(entity_ids),
            'end_time': end_time
        }
        
        print(f"📡 Regular History API URL: {url}")
        print(f"🎯 Entities: {', '.join(entity_ids)}")
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=60  # Increased timeout for larger requests
            )
            response.raise_for_status()
            
            data = response.json()
            print(f"✅ Successfully retrieved regular history data")
            
            # Count total data points
            total_points = sum(len(entity_data) for entity_data in data)
            print(f"� Total data points retrieved: {total_points}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching regular history data: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON response: {e}")
            return []
    
    def get_long_term_statistics(self, entity_ids: List[str], start_time: str, end_time: str) -> List[List[Dict]]:
        """
        Retrieve history data using the /api/history/statistics endpoint.
        Best for historical data (7+ days) with hourly aggregation.
        
        Args:
            entity_ids: List of entity IDs to retrieve data for
            start_time: Start time in ISO format  
            end_time: End time in ISO format
            
        Returns:
            Dictionary containing the history data response (converted to regular format)
        """
        # Try different possible statistics API endpoints
        statistics_endpoints = [
            '/api/history/statistics',
            '/api/statistics',
            '/api/history/statistics_during_period'
        ]
        
        for endpoint in statistics_endpoints:
            try:
                # Construct the statistics API URL
                if '/core' in self.ha_url:
                    url = f"{self.ha_url}{endpoint}"
                else:
                    url = urljoin(self.ha_url, endpoint)
                
                # Try different parameter formats
                params_variants = [
                    {
                        'statistic_ids': ','.join(entity_ids),
                        'start_time': start_time,
                        'end_time': end_time,
                        'period': 'hour'
                    },
                    {
                        'statistic_ids': entity_ids,  # As list instead of comma-separated
                        'start_time': start_time,
                        'end_time': end_time,
                        'period': 'hour'
                    },
                    {
                        'entity_ids': ','.join(entity_ids),  # Try entity_ids instead of statistic_ids
                        'start_time': start_time,
                        'end_time': end_time,
                        'period': 'hour'
                    }
                ]
                
                for i, params in enumerate(params_variants):
                    print(f"📡 Trying Statistics API: {url} (variant {i+1})")
                    print(f"🎯 Parameters: {params}")
                    
                    response = requests.get(
                        url,
                        headers=self.headers,
                        params=params,
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        statistics_data = response.json()
                        print(f"✅ Successfully retrieved long-term statistics from {endpoint}")
                        
                        # Convert statistics format to regular history format for compatibility
                        converted_data = self.convert_statistics_to_history_format(statistics_data)
                        
                        # Count total data points
                        total_points = sum(len(entity_data) for entity_data in converted_data)
                        print(f"📊 Total data points converted: {total_points}")
                        
                        return converted_data
                    else:
                        print(f"⚠️ {endpoint} variant {i+1} returned {response.status_code}: {response.reason}")
                        
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Error with {endpoint}: {e}")
                continue
        
        # If all statistics endpoints failed, fall back to regular history
        print(f"❌ All statistics API endpoints failed")
        print(f"🔄 Falling back to regular history API...")
        return self.get_regular_history(entity_ids, start_time, end_time)
    
    def convert_statistics_to_history_format(self, statistics_data: Dict) -> List[List[Dict]]:
        """
        Convert long-term statistics format to regular history format for compatibility.
        
        Args:
            statistics_data: Raw statistics response from HA API
            
        Returns:
            List in the same format as regular history API
        """
        try:
            converted_data = []
            
            # Process each entity's statistics
            for entity_id, stats_list in statistics_data.items():
                entity_records = []
                
                for stat_record in stats_list:
                    # Convert statistics record to history record format
                    history_record = {
                        'entity_id': entity_id,
                        'state': str(stat_record.get('state', stat_record.get('sum', 0))),  # Use 'sum' for energy sensors
                        'last_changed': stat_record.get('start', ''),
                        'last_updated': stat_record.get('start', ''),
                        'attributes': {
                            'unit_of_measurement': 'kWh',  # Default for energy sensors
                            'device_class': 'energy',
                            'state_class': 'total_increasing',
                            'source': 'long_term_statistics',
                            'original_statistic': stat_record  # Keep original for debugging
                        }
                    }
                    entity_records.append(history_record)
                
                if entity_records:
                    converted_data.append(entity_records)
                    print(f"📊 Converted {len(entity_records)} statistics records for {entity_id}")
            
            print(f"✅ Statistics conversion complete: {len(converted_data)} entities")
            return converted_data
            
        except Exception as e:
            print(f"❌ Error converting statistics to history format: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_statistics_metadata(self, entity_ids: List[str]) -> Dict:
        """
        Get metadata about available statistics for the given entities.
        Useful for understanding what statistics are available before requesting data.
        
        Args:
            entity_ids: List of entity IDs to check for statistics
            
        Returns:
            Dictionary containing available statistics metadata
        """
        # Construct the statistics metadata API URL
        if '/core' in self.ha_url:
            url = f"{self.ha_url}/api/history/statistics/metadata"
        else:
            url = urljoin(self.ha_url, '/api/history/statistics/metadata')
        
        # Parameters for the metadata request
        params = {
            'statistic_ids': ','.join(entity_ids)
        }
        
        print(f"🔍 Checking statistics metadata for entities...")
        print(f"📡 API URL: {url}")
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            metadata = response.json()
            print(f"✅ Retrieved statistics metadata for {len(metadata)} entities")
            
            # Log available statistics
            for entity_id, meta in metadata.items():
                print(f"📊 {entity_id}:")
                print(f"   - Unit: {meta.get('unit_of_measurement', 'unknown')}")
                print(f"   - Statistics ID: {meta.get('statistic_id', 'unknown')}")
                print(f"   - Source: {meta.get('source', 'unknown')}")
            
            return metadata
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching statistics metadata: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing metadata JSON response: {e}")
            return {}
    
    def discover_available_endpoints(self) -> Dict:
        """
        Discover what API endpoints are available on this Home Assistant instance.
        This can help debug API availability issues.
        
        Returns:
            Dictionary of endpoint availability
        """
        endpoints_to_check = [
            '/api/',
            '/api/history',
            '/api/history/statistics',
            '/api/statistics',
            '/api/history/statistics_during_period',
            '/api/states'
        ]
        
        results = {}
        
        for endpoint in endpoints_to_check:
            try:
                if '/core' in self.ha_url:
                    url = f"{self.ha_url}{endpoint}"
                else:
                    url = urljoin(self.ha_url, endpoint)
                
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=10
                )
                
                results[endpoint] = {
                    'status_code': response.status_code,
                    'available': response.status_code in [200, 400],  # 400 might mean endpoint exists but needs params
                    'reason': response.reason
                }
                
            except Exception as e:
                results[endpoint] = {
                    'status_code': None,
                    'available': False,
                    'error': str(e)
                }
        
        return results
    
    def save_to_csv(self, history_data: List[List[Dict]], output_file: str) -> bool:
        """
        Save history data to CSV file.
        
        Args:
            history_data: List of entity data lists from HA API
            output_file: Path to output CSV file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            all_records = []
            
            # Process each entity's data
            for entity_data in history_data:
                for record in entity_data:
                    # Clean up the record
                    clean_record = {
                        'entity_id': record.get('entity_id', ''),
                        'state': record.get('state', ''),
                        'last_changed': record.get('last_changed', ''),
                        'last_updated': record.get('last_updated', ''),
                        'attributes': json.dumps(record.get('attributes', {}))
                    }
                    all_records.append(clean_record)
            
            # Create DataFrame and save to CSV
            df = pd.DataFrame(all_records)
            
            if not df.empty:
                # Sort by entity_id and last_changed
                df = df.sort_values(['entity_id', 'last_changed'])
                df.to_csv(output_file, index=False)
                print(f"💾 Saved {len(df)} records to {output_file}")
                return True
            else:
                print("⚠️ No data to save")
                return False
                
        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")
            return False
    
    def save_to_json(self, history_data: List[List[Dict]], output_file: str) -> bool:
        """
        Save history data to JSON file.
        
        Args:
            history_data: List of entity data lists from HA API
            output_file: Path to output JSON file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            
            total_points = sum(len(entity_data) for entity_data in history_data)
            print(f"💾 Saved {total_points} records to {output_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving to JSON: {e}")
            return False


def parse_datetime(date_str: str) -> str:
    """
    Parse various date formats and return ISO format string.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        ISO format datetime string
    """
    formats = [
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%dT%H:%M'
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.isoformat()
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse date: {date_str}")


def main():
    """Main function to handle command line arguments and execute the script."""
    
    parser = argparse.ArgumentParser(
        description='Pull historical data from Home Assistant for sensors listed in CSV file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pull data for yesterday
  python ha_history_puller.py --csv ha_sensors.csv --start 2025-10-14 --end 2025-10-15
  
  # Pull data with specific times
  python ha_history_puller.py --csv ha_sensors.csv --start "2025-10-14 08:00:00" --end "2025-10-14 20:00:00"
  
  # Use environment variables for credentials
  export HA_URL="http://homeassistant.local:8123"
  export HA_TOKEN="your_long_lived_access_token"
  python ha_history_puller.py --csv history.csv --start 2025-10-14 --end 2025-10-15
        """
    )
    
    # Required arguments
    parser.add_argument('--csv', required=True, 
                       help='Path to CSV file containing sensor entity_ids')
    parser.add_argument('--start', required=True,
                       help='Start date/time (YYYY-MM-DD or "YYYY-MM-DD HH:MM:SS")')
    parser.add_argument('--end', required=True,
                       help='End date/time (YYYY-MM-DD or "YYYY-MM-DD HH:MM:SS")')
    
    # Optional arguments
    parser.add_argument('--ha-url', 
                       default=os.getenv('HA_URL', 'http://homeassistant.local:8123'),
                       help='Home Assistant URL (default: $HA_URL or http://homeassistant.local:8123)')
    parser.add_argument('--token',
                       default=os.getenv('HA_TOKEN'),
                       help='Home Assistant long-lived access token (default: $HA_TOKEN)')
    parser.add_argument('--output', default='ha_history_output',
                       help='Output file prefix (default: ha_history_output)')
    parser.add_argument('--format', choices=['csv', 'json', 'both'], default='csv',
                       help='Output format (default: csv)')
    
    args = parser.parse_args()
    
    # Validate token
    if not args.token:
        print("❌ Error: Home Assistant token is required!")
        print("   Set it via --token argument or HA_TOKEN environment variable")
        return 1
    
    # Parse dates
    try:
        start_time = parse_datetime(args.start)
        end_time = parse_datetime(args.end)
    except ValueError as e:
        print(f"❌ Date parsing error: {e}")
        return 1
    
    # Validate date range
    if start_time >= end_time:
        print("❌ Error: Start time must be before end time")
        return 1
    
    print("🏠 Home Assistant History Data Puller")
    print("=" * 50)
    print(f"📅 Date range: {start_time} to {end_time}")
    print(f"🔗 HA URL: {args.ha_url}")
    print(f"📄 CSV file: {args.csv}")
    print(f"💾 Output format: {args.format}")
    print()
    
    # Initialize the puller
    puller = HomeAssistantHistoryPuller(args.ha_url, args.token)
    
    # Test connection
    if not puller.test_connection():
        return 1
    
    # Get sensor list from CSV
    sensors = puller.get_sensor_list_from_csv(args.csv)
    if not sensors:
        return 1
    
    print()
    
    # Fetch history data
    history_data = puller.get_history_data(sensors, start_time, end_time)
    if not history_data:
        return 1
    
    print()
    
    # Save data
    success = False
    
    if args.format in ['csv', 'both']:
        csv_file = f"{args.output}.csv"
        success = puller.save_to_csv(history_data, csv_file) or success
    
    if args.format in ['json', 'both']:
        json_file = f"{args.output}.json"
        success = puller.save_to_json(history_data, json_file) or success
    
    if success:
        print("\n✅ History data retrieval completed successfully!")
        return 0
    else:
        print("\n❌ Failed to save history data")
        return 1


if __name__ == '__main__':
    exit(main())