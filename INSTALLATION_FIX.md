# 🔧 Add-on Installation Troubleshooting

## ✅ **Issue Fixed: Docker Registry Error**

### Problem
```
Failed to install add-on
Can't install ghcr.io/chesterfield3/ha-energy-analyzer:1.0.0: 403 Client Error
```

### ✅ **Solution Applied**
- Removed invalid Docker registry reference from `config.yaml`
- Add-on now builds locally using the Dockerfile
- No external registry dependencies

## 🚀 **How to Install Now**

### Step 1: Refresh the Repository
1. Go to **Settings** → **Add-ons** → **Add-on Store** 
2. Click **⋮** menu → **Check for updates**
3. Or remove and re-add the repository URL

### Step 2: Install the Add-on
1. Find "HA Energy Data Analyzer" in the add-on store
2. Click **Install** (it will now build locally)
3. Wait for the build to complete (may take a few minutes)

### Step 3: Configure
```yaml
ha_url: "http://supervisor/core"  # Leave as default
ha_token: "your_long_lived_access_token_here"
update_interval: 24
log_level: "INFO"
```

### Step 4: Start
1. Click **Start**
2. Check the **Log** tab for status messages
3. Health check available at port 8080

## 🔍 **What Changed**

### ✅ **Fixed Issues:**
- **Docker Build**: Now builds locally instead of pulling from registry
- **Health Monitoring**: Added HTTP health check endpoint
- **Sensor Files**: Automatically copies configuration templates
- **Continuous Operation**: Runs analysis every configured interval
- **Better Logging**: Uses Home Assistant logging system

### ✅ **New Features:**
- **Health Endpoint**: `http://your-ha:8080/health`
- **Automatic Setup**: Copies sensor templates on first run
- **Background Operation**: Runs continuously with scheduling
- **Shared Storage**: Results saved to `/share/ha_energy_analyzer/`

## 📊 **Sensor Configuration**

### After Installation:
1. Files will be copied to `/share/ha_energy_analyzer/`
2. Edit `ha_sensors.csv` with your actual sensor entity IDs
3. Edit `emporia_sensors.csv` for Emporia Vue sensors (optional)
4. Restart the add-on after configuration changes

### Template Files Available:
- `ha_sensors.csv.template` - Examples and instructions
- `emporia_sensors.csv.template` - Emporia Vue examples

## 🆘 **Still Having Issues?**

### Check Logs:
1. Add-on → HA Energy Data Analyzer → **Log** tab
2. Look for startup messages and error details

### Common Issues:
- **Missing Token**: Ensure Home Assistant long-lived access token is configured
- **Sensor Configuration**: Check that sensor entity IDs exist in Home Assistant
- **Build Time**: Initial installation may take 5-10 minutes to build

### Health Check:
- Visit `http://homeassistant:8080/health` to verify the add-on is running
- Should return JSON with status information

The add-on should now install and run successfully! 🎉