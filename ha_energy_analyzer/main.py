#!/usr/bin/env python3
"""
Home Assistant Energy Data Analyzer - Main Entry Point

This is the main entry point for the HA Energy Data Analyzer.
It imports and runs the main application from the src package.
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run the main application
from ha_energy_analyzer.main import HAHistoryMain

def main():
    """Main entry point"""
    app = HAHistoryMain()
    return app.run()

if __name__ == '__main__':
    sys.exit(main())