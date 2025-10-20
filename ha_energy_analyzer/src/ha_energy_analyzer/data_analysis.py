#!/usr/bin/env python3
"""
Home Assistant Energy Data Analysis

This script analyzes energy consumption data from Home Assistant CSV exports.
It converts cumulative consumption data into hourly consumption values using
linear interpolation when exact hourly values are not available.

Features:
- Convert cumulative to hourly consumption
- Linear interpolation for missing hourly data points
- Statistical analysis and visualization
- Export processed data to CSV

Author: AI Assistant
Date: 2025-10-15
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Tuple, Optional
import argparse
import os
from scipy import stats
from sklearn.linear_model import LinearRegression


class EnergyDataAnalyzer:
    """Analyzer for Home Assistant energy consumption data"""
    
    def __init__(self, csv_file: str, sensor_names_file: str = 'ha_sensors.csv'):
        """
        Initialize the analyzer with a CSV file.
        
        Args:
            csv_file: Path to CSV file with HA history data
            sensor_names_file: Path to CSV file with sensor name mappings
        """
        self.csv_file = csv_file
        self.sensor_names_file = sensor_names_file
        self.data: Optional[pd.DataFrame] = None
        self.hourly_data: Dict[str, pd.DataFrame] = {}
        self.sensor_names: Dict[str, str] = {}
        self.central_tz = pytz.timezone('US/Central')
        self.load_sensor_names()
        
    def load_sensor_names(self) -> bool:
        """Load sensor name mapping from CSV file"""
        try:
            if not os.path.exists(self.sensor_names_file):
                print(f"⚠️ Warning: Sensor names file '{self.sensor_names_file}' not found!")
                return False
            
            # Read the CSV file with sensor names
            df = pd.read_csv(self.sensor_names_file)
            
            # Clean up column names (remove spaces)
            df.columns = df.columns.str.strip()
            
            # Create the mapping dictionary
            for _, row in df.iterrows():
                entity_id = str(row['entity_id']).strip()
                name = str(row['name']).strip()
                self.sensor_names[entity_id] = name
            
            print(f"📋 Loaded {len(self.sensor_names)} sensor name mappings")
            return True
            
        except Exception as e:
            print(f"⚠️ Warning: Failed to load sensor names: {e}")
            return False
        
    def load_data(self) -> bool:
        """
        Load and preprocess the CSV data.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"📁 Loading data from {self.csv_file}")
            
            # Load CSV data
            self.data = pd.read_csv(self.csv_file)
            
            # Check if this is already processed hourly data or raw history data
            if 'hourly_consumption' in self.data.columns:
                print("📊 Detected processed hourly consumption data")
                # This is already processed hourly data
                self.data['datetime'] = pd.to_datetime(self.data['datetime'], format='ISO8601')
                self.data['state_numeric'] = self.data['cumulative_consumption']
                self.data['last_changed'] = self.data['datetime']  # For compatibility
                valid_data = self.data
            else:
                print("📊 Detected raw history data - will process into hourly consumption")
                # This is raw history data
                # Convert timestamps to datetime and then to Central Time
                self.data['last_changed'] = pd.to_datetime(self.data['last_changed'], format='ISO8601')
                self.data['last_updated'] = pd.to_datetime(self.data['last_updated'], format='ISO8601')
                
                # Convert timestamps to Central Time if they are timezone-aware
                if self.data['last_changed'].dt.tz is not None:
                    self.data['last_changed'] = self.data['last_changed'].dt.tz_convert(self.central_tz)
                    print("🕐 Converted timestamps to Central Time")
                    
                if self.data['last_updated'].dt.tz is not None:
                    self.data['last_updated'] = self.data['last_updated'].dt.tz_convert(self.central_tz)
                
                # Convert state to numeric, handling non-numeric values
                self.data['state_numeric'] = pd.to_numeric(self.data['state'], errors='coerce')
                
                # Filter out non-numeric states (like 'unavailable', 'unknown')
                valid_data = self.data.dropna(subset=['state_numeric'])
            
            print(f"📊 Loaded {len(self.data)} total records")
            print(f"📊 {len(valid_data)} records with numeric values")
            print(f"🏷️ Found {self.data['entity_id'].nunique()} unique sensors")
            
            # Show sensor list
            sensors = self.data['entity_id'].unique()
            print(f"\n📋 Sensors found:")
            for sensor in sorted(sensors):
                count = len(self.data[self.data['entity_id'] == sensor])
                print(f"   - {sensor} ({count} records)")
            
            self.data = valid_data
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    
    def interpolate_hourly_value(self, df_sensor: pd.DataFrame, target_hour: datetime) -> Optional[float]:
        """
        Interpolate consumption value for a specific hour using linear regression.
        
        Args:
            df_sensor: DataFrame with data for a single sensor
            target_hour: Target datetime (should be exactly on the hour)
            
        Returns:
            Interpolated consumption value or None if not possible
        """
        # Check if we have an exact match first
        exact_match = df_sensor[df_sensor['last_changed'] == target_hour]
        if not exact_match.empty:
            return float(exact_match.iloc[0]['state_numeric'])
        
        # Find the closest records before and after the target hour
        before = df_sensor[df_sensor['last_changed'] < target_hour]
        after = df_sensor[df_sensor['last_changed'] > target_hour]
        
        if before.empty or after.empty:
            return None
        
        # Get the closest records
        before_record = before.iloc[-1]  # Latest record before target
        after_record = after.iloc[0]     # Earliest record after target
        
        # CHECK FOR SENSOR RESET before interpolating
        value_diff = after_record['state_numeric'] - before_record['state_numeric']
        
        # If the after value is much smaller than before value, this indicates a sensor reset
        # Don't interpolate across sensor resets - use the before value instead
        if value_diff < -0.1:  # Sensor reset detected
            print(f"🔄 Sensor reset detected during interpolation at {target_hour}: {before_record['state_numeric']:.3f} → {after_record['state_numeric']:.3f}")
            # For interpolation during a reset, use the before value (pre-reset cumulative)
            # This prevents creating artificial consumption values
            return float(before_record['state_numeric'])
        
        # Convert timestamps to seconds for linear regression
        before_seconds = before_record['last_changed'].timestamp()
        after_seconds = after_record['last_changed'].timestamp()
        target_seconds = target_hour.timestamp()
        
        # Linear interpolation (only if no reset detected)
        time_diff = after_seconds - before_seconds
        if time_diff == 0:
            return float(before_record['state_numeric'])
        
        target_offset = target_seconds - before_seconds
        
        interpolated_value = before_record['state_numeric'] + (value_diff * target_offset / time_diff)
        
        return float(interpolated_value)
    
    def calculate_hourly_consumption(self, sensor_id: str) -> pd.DataFrame:
        """
        Calculate hourly consumption for a specific sensor.
        
        Args:
            sensor_id: Entity ID of the sensor
            
        Returns:
            DataFrame with hourly consumption data
        """
        print(f"\n🔄 Processing sensor: {sensor_id}")
        
        # Check if data is loaded
        if self.data is None:
            print(f"⚠️ No data loaded. Call load_data() first.")
            return pd.DataFrame()
        
        # Filter data for this sensor
        sensor_data = self.data[self.data['entity_id'] == sensor_id].copy()
        sensor_data = sensor_data.sort_values('last_changed')
        
        if sensor_data.empty:
            print(f"⚠️ No data found for sensor {sensor_id}")
            return pd.DataFrame()
        
        print(f"📊 Found {len(sensor_data)} records")
        print(f"📅 Date range: {sensor_data['last_changed'].min()} to {sensor_data['last_changed'].max()}")
        
        # Generate hourly timestamps
        start_hour = sensor_data['last_changed'].min().replace(minute=0, second=0, microsecond=0)
        # Round the end time UP to the next hour to include the final partial hour
        max_time = sensor_data['last_changed'].max()
        if max_time.minute > 0 or max_time.second > 0 or max_time.microsecond > 0:
            # If there are minutes/seconds, round up to next hour
            end_hour = max_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
        else:
            # If exactly on the hour, just add one hour
            end_hour = max_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        hourly_timestamps = pd.date_range(start=start_hour, end=end_hour, freq='h')
        
        hourly_consumption = []
        interpolated_count = 0
        exact_count = 0
        
        print(f"🕐 Generating {len(hourly_timestamps)} hourly data points...")
        
        for i, hour in enumerate(hourly_timestamps):
            # Get cumulative consumption at this hour
            cumulative_value = self.interpolate_hourly_value(sensor_data, hour)
            
            if cumulative_value is not None:
                # Check if this was interpolated or exact
                exact_match = sensor_data[sensor_data['last_changed'] == hour]
                if exact_match.empty:
                    interpolated_count += 1
                    method = 'interpolated'
                else:
                    exact_count += 1
                    method = 'exact'
                
                # Calculate hourly consumption (difference from previous hour)
                if len(hourly_consumption) == 0:
                    hourly_consumption_value = 0  # First hour, no previous value
                else:
                    # Normal hour: Calculate difference from previous hour
                    prev_cumulative = hourly_consumption[-1]['cumulative_consumption']
                    raw_consumption = cumulative_value - prev_cumulative
                    
                    # Handle HA energy sensor reset (large negative value indicates reset)
                    if raw_consumption < -0.1:  # Lowered threshold to catch more resets
                        # This is likely a sensor reset - use the current cumulative value as hourly consumption
                        # This represents consumption from reset (0) to current cumulative value
                        hourly_consumption_value = max(0, cumulative_value)
                        method = method + '_reset_detected'
                        print(f"🔄 Detected sensor reset at {hour}: {prev_cumulative:.3f} → {cumulative_value:.3f}")
                    else:
                        hourly_consumption_value = max(0, raw_consumption)
                
                # Get sensor name
                sensor_name = self.sensor_names.get(sensor_id, sensor_id.replace('sensor.', '').replace('_', ' '))
                
                hourly_consumption.append({
                    'datetime': hour,
                    'entity_id': sensor_id,
                    'sensor_name': sensor_name,
                    'cumulative_consumption': cumulative_value,
                    'hourly_consumption': hourly_consumption_value,
                    'data_method': method
                })
        
        print(f"✅ Generated hourly data: {exact_count} exact matches, {interpolated_count} interpolated")
        
        return pd.DataFrame(hourly_consumption)
    
    def analyze_all_sensors(self) -> Dict[str, pd.DataFrame]:
        """
        Analyze all sensors and calculate hourly consumption.
        
        Returns:
            Dictionary of sensor_id -> hourly consumption DataFrame
        """
        if self.data is None:
            print("❌ No data loaded!")
            return {}
        
        sensors = self.data['entity_id'].unique()
        
        print(f"\n🔄 Analyzing {len(sensors)} sensors...")
        
        for sensor in sensors:
            hourly_df = self.calculate_hourly_consumption(sensor)
            if not hourly_df.empty:
                self.hourly_data[sensor] = hourly_df
        
        print(f"\n✅ Analysis complete! Processed {len(self.hourly_data)} sensors.")
        return self.hourly_data
    
    def save_hourly_data(self, output_file: str) -> bool:
        """
        Save all hourly consumption data to CSV.
        
        Args:
            output_file: Path to output CSV file
            
        Returns:
            bool: True if successful
        """
        try:
            if not self.hourly_data:
                print("❌ No hourly data to save!")
                return False
            
            # Combine all sensor data
            all_hourly_data = []
            for sensor_id, df in self.hourly_data.items():
                all_hourly_data.append(df)
            
            combined_df = pd.concat(all_hourly_data, ignore_index=True)
            combined_df = combined_df.sort_values(['entity_id', 'datetime'])
            
            # Save to CSV
            combined_df.to_csv(output_file, index=False)
            
            print(f"💾 Saved {len(combined_df)} hourly records to {output_file}")
            
            # Show summary statistics
            total_consumption = combined_df['hourly_consumption'].sum()
            avg_hourly = combined_df['hourly_consumption'].mean()
            max_hourly = combined_df['hourly_consumption'].max()
            
            print(f"\n📊 Summary Statistics:")
            print(f"   Total consumption: {total_consumption:.3f} kWh")
            print(f"   Average hourly: {avg_hourly:.3f} kWh")
            print(f"   Maximum hourly: {max_hourly:.3f} kWh")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving hourly data: {e}")
            return False
    
    def create_consumption_plots(self, output_dir: str = "plots") -> bool:
        """
        Create visualization plots for consumption data.
        
        Args:
            output_dir: Directory to save plots
            
        Returns:
            bool: True if successful
        """
        try:
            if not self.hourly_data:
                print("❌ No hourly data for plotting!")
                return False
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            print(f"\n📊 Creating consumption plots in {output_dir}/")
            
            # Set style
            plt.style.use('default')
            sns.set_palette("husl")
            
            # Plot 1: Daily consumption by sensor
            fig, ax = plt.subplots(figsize=(15, 8))
            
            for sensor_id, df in self.hourly_data.items():
                if not df.empty:
                    # Group by date and sum hourly consumption
                    df['date'] = df['datetime'].dt.date
                    daily_consumption = df.groupby('date')['hourly_consumption'].sum()
                    
                    # Clean sensor name for legend
                    clean_name = sensor_id.replace('sensor.', '').replace('_today_s_consumption', '').replace('_', ' ').title()
                    
                    ax.plot(list(daily_consumption.index), list(daily_consumption.values), 
                           marker='o', linewidth=2, markersize=4, label=clean_name)
            
            ax.set_title('Daily Energy Consumption by Sensor', fontsize=16, fontweight='bold')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Daily Consumption (kWh)', fontsize=12)
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f"{output_dir}/daily_consumption.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            # Plot 2: Hourly consumption heatmap for each sensor
            for sensor_id, df in list(self.hourly_data.items())[:3]:  # Limit to first 3 sensors
                if df.empty:
                    continue
                
                clean_name = sensor_id.replace('sensor.', '').replace('_today_s_consumption', '').replace('_', ' ').title()
                
                # Create pivot table for heatmap
                df_copy = df.copy()
                df_copy['date'] = df_copy['datetime'].dt.date
                df_copy['hour'] = df_copy['datetime'].dt.hour
                
                pivot = df_copy.pivot_table(values='hourly_consumption', 
                                          index='date', 
                                          columns='hour', 
                                          fill_value=0)
                
                if not pivot.empty:
                    fig, ax = plt.subplots(figsize=(16, 8))
                    sns.heatmap(pivot, cmap='YlOrRd', annot=False, fmt='.3f', 
                               cbar_kws={'label': 'Hourly Consumption (kWh)'}, ax=ax)
                    ax.set_title(f'Hourly Consumption Pattern - {clean_name}', fontsize=14, fontweight='bold')
                    ax.set_xlabel('Hour of Day', fontsize=12)
                    ax.set_ylabel('Date', fontsize=12)
                    plt.tight_layout()
                    
                    safe_filename = sensor_id.replace('sensor.', '').replace('.', '_')
                    plt.savefig(f"{output_dir}/heatmap_{safe_filename}.png", dpi=300, bbox_inches='tight')
                    plt.close()
            
            print(f"✅ Plots saved to {output_dir}/")
            return True
            
        except Exception as e:
            print(f"❌ Error creating plots: {e}")
            return False
    
    def generate_summary_report(self) -> str:
        """
        Generate a summary report of the analysis.
        
        Returns:
            String with summary report
        """
        if not self.hourly_data:
            return "No data analyzed yet."
        
        report = []
        report.append("📊 ENERGY CONSUMPTION ANALYSIS REPORT")
        report.append("=" * 50)
        report.append(f"📅 Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"📁 Source File: {self.csv_file}")
        report.append("")
        
        # Overall statistics
        total_sensors = len(self.hourly_data)
        total_hours = sum(len(df) for df in self.hourly_data.values())
        total_consumption = sum(df['hourly_consumption'].sum() for df in self.hourly_data.values())
        
        report.append("📈 OVERALL STATISTICS:")
        report.append(f"   Sensors analyzed: {total_sensors}")
        report.append(f"   Total hour records: {total_hours}")
        report.append(f"   Total consumption: {total_consumption:.3f} kWh")
        report.append("")
        
        # Per-sensor breakdown
        report.append("🏷️ SENSOR BREAKDOWN:")
        for sensor_id, df in self.hourly_data.items():
            clean_name = sensor_id.replace('sensor.', '').replace('_today_s_consumption', '').replace('_', ' ').title()
            sensor_total = df['hourly_consumption'].sum()
            sensor_avg = df['hourly_consumption'].mean()
            sensor_max = df['hourly_consumption'].max()
            date_range = f"{df['datetime'].min().date()} to {df['datetime'].max().date()}"
            
            report.append(f"   📊 {clean_name}:")
            report.append(f"      Total: {sensor_total:.3f} kWh")
            report.append(f"      Average hourly: {sensor_avg:.3f} kWh")
            report.append(f"      Peak hourly: {sensor_max:.3f} kWh")
            report.append(f"      Date range: {date_range}")
            report.append("")
        
        return "\n".join(report)


def main():
    """Main function for command line usage"""
    parser = argparse.ArgumentParser(
        description='Analyze Home Assistant energy consumption data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis
  python data_analysis.py --input ha_history_output.csv
  
  # Analysis with plots
  python data_analysis.py --input ha_history_output.csv --plots
  
  # Custom output file
  python data_analysis.py --input ha_history_output.csv --output hourly_consumption.csv
        """
    )
    
    parser.add_argument('--input', required=True,
                       help='Input CSV file with HA history data')
    parser.add_argument('--output', default='hourly_consumption.csv',
                       help='Output CSV file for hourly consumption data')
    parser.add_argument('--plots', action='store_true',
                       help='Generate visualization plots')
    parser.add_argument('--plot-dir', default='plots',
                       help='Directory for saving plots')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"❌ Input file not found: {args.input}")
        return 1
    
    print("🔬 HOME ASSISTANT ENERGY DATA ANALYSIS")
    print("=" * 50)
    
    # Initialize analyzer
    analyzer = EnergyDataAnalyzer(args.input)
    
    # Load data
    if not analyzer.load_data():
        return 1
    
    # Analyze all sensors
    hourly_data = analyzer.analyze_all_sensors()
    
    if not hourly_data:
        print("❌ No hourly data generated!")
        return 1
    
    # Save hourly data
    if not analyzer.save_hourly_data(args.output):
        return 1
    
    # Create plots if requested
    if args.plots:
        analyzer.create_consumption_plots(args.plot_dir)
    
    # Generate and display summary report
    report = analyzer.generate_summary_report()
    print(f"\n{report}")
    
    print(f"\n✅ Analysis complete!")
    print(f"📄 Hourly data saved to: {args.output}")
    if args.plots:
        print(f"📊 Plots saved to: {args.plot_dir}/")
    
    return 0


if __name__ == '__main__':
    exit(main())