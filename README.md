# Home Assistant Energy Data Analyzer Add-on Repository

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fchesterfield3%2Fha-energy-addon-repository)

This repository contains Home Assistant add-ons for energy monitoring and analysis.

## Add-ons

This repository contains the following add-ons:

### 🏠 [HA Energy Data Analyzer](./ha_energy_analyzer)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

A comprehensive energy monitoring and analysis tool that seamlessly integrates with Home Assistant and Emporia Vue smart meters.

**Features:**
- 📊 Historical energy data analysis from Home Assistant sensors
- ⚡ Emporia Vue smart meter integration
- 🔄 Incremental data updates preserving historical records
- 📧 Email notifications and automated reporting
- 📈 Data visualization and cost analysis
- ⏰ Configurable automated scheduling

## Installation

Click the button below to add this repository to your Home Assistant instance:

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fchesterfield3%2Fha-energy-addon-repository)

**Or manually add the repository:**

1. Go to **Settings** → **Add-ons** → **Add-on Store**
2. Click the **⋮** menu in the top right corner
3. Select **Repositories**
4. Add this URL: `https://github.com/chesterfield3/ha-energy-addon-repository`
5. Click **Add**

## Usage

After adding the repository:

1. Find "HA Energy Data Analyzer" in your add-on store
2. Click **Install**
3. Configure the add-on with your Home Assistant token
4. Start the add-on
5. View your energy analysis results in `/share/ha_energy_analyzer/`

## Support

- 📋 [Create an Issue](https://github.com/chesterfield3/HA_Energy_Tracker/issues) 
- 📖 [Full Documentation](https://github.com/chesterfield3/HA_Energy_Tracker)
- 💬 [Community Discussions](https://github.com/chesterfield3/HA_Energy_Tracker/discussions)

## Development

This add-on repository is maintained as part of the [HA Energy Tracker](https://github.com/chesterfield3/HA_Energy_Tracker) project.

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg  
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg