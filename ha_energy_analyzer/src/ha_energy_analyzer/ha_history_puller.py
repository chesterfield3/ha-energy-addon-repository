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


class HomeAssistantHistoryPuller:
    """Class to handle Home Assistant history data retrieval."""
    
    def __init__(self, ha_url: str, token: str):
        """
        Initialize the Home Assistant connection.
        
        Args:
            ha_url: URL of your Home Assistant instance (e.g., 'http://homeassistant.local:8123')
            token: Long-lived access token for API authentication
        """
        self.ha_url = ha_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
    def test_connection(self) -> bool:
        """
        Test the connection to Home Assistant API.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
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
    
    def get_history_data(self, entity_ids: List[str], start_time: str, end_time: str) -> Dict:
        """
        Retrieve history data from Home Assistant.
        
        Args:
            entity_ids: List of entity IDs to retrieve data for
            start_time: Start time in ISO format (e.g., '2025-10-15T00:00:00')
            end_time: End time in ISO format (e.g., '2025-10-15T23:59:59')
            
        Returns:
            Dictionary containing the history data response
        """
        # Construct the API URL
        url = urljoin(self.ha_url, '/api/history/period/' + start_time)
        
        # Parameters for the request
        params = {
            'filter_entity_id': ','.join(entity_ids),
            'end_time': end_time
        }
        
        print(f"🔄 Fetching history data from {start_time} to {end_time}")
        print(f"📡 API URL: {url}")
        print(f"🎯 Entities: {', '.join(entity_ids)}")
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            print(f"✅ Successfully retrieved history data")
            
            # Count total data points
            total_points = sum(len(entity_data) for entity_data in data)
            print(f"📊 Total data points retrieved: {total_points}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching history data: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON response: {e}")
            return {}
    
    def save_to_csv(self, history_data: Dict, output_file: str) -> bool:
        """
        Save history data to CSV file.
        
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
    
    def save_to_json(self, history_data: Dict, output_file: str) -> bool:
        """
        Save history data to JSON file.
        
        Args:
            history_data: Dictionary containing history data from HA API
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