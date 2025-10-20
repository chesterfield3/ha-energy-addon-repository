"""
Home Assistant Energy Data Analyzer

A comprehensive tool for analyzing Home Assistant and Emporia Vue energy consumption data.
Combines data from multiple sources, converts cumulative readings to hourly consumption,
and provides detailed analysis with visualizations.
"""

__version__ = "1.6.0"
__author__ = "Home Assistant Energy Data Analysis Project"

from .main import HAHistoryMain
from .data_analysis import EnergyDataAnalyzer
from .ha_history_puller import HomeAssistantHistoryPuller
from .emporia_data_puller import EmporiaDataPuller

__all__ = [
    'HAHistoryMain',
    'EnergyDataAnalyzer', 
    'HomeAssistantHistoryPuller',
    'EmporiaDataPuller'
]