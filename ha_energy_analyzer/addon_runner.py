#!/usr/bin/env python3
"""
Non-interactive runner for Home Assistant Add-on

This script runs the energy analyzer automatically without user interaction,
using environment variables for configuration.

Author: AI Assistant
Date: 2025-10-20
"""

import os
import sys
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run energy analysis non-interactively"""
    try:
        logger.info("🏠 Starting HA Energy Analyzer Add-on...")
        
        # Test holidays library availability
        try:
            import holidays
            logger.info("✅ holidays library loaded successfully for peak hour detection")
        except ImportError as e:
            logger.warning(f"⚠️ holidays library not available ({e}) - will use weekday-only peak detection")
        except Exception as e:
            logger.warning(f"⚠️ Error loading holidays library ({e}) - will use weekday-only peak detection")
        
        # Import after ensuring the module path
        sys.path.insert(0, '/app/src')
        from ha_energy_analyzer.main import HAHistoryMain
        
        # Create main instance
        app = HAHistoryMain()
        
        # Override paths for add-on environment
        app.base_dir = "/share/ha_energy_analyzer"  # Use shared directory for persistence
        app.csv_file = "/share/ha_energy_analyzer/ha_sensors.csv"
        
        # Use environment variables for credentials
        ha_url_from_config = os.getenv('HA_URL', 'http://supervisor/core')
        app.ha_token = os.getenv('HA_TOKEN', '')
        
        # For Home Assistant add-ons, we need to use the correct supervisor endpoint
        if ha_url_from_config == 'http://supervisor/core':
            # Try the standard supervisor API endpoint first
            app.ha_url = 'http://supervisor/core'
            logger.info("🔧 Using Home Assistant Supervisor core API")
            
            # Check if we have a Supervisor token available
            supervisor_token = os.getenv('SUPERVISOR_TOKEN', '')
            if supervisor_token and not app.ha_token:
                app.ha_token = supervisor_token
                logger.info("🔐 Using Supervisor token for authentication")
        else:
            app.ha_url = ha_url_from_config
        
        if not app.ha_token:
            logger.error("❌ HA_TOKEN environment variable is required!")
            logger.error("💡 Please configure the ha_token in the add-on configuration")
            logger.error("🔗 Or try using your external HA URL (e.g., http://homeassistant.local:8123)")
            return 1
        
        logger.info(f"🔗 HA URL: {app.ha_url}")
        logger.info(f"📄 CSV File: {app.csv_file}")
        
        # Initialize puller without user interaction
        logger.info("🔄 Initializing Home Assistant connection...")
        
        # Check if CSV file exists in share directory
        if not os.path.exists(app.csv_file):
            # Copy default file if it doesn't exist
            default_csv = "/app/data/ha_sensors.csv"
            if os.path.exists(default_csv):
                import shutil
                shutil.copy2(default_csv, app.csv_file)
                logger.info(f"📋 Copied default sensor configuration to {app.csv_file}")
            else:
                logger.error(f"❌ No sensor configuration found at {app.csv_file}")
                return 1
        
        # Initialize HA connection
        from ha_energy_analyzer.ha_history_puller import HomeAssistantHistoryPuller
        app.puller = HomeAssistantHistoryPuller(app.ha_url, app.ha_token)
        
        if not app.puller.test_connection():
            logger.error("❌ Failed to connect to Home Assistant!")
            return 1
        
        # Load sensor names
        app.load_sensor_names()
        
        # Initialize Emporia (optional)
        app.initialize_emporia()
        
        # Check if this is the first run by looking for existing analysis data
        output_dir = "/share/ha_energy_analyzer/output"
        os.makedirs(output_dir, exist_ok=True)
        
        existing_analysis = os.path.join(output_dir, "latest_analysis.csv")
        is_first_run = not os.path.exists(existing_analysis)
        
        if is_first_run:
            logger.info("🔍 No existing energy analysis found - performing initial historical data pull")
            # For first run, pull all data from Emporia service start date (Sept 27, 2025)
            start_date = datetime(2025, 9, 27, 0, 0, 0)
            end_date = datetime.now()
            is_incremental = False
            
            logger.info(f"📅 Initial historical pull: {start_date} to {end_date}")
            logger.info(f"⏰ This may take several minutes for the initial data load...")
        else:
            logger.info("📊 Existing data found - performing incremental update")
            # For subsequent runs, do incremental update from most recent data timestamp
            
            # Find the most recent timestamp in existing data
            latest_timestamp = app.get_latest_timestamp_from_analysis()
            
            if latest_timestamp:
                # Start 6 hours before the latest data timestamp to ensure overlap
                start_date = latest_timestamp - timedelta(hours=6)
                end_date = datetime.now()
                logger.info(f"📅 Found latest data timestamp: {latest_timestamp}")
                logger.info(f"📅 Starting incremental update 6 hours before latest: {start_date}")
            else:
                # Fallback to current time if no existing data found
                logger.warning("⚠️ Could not find latest timestamp, falling back to 6 hours from now")
                end_date = datetime.now()
                start_date = end_date - timedelta(hours=6)
            
            is_incremental = True
            logger.info(f"📅 Incremental update: {start_date} to {end_date}")
        
        # Generate output filename
        if is_first_run:
            output_filename = f"initial_historical_pull_{end_date.strftime('%Y%m%d_%H%M%S')}"
        else:
            output_filename = f"incremental_update_{end_date.strftime('%Y%m%d_%H%M%S')}"
        
        # Pull and analyze data
        if app.emporia_available:
            data_sources = 'both'
            logger.info("📊 Using both Home Assistant and Emporia Vue data sources")
        else:
            data_sources = 'both'  # Still try both - let the main app handle the fallback
            logger.warning("⚠️ Emporia Vue not available, but still requesting both sources (will fallback to HA only)")
        
        logger.info(f"🚀 Starting data pull with parameters:")
        logger.info(f"   📅 Date range: {start_date} to {end_date}")
        logger.info(f"   � Date types: {type(start_date)} to {type(end_date)}")
        logger.info(f"   �📊 Data sources: {data_sources}")
        logger.info(f"   🔄 Incremental: {is_incremental}")
        
        logger.info("🎯 About to call app.pull_data()...")
        
        try:
            result = app.pull_data(
                start_date=start_date,
                end_date=end_date,
                output_format='both',  # CSV and JSON
                output_filename=output_filename,
                analyze=True,
                data_sources=data_sources,  # Always try both, let main app handle fallback
                apply_ha_offset=True,
                ha_pull_offset_only=False,
                is_incremental=is_incremental  # True for incremental, False for initial pull
            )
            logger.info(f"✅ app.pull_data() returned successfully")
            
        except Exception as e:
            logger.error(f"❌ Exception in app.pull_data(): {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            raise
        
        logger.info(f"📋 Data pull completed, checking results...")
        
        if isinstance(result, dict) and result['data_pull']:
            if is_first_run:
                logger.info("✅ Initial historical data pull completed successfully!")
                logger.info("📊 Future runs will perform incremental updates every few hours")
            else:
                logger.info("✅ Incremental energy analysis completed successfully!")
            
            # Copy results to predictable locations
            latest_csv = os.path.join(output_dir, "latest_analysis.csv")
            latest_json = os.path.join(output_dir, "latest_analysis.json")
            
            # With the new base_dir, files are saved directly to shared directory
            import shutil
            try:
                energy_csv = os.path.join(output_dir, "energy_analysis.csv")
                energy_json = os.path.join(output_dir, "energy_analysis.json")
                
                if os.path.exists(energy_csv):
                    shutil.copy2(energy_csv, latest_csv)
                    logger.info(f"📊 Latest CSV available at: {latest_csv}")
                
                if os.path.exists(energy_json):
                    shutil.copy2(energy_json, latest_json)
                    logger.info(f"📊 Latest JSON available at: {latest_json}")
                    
                # Ensure the detection file exists for future runs
                if not os.path.exists(latest_csv) and os.path.exists(energy_csv):
                    shutil.copy2(energy_csv, latest_csv)
                    logger.info(f"🔧 Created detection file for future incremental runs")
                    
            except Exception as e:
                logger.warning(f"⚠️ Could not copy latest files: {e}")
            
            return 0
        else:
            if is_first_run:
                logger.error("❌ Initial historical data pull failed!")
            else:
                logger.error("❌ Incremental energy analysis failed!")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Error in add-on runner: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())