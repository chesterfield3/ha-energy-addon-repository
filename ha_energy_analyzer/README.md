# Home Assistant Energy Data Analyzer

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

A comprehensive energy monitoring and analysis tool that seamlessly integrates with Home Assistant and Emporia Vue smart meters to provide detailed energy consumption insights, cost tracking, and automated reporting.

## About

This add-on provides a complete energy monitoring solution that:

- 📊 Analyzes historical energy consumption data from Home Assistant sensors
- ⚡ Integrates with Emporia Vue smart meters for enhanced data
- 🔄 Performs incremental data updates to preserve historical records
- 📧 Sends email notifications and reports
- 📈 Generates data visualizations and cost analysis
- ⏰ Runs automated analysis on a configurable schedule

## Installation

1. Add this repository to your Home Assistant Add-on Store:
   - Go to **Settings** → **Add-ons** → **Add-on Store**
   - Click the **⋮** menu in the top right
   - Select **Repositories**
   - Add: `https://github.com/chesterfield3/ha-energy-addon-repository`

2. Install the "HA Energy Data Analyzer" add-on

3. Configure the add-on (see Configuration section below)

4. Start the add-on

## Configuration

### Required Settings

```yaml
ha_url: "http://supervisor/core"  # Leave as default for add-on
ha_token: "your_long_lived_access_token_here"
```

### Optional Settings

```yaml
# Emporia Vue Integration (optional)
emporia_email: "your-emporia-email@example.com"
emporia_password: "your-emporia-password"

# Analysis Schedule
update_interval: 24  # Hours between updates (1-168)
log_level: "INFO"    # DEBUG, INFO, WARNING, ERROR
timezone: "America/Chicago"

# Email Notifications (optional)
enable_email_notifications: false
email_from: "your-email@gmail.com"
email_to: "notifications@example.com"
email_password: "your-gmail-app-password"
```

### Getting Your Home Assistant Token

1. In Home Assistant, go to your **Profile** (click your username)
2. Scroll down to **Long-lived access tokens**
3. Click **Create Token**
4. Give it a name like "Energy Analyzer"
5. Copy the token and paste it in the `ha_token` field

## Usage

Once configured and started, the add-on will:

1. **Automatically analyze** your energy data based on the update interval
2. **Generate reports** and save them to `/share/ha_energy_analyzer/`
3. **Provide a web interface** at `http://homeassistant:8080` for health monitoring
4. **Send email notifications** (if configured) with analysis results

### Output Files

The add-on creates analysis files in your Home Assistant `/share` folder:

- `energy_analysis.csv` - Detailed consumption data
- `energy_cost_analysis.png` - Cost visualization charts  
- `consumption_patterns.png` - Usage pattern analysis
- `monthly_summary.csv` - Aggregated monthly data

## Support

- 📋 [Create an Issue](https://github.com/chesterfield3/HA_Energy_Tracker/issues)
- 📖 [Full Documentation](https://github.com/chesterfield3/HA_Energy_Tracker)
- 💬 [Discussions](https://github.com/chesterfield3/HA_Energy_Tracker/discussions)

## Changelog & Releases

- **1.0.0** - Initial release with full energy analysis functionality

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg