#!/usr/bin/env python3
"""
Home Assistant Database Data Puller

This module provides direct access to the Home Assistant SQLite database
for efficient historical data retrieval, bypassing API limitations.

The HA database schema includes:
- states: Current and historical entity states
- statistics_short_term: Short-term statistics (hourly)
- statistics: Long-term statistics (daily/monthly)
- statistics_meta: Metadata about statistical entities

Author: AI Assistant
Date: 2025-10-20
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import os
from pathlib import Path


class HomeAssistantDatabasePuller:
    """Class to handle direct Home Assistant database access."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to home-assistant_v2.db file. If None, will try to auto-detect.
        """
        self.db_path = db_path
        self.connection = None
        
        if not self.db_path:
            self.db_path = self.find_ha_database()
        
        if self.db_path and os.path.exists(self.db_path):
            print(f"📁 Using HA database: {self.db_path}")
        else:
            print(f"❌ HA database not found at: {self.db_path}")
    
    def find_ha_database(self) -> Optional[str]:
        """
        Try to auto-detect the Home Assistant database location.
        
        Returns:
            Path to database if found, None otherwise
        """
        # Common HA database locations
        possible_paths = [
            # Home Assistant OS / Supervised (from add-on)
            "/config/home-assistant_v2.db",
            # Docker container mounted volume
            "/data/home-assistant_v2.db",
            # Manual installation
            "~/.homeassistant/home-assistant_v2.db",
            # Custom config directory
            "/homeassistant/home-assistant_v2.db",
            # Add-on environment
            "/share/homeassistant/home-assistant_v2.db"
        ]
        
        for path in possible_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                return expanded_path
        
        return None
    
    def connect(self) -> bool:
        """
        Connect to the Home Assistant database.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.db_path or not os.path.exists(self.db_path):
                print(f"❌ Database file not found: {self.db_path}")
                return False
            
            self.connection = sqlite3.connect(self.db_path, timeout=30.0)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
            
            # Test the connection
            cursor = self.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            print(f"✅ Connected to HA database")
            print(f"📊 Available tables: {', '.join(tables)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False
    
    def disconnect(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def get_entity_statistics(self, entity_ids: List[str], start_time: datetime, end_time: datetime, 
                            use_short_term: bool = True) -> List[Dict]:
        """
        Get statistical data directly from the HA database.
        
        Args:
            entity_ids: List of entity IDs to retrieve
            start_time: Start datetime
            end_time: End datetime
            use_short_term: If True, use statistics_short_term (hourly), else statistics (daily)
            
        Returns:
            List of statistics records
        """
        if not self.connection:
            print("❌ No database connection")
            return []
        
        try:
            # Choose the appropriate statistics table
            stats_table = "statistics_short_term" if use_short_term else "statistics"
            period_name = "hourly" if use_short_term else "daily"
            
            print(f"📊 Querying {stats_table} for {period_name} statistics")
            print(f"📅 Time range: {start_time} to {end_time}")
            print(f"🎯 Entities: {', '.join(entity_ids)}")
            
            # Convert datetime to timestamps (HA uses Unix timestamps)
            start_ts = start_time.timestamp()
            end_ts = end_time.timestamp()
            
            print(f"🔍 Debug: start_ts = {start_ts}, end_ts = {end_ts}")
            
            # First, let's check what entities actually exist in statistics_meta
            cursor = self.connection.cursor()
            cursor.execute("SELECT statistic_id FROM statistics_meta LIMIT 10")
            sample_entities = [row[0] for row in cursor.fetchall()]
            print(f"🔍 Debug: Sample entities in statistics_meta: {sample_entities[:5]}")
            
            # Check if any of our target entities exist
            placeholders_check = ','.join(['?'] * len(entity_ids))
            cursor.execute(f"SELECT statistic_id FROM statistics_meta WHERE statistic_id IN ({placeholders_check})", entity_ids)
            found_entities = [row[0] for row in cursor.fetchall()]
            print(f"🔍 Debug: Found entities in statistics_meta: {found_entities}")
            
            if not found_entities:
                print(f"⚠️ None of the requested entities found in statistics_meta table")
                return []
            
            # Use only the entities that actually exist
            working_entity_ids = found_entities
            
            # Build the SQL query
            placeholders = ','.join(['?'] * len(working_entity_ids))
            
            # Also check what data exists in the time range
            cursor.execute(f"""
                SELECT COUNT(*), MIN(start_ts), MAX(start_ts) 
                FROM {stats_table} s
                JOIN statistics_meta sm ON s.metadata_id = sm.id
                WHERE sm.statistic_id IN ({placeholders})
            """, working_entity_ids)
            
            count_result = cursor.fetchone()
            print(f"🔍 Debug: count_result = {count_result}")
            if count_result:
                total_records, min_start, max_start = count_result
                print(f"🔍 Debug: Total records for entities: {total_records}")
                print(f"🔍 Debug: min_start = {min_start}, max_start = {max_start}")
                if min_start and max_start:
                    min_dt = datetime.fromtimestamp(min_start)
                    max_dt = datetime.fromtimestamp(max_start)
                    print(f"🔍 Debug: Data range: {min_dt} to {max_dt}")
                    
                    # Check how many records match our time filter
                    cursor.execute(f"""
                        SELECT COUNT(*) 
                        FROM {stats_table} s
                        JOIN statistics_meta sm ON s.metadata_id = sm.id
                        WHERE sm.statistic_id IN ({placeholders})
                        AND s.start_ts >= ?
                        AND s.start_ts <= ?
                    """, working_entity_ids + [start_ts, end_ts])
                    
                    filtered_count = cursor.fetchone()[0]
                    print(f"🔍 Debug: Records in time range {start_ts} to {end_ts}: {filtered_count}")
            
            query = f"""
            SELECT 
                sm.statistic_id,
                sm.unit_of_measurement,
                s.start_ts,
                s.mean,
                s.min,
                s.max,
                s.last_reset_ts,
                s.state,
                s.sum
            FROM {stats_table} s
            JOIN statistics_meta sm ON s.metadata_id = sm.id
            WHERE sm.statistic_id IN ({placeholders})
            AND s.start_ts >= ?
            AND s.start_ts <= ?
            ORDER BY sm.statistic_id, s.start_ts
            """
            
            params = working_entity_ids + [start_ts, end_ts]
            
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                # Convert back to datetime
                start_dt = datetime.fromtimestamp(row['start_ts'])
                
                record = {
                    'entity_id': row['statistic_id'],
                    'timestamp': start_dt.isoformat(),
                    'mean': row['mean'],
                    'min': row['min'],
                    'max': row['max'],
                    'state': row['state'],
                    'sum': row['sum'],
                    'last_reset': datetime.fromtimestamp(row['last_reset_ts']).isoformat() if row['last_reset_ts'] else None,
                    'unit_of_measurement': row['unit_of_measurement'],
                    'data_source': f'database_{period_name}'
                }
                results.append(record)
            
            print(f"✅ Retrieved {len(results)} {period_name} statistics records")
            return results
            
        except Exception as e:
            print(f"❌ Error querying statistics: {e}")
            return []
    
    def get_entity_states(self, entity_ids: List[str], start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Get raw state data directly from the HA database.
        
        Args:
            entity_ids: List of entity IDs to retrieve
            start_time: Start datetime
            end_time: End datetime
            
        Returns:
            List of state records
        """
        if not self.connection:
            print("❌ No database connection")
            return []
        
        try:
            print(f"📊 Querying states table for raw state data")
            print(f"📅 Time range: {start_time} to {end_time}")
            print(f"🎯 Entities: {', '.join(entity_ids)}")
            
            # Convert datetime to timestamps
            start_ts = start_time.timestamp()
            end_ts = end_time.timestamp()
            
            print(f"🔍 Debug: start_ts = {start_ts}, end_ts = {end_ts}")
            
            # Check what entities actually exist in states table
            cursor = self.connection.cursor()
            placeholders_check = ','.join(['?'] * len(entity_ids))
            cursor.execute(f"SELECT DISTINCT entity_id FROM states WHERE entity_id IN ({placeholders_check}) LIMIT 10", entity_ids)
            found_entities = [row[0] for row in cursor.fetchall()]
            print(f"🔍 Debug: Found entities in states table: {found_entities}")
            
            if not found_entities:
                print(f"⚠️ None of the requested entities found in states table")
                return []
            
            # Check data range for these entities
            cursor.execute(f"""
                SELECT COUNT(*), MIN(last_changed), MAX(last_changed)
                FROM states 
                WHERE entity_id IN ({placeholders_check})
            """, found_entities)
            
            count_result = cursor.fetchone()
            if count_result:
                total_records, min_changed, max_changed = count_result
                print(f"🔍 Debug: Total state records for entities: {total_records}")
                if min_changed and max_changed:
                    min_dt = datetime.fromtimestamp(min_changed)
                    max_dt = datetime.fromtimestamp(max_changed)
                    print(f"🔍 Debug: State data range: {min_dt} to {max_dt}")
            
            # Use only the entities that actually exist
            working_entity_ids = found_entities
            
            # Build the SQL query
            placeholders = ','.join(['?'] * len(working_entity_ids))
            
            query = f"""
            SELECT 
                s.entity_id,
                s.state,
                s.attributes,
                s.last_changed,
                s.last_updated
            FROM states s
            WHERE s.entity_id IN ({placeholders})
            AND s.last_changed >= ?
            AND s.last_changed <= ?
            ORDER BY s.entity_id, s.last_changed
            """
            
            params = working_entity_ids + [start_ts, end_ts]
            
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                # Convert timestamps back to datetime
                last_changed_dt = datetime.fromtimestamp(row['last_changed'])
                last_updated_dt = datetime.fromtimestamp(row['last_updated'])
                
                record = {
                    'entity_id': row['entity_id'],
                    'state': row['state'],
                    'attributes': row['attributes'],  # JSON string
                    'last_changed': last_changed_dt.isoformat(),
                    'last_updated': last_updated_dt.isoformat(),
                    'data_source': 'database_states'
                }
                results.append(record)
            
            print(f"✅ Retrieved {len(results)} state records")
            return results
            
        except Exception as e:
            print(f"❌ Error querying states: {e}")
            return []
    
    def get_available_statistics(self) -> List[Dict]:
        """
        Get list of all entities that have statistics available.
        
        Returns:
            List of available statistic entities with metadata
        """
        if not self.connection:
            print("❌ No database connection")
            return []
        
        try:
            query = """
            SELECT 
                statistic_id,
                source,
                unit_of_measurement,
                has_mean,
                has_sum,
                name
            FROM statistics_meta
            ORDER BY statistic_id
            """
            
            cursor = self.connection.cursor()
            cursor.execute(query)
            
            results = []
            for row in cursor.fetchall():
                record = {
                    'statistic_id': row['statistic_id'],
                    'source': row['source'],
                    'unit_of_measurement': row['unit_of_measurement'],
                    'has_mean': bool(row['has_mean']),
                    'has_sum': bool(row['has_sum']),
                    'name': row['name']
                }
                results.append(record)
            
            print(f"✅ Found {len(results)} entities with statistics")
            return results
            
        except Exception as e:
            print(f"❌ Error querying statistics metadata: {e}")
            return []
    
    def convert_to_history_format(self, records: List[Dict], data_type: str = 'statistics') -> List[List[Dict]]:
        """
        Convert database records to the same format as the API history puller.
        
        Args:
            records: Raw database records
            data_type: 'statistics' or 'states'
            
        Returns:
            Data in the same format as HomeAssistantHistoryPuller
        """
        if not records:
            return []
        
        # Group records by entity_id
        grouped = {}
        for record in records:
            entity_id = record['entity_id']
            if entity_id not in grouped:
                grouped[entity_id] = []
            
            if data_type == 'statistics':
                # Convert statistics record to history format
                history_record = {
                    'entity_id': entity_id,
                    'state': str(record.get('sum', record.get('state', 0))),
                    'last_changed': record['timestamp'],
                    'last_updated': record['timestamp'],
                    'attributes': json.dumps({
                        'unit_of_measurement': record.get('unit_of_measurement', 'kWh'),
                        'device_class': 'energy',
                        'state_class': 'total_increasing',
                        'source': record.get('data_source', 'database_statistics'),
                        'mean': record.get('mean'),
                        'min': record.get('min'),
                        'max': record.get('max'),
                        'sum': record.get('sum')
                    })
                }
            else:  # states
                # States are already in the right format, just ensure consistency
                history_record = {
                    'entity_id': entity_id,
                    'state': record['state'],
                    'last_changed': record['last_changed'],
                    'last_updated': record['last_updated'],
                    'attributes': record['attributes']  # Already JSON string
                }
            
            grouped[entity_id].append(history_record)
        
        # Convert to list of lists (same format as API)
        result = list(grouped.values())
        
        total_records = sum(len(entity_records) for entity_records in result)
        print(f"🔄 Converted {total_records} records for {len(result)} entities")
        
        return result
    
    def get_database_info(self) -> Dict:
        """
        Get information about the Home Assistant database.
        
        Returns:
            Dictionary with database information
        """
        if not self.connection:
            return {}
        
        try:
            info = {}
            
            # Get database file info
            if self.db_path:
                stat = os.stat(self.db_path)
                info['file_size_mb'] = round(stat.st_size / (1024 * 1024), 2)
                info['last_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            # Get table row counts
            cursor = self.connection.cursor()
            
            tables = ['states', 'statistics', 'statistics_short_term', 'statistics_meta']
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    info[f'{table}_count'] = count
                except:
                    info[f'{table}_count'] = 'N/A'
            
            # Get date range of data
            try:
                cursor.execute("SELECT MIN(last_changed), MAX(last_changed) FROM states")
                min_ts, max_ts = cursor.fetchone()
                if min_ts and max_ts:
                    info['states_date_range'] = {
                        'earliest': datetime.fromtimestamp(min_ts).isoformat(),
                        'latest': datetime.fromtimestamp(max_ts).isoformat()
                    }
            except:
                pass
            
            return info
            
        except Exception as e:
            print(f"❌ Error getting database info: {e}")
            return {}
    
    def debug_database_contents(self, entity_id_pattern: Optional[str] = None) -> Dict:
        """
        Debug helper to examine database contents and structure.
        
        Args:
            entity_id_pattern: Optional pattern to filter entities (SQL LIKE syntax)
            
        Returns:
            Dictionary with debug information
        """
        if not self.connection:
            return {}
        
        debug_info = {}
        cursor = self.connection.cursor()
        
        try:
            # Check statistics_meta table
            if entity_id_pattern:
                cursor.execute("SELECT COUNT(*) FROM statistics_meta WHERE statistic_id LIKE ?", (f"%{entity_id_pattern}%",))
            else:
                cursor.execute("SELECT COUNT(*) FROM statistics_meta")
            debug_info['statistics_meta_count'] = cursor.fetchone()[0]
            
            # Get sample statistic IDs
            if entity_id_pattern:
                cursor.execute("SELECT statistic_id FROM statistics_meta WHERE statistic_id LIKE ? LIMIT 10", (f"%{entity_id_pattern}%",))
            else:
                cursor.execute("SELECT statistic_id FROM statistics_meta LIMIT 10")
            debug_info['sample_statistic_ids'] = [row[0] for row in cursor.fetchall()]
            
            # Check statistics_short_term table
            cursor.execute("SELECT COUNT(*) FROM statistics_short_term")
            debug_info['statistics_short_term_count'] = cursor.fetchone()[0]
            
            # Check states table
            if entity_id_pattern:
                cursor.execute("SELECT COUNT(DISTINCT entity_id) FROM states WHERE entity_id LIKE ?", (f"%{entity_id_pattern}%",))
            else:
                cursor.execute("SELECT COUNT(DISTINCT entity_id) FROM states")
            debug_info['unique_entities_in_states'] = cursor.fetchone()[0]
            
            # Get sample entity IDs from states
            if entity_id_pattern:
                cursor.execute("SELECT DISTINCT entity_id FROM states WHERE entity_id LIKE ? LIMIT 10", (f"%{entity_id_pattern}%",))
            else:
                cursor.execute("SELECT DISTINCT entity_id FROM states LIMIT 10")
            debug_info['sample_entity_ids_states'] = [row[0] for row in cursor.fetchall()]
            
            # Get time range of data
            cursor.execute("SELECT MIN(last_changed), MAX(last_changed) FROM states")
            min_ts, max_ts = cursor.fetchone()
            if min_ts and max_ts:
                debug_info['states_time_range'] = {
                    'min': datetime.fromtimestamp(min_ts).isoformat(),
                    'max': datetime.fromtimestamp(max_ts).isoformat()
                }
            
            # Check if statistics have time range
            cursor.execute("SELECT MIN(start), MAX(start) FROM statistics_short_term")
            min_ts, max_ts = cursor.fetchone()
            if min_ts and max_ts:
                debug_info['statistics_time_range'] = {
                    'min': datetime.fromtimestamp(min_ts).isoformat(),
                    'max': datetime.fromtimestamp(max_ts).isoformat()
                }
            
            return debug_info
            
        except Exception as e:
            debug_info['error'] = str(e)
            return debug_info


# Integration function to work with existing code
def create_database_puller(db_path: Optional[str] = None) -> Optional[HomeAssistantDatabasePuller]:
    """
    Create and connect a database puller instance.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        Connected database puller or None if failed
    """
    puller = HomeAssistantDatabasePuller(db_path)
    
    if puller.connect():
        return puller
    else:
        return None


if __name__ == '__main__':
    # Test the database puller
    print("🧪 Testing Home Assistant Database Puller")
    print("=" * 50)
    
    puller = create_database_puller()
    
    if puller:
        try:
            # Show database info
            info = puller.get_database_info()
            print(f"\n📊 Database Information:")
            for key, value in info.items():
                print(f"   {key}: {value}")
            
            # Show available statistics
            stats = puller.get_available_statistics()
            print(f"\n📈 Available Statistics Entities: {len(stats)}")
            for stat in stats[:10]:  # Show first 10
                print(f"   {stat['statistic_id']} ({stat.get('unit_of_measurement', 'N/A')})")
            if len(stats) > 10:
                print(f"   ... and {len(stats) - 10} more")
                
        finally:
            puller.disconnect()
    else:
        print("❌ Could not connect to Home Assistant database")