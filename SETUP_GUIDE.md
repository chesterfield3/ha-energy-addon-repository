# 🏠 Home Assistant Add-on Repository Setup Guide

## 📋 What We Created

A complete Home Assistant Add-on repository structure that users can add directly to their Home Assistant Add-on Store. This provides a much easier installation method compared to manual deployment.

## 🚀 Setting Up the GitHub Repository

### Step 1: Create New GitHub Repository

1. Go to GitHub: https://github.com/new
2. **Repository name**: `ha-energy-addon-repository`
3. **Description**: "Home Assistant Add-on Repository for Energy Data Analyzer"
4. Make it **Public** (required for Home Assistant Add-on Store)
5. **Don't** initialize with README (we already have one)
6. Click **Create repository**

### Step 2: Push Your Add-on Repository

```powershell
# You're already in the ha-addon-repository directory
# Add the GitHub repository as origin
& "C:\Program Files\Git\bin\git.exe" remote add origin https://github.com/chesterfield3/ha-energy-addon-repository.git

# Push to GitHub
& "C:\Program Files\Git\bin\git.exe" push -u origin main
```

## 🏠 How Users Will Install Your Add-on

### Method 1: One-Click Installation (Recommended)

Users can click this button in your documentation:

[![Add Repository](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fchesterfield3%2Fha-energy-addon-repository)

### Method 2: Manual Installation

1. **Add Repository**:
   - Go to Settings → Add-ons → Add-on Store
   - Click ⋮ menu → Repositories
   - Add: `https://github.com/chesterfield3/ha-energy-addon-repository`

2. **Install Add-on**:
   - Find "HA Energy Data Analyzer" in the store
   - Click Install
   - Configure with Home Assistant token
   - Start the add-on

## ⚙️ Add-on Configuration

### Required Settings
```yaml
ha_url: "http://supervisor/core"  # Default - connects to local HA
ha_token: "your_long_lived_access_token"
```

### Optional Settings
```yaml
# Emporia Vue Integration
emporia_email: "your@email.com"
emporia_password: "your-password"

# Schedule & Logging
update_interval: 24  # Hours between updates
log_level: "INFO"
timezone: "America/Chicago"

# Email Notifications
enable_email_notifications: false
email_from: "your@gmail.com"
email_to: "notifications@example.com"  
email_password: "gmail-app-password"
```

## 📁 Repository Structure

```
ha-energy-addon-repository/
├── 📄 repository.json              # Repository metadata
├── 📖 README.md                    # Repository documentation
└── 📁 ha_energy_analyzer/          # Add-on directory
    ├── 📄 config.yaml              # Add-on configuration & UI schema
    ├── 📄 Dockerfile               # Container build instructions
    ├── 📄 build.json               # Multi-architecture build config
    ├── 📄 run.sh                   # Add-on startup script
    ├── 📖 README.md                # Add-on documentation
    ├── 📁 src/                     # Python source code
    ├── 📁 config/                  # Configuration templates
    ├── 📄 requirements.txt         # Python dependencies
    └── 📄 main.py                  # Entry point
```

## 🔧 Add-on Features

### ✅ **Home Assistant Integration**
- Uses `http://supervisor/core` for local HA API access
- No network configuration needed
- Secure token-based authentication

### ✅ **Multi-Architecture Support**
- ARM64 (Raspberry Pi 4, etc.)
- AMD64 (x86_64 systems)
- ARMv7 (Raspberry Pi 3, etc.)
- ARMhf (older ARM systems)
- i386 (32-bit x86)

### ✅ **User-Friendly Configuration**
- Configuration through Home Assistant UI
- Input validation and helpful descriptions
- Secure password fields for sensitive data

### ✅ **Data Persistence**
- Analysis results saved to `/share/ha_energy_analyzer/`
- Accessible through Home Assistant file manager
- Persistent across add-on restarts

### ✅ **Health Monitoring**
- Built-in health check endpoint
- Automatic restart on failure
- Logging integration with Home Assistant

## 🚀 Advanced SSH Access to Home Assistant

If you still need SSH access to your Home Assistant system:

### Option 1: Terminal & SSH Add-on
1. Install "Terminal & SSH" from the official add-on store
2. Configure with your SSH keys or password
3. Access via web terminal or SSH

### Option 2: SSH & Web Terminal Add-on
1. Go to Settings → Add-ons → Add-on Store
2. Search for "SSH & Web Terminal"
3. Install and configure

### Option 3: Advanced SSH Add-on
1. Add the community add-on repository:
   `https://github.com/hassio-addons/repository`
2. Install "SSH & Web Terminal" add-on
3. Configure with password or SSH keys

## 📝 Testing Your Add-on

### Local Testing
1. Use the add-on locally first
2. Check logs in Add-on → HA Energy Data Analyzer → Log
3. Verify files are created in `/share/ha_energy_analyzer/`
4. Test the health endpoint: `http://homeassistant:8080/health`

### Repository Validation
- Ensure repository.json is valid JSON
- Check that config.yaml follows Home Assistant schema
- Verify Dockerfile builds successfully
- Test multi-architecture compatibility

## 🔄 Updating Your Add-on

When you make changes:

1. **Update version** in `config.yaml`
2. **Commit and push** changes
3. **Users will see updates** in their Add-on Store
4. **Create releases** on GitHub for version tracking

## 🆘 Troubleshooting

### Common Issues
- **Add-on won't start**: Check Home Assistant token validity
- **No data generated**: Verify sensor names and availability
- **Permission errors**: Ensure `/share` directory is accessible
- **Build failures**: Check Dockerfile and dependencies

### Getting Help
- 📋 Create issues on your main repository
- 💬 Use Home Assistant community forums
- 📖 Check Home Assistant add-on development docs

Your users will now have a professional, easy-to-install Home Assistant add-on experience! 🎉