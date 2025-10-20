# Sensor Configuration Guide

This guide explains how to configure your energy sensors for the Home Assistant Energy Data Analyzer.

## Required Configuration Files

The add-on uses two CSV files to map your Home Assistant sensor entity IDs to friendly names:

### 1. `ha_sensors.csv` - Home Assistant Energy Sensors
Maps your Home Assistant energy sensors (Kasa plugs, Shelly devices, etc.) to friendly names.

### 2. `emporia_sensors.csv` - Emporia Vue Sensors  
Maps your Emporia Vue smart meter sensors to friendly names.

## Setup Instructions

### Step 1: Find Your Sensor Entity IDs

1. **In Home Assistant**, go to:
   - **Developer Tools** → **States**
   - Search for sensors containing "consumption" or "energy"
   - Look for sensors ending in `_today_s_consumption`

2. **Copy the entity IDs** (examples):
   - `sensor.kitchen_fridge_today_s_consumption`
   - `sensor.emporia_main_panel_today_s_consumption`

### Step 2: Create Your Configuration Files

#### Option A: Use the Web Interface
1. Go to **File Editor** add-on in Home Assistant
2. Navigate to `/share/ha_energy_analyzer/`
3. Create `ha_sensors.csv` and `emporia_sensors.csv`

#### Option B: Use Templates
Copy the template files and customize them:

**ha_sensors.csv:**
```csv
entity_id, name, upstream_sensor
sensor.kitchen_fridge_today_s_consumption, kitchen_fridge, none
sensor.living_room_tv_today_s_consumption, living_room_tv, none
sensor.computer_today_s_consumption, computer, office
sensor.printer_today_s_consumption, printer, office
```

**emporia_sensors.csv:**
```csv
entity_id, name
sensor.emporia_main_panel_today_s_consumption, main_panel
sensor.emporia_office_today_s_consumption, office
sensor.emporia_hvac_today_s_consumption, hvac
```

### Step 3: File Format Details

#### ha_sensors.csv Format
- **entity_id**: Exact Home Assistant entity ID
- **name**: Friendly name for reports (no spaces recommended)
- **upstream_sensor**: Grouping field (use "none" if not grouping)

#### emporia_sensors.csv Format  
- **entity_id**: Exact Emporia Vue entity ID  
- **name**: Friendly name for reports (no spaces recommended)

## Common Sensor Types

### Kasa Smart Plugs
```csv
sensor.kasa_plug_kitchen_today_s_consumption, kitchen_appliance, none
```

### Shelly Devices
```csv
sensor.shelly_washer_today_s_consumption, washing_machine, none
```

### Emporia Vue Circuits
```csv
sensor.emporia_hvac_today_s_consumption, hvac
sensor.emporia_water_heater_today_s_consumption, water_heater
```

## Troubleshooting

### Common Issues

**Sensor Not Found:**
- Verify the entity ID exists in Developer Tools → States
- Check spelling and underscores
- Ensure the sensor has recent data

**No Data in Reports:**
- Check that sensors have `_today_s_consumption` in the name
- Verify sensors are recording energy data (not power)
- Ensure sensors reset daily

**File Format Errors:**
- Use commas to separate columns
- No spaces in the friendly names (use underscores)
- Include header row with column names

### Getting Sensor Entity IDs

1. **Kasa Integration**: Look for `sensor.*_today_s_consumption`
2. **Shelly Integration**: Look for `sensor.shelly_*_today_s_consumption`  
3. **Emporia Vue**: Look for `sensor.emporia_*_today_s_consumption`
4. **Generic Energy**: Look for any sensor ending in `consumption`

## File Locations

When using the Home Assistant Add-on:
- Configuration files: `/share/ha_energy_analyzer/`
- Generated reports: `/share/ha_energy_analyzer/output/`
- Logs: Available in Add-on → HA Energy Data Analyzer → Log

## Example Complete Setup

**ha_sensors.csv:**
```csv
entity_id, name, upstream_sensor
sensor.kitchen_fridge_today_s_consumption, kitchen_fridge, none
sensor.basement_fridge_today_s_consumption, basement_fridge, none
sensor.dishwasher_today_s_consumption, dishwasher, none
sensor.washing_machine_today_s_consumption, washing_machine, none
sensor.computer_main_today_s_consumption, computer_main, office
sensor.computer_monitor_today_s_consumption, computer_monitor, office
sensor.printer_today_s_consumption, printer, office
```

**emporia_sensors.csv:**
```csv
entity_id, name
sensor.emporia_main_panel_today_s_consumption, main_panel
sensor.emporia_hvac_today_s_consumption, hvac  
sensor.emporia_water_heater_today_s_consumption, water_heater
sensor.emporia_dryer_today_s_consumption, dryer
sensor.emporia_car_charger_today_s_consumption, car_charger
sensor.emporia_office_today_s_consumption, office_total
```

This setup will track individual smart plugs through Home Assistant sensors and main circuits through Emporia Vue, giving you comprehensive energy monitoring coverage.