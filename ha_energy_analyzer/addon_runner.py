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
        app.base_dir = "/app"
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
            # For subsequent runs, do incremental update (last 6 hours with overlap)
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
        result = app.pull_data(
            start_date=start_date,
            end_date=end_date,
            output_format='both',  # CSV and JSON
            output_filename=output_filename,
            analyze=True,
            data_sources='both',  # HA and Emporia if available
            apply_ha_offset=True,
            ha_pull_offset_only=False,
            is_incremental=is_incremental  # True for incremental, False for initial pull
        )
        
        if isinstance(result, dict) and result['data_pull']:
            if is_first_run:
                logger.info("✅ Initial historical data pull completed successfully!")
                logger.info("📊 Future runs will perform incremental updates every few hours")
            else:
                logger.info("✅ Incremental energy analysis completed successfully!")
            
            # Copy results to predictable locations
            latest_csv = os.path.join(output_dir, "latest_analysis.csv")
            latest_json = os.path.join(output_dir, "latest_analysis.json")
            
            # Copy the latest files
            import shutil
            try:
                if os.path.exists("/app/output/energy_analysis.csv"):
                    shutil.copy2("/app/output/energy_analysis.csv", latest_csv)
                    logger.info(f"📊 Latest CSV available at: {latest_csv}")
                
                if os.path.exists("/app/output/energy_analysis.json"):
                    shutil.copy2("/app/output/energy_analysis.json", latest_json)
                    logger.info(f"📊 Latest JSON available at: {latest_json}")
                    
                # Ensure the detection file exists for future runs
                if not os.path.exists(latest_csv) and os.path.exists("/app/output/energy_analysis.csv"):
                    shutil.copy2("/app/output/energy_analysis.csv", latest_csv)
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