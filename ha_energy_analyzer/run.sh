#!/usr/bin/with-contenv bashio

# Get configuration
export HA_URL=$(bashio::config 'ha_url')
export HA_TOKEN=$(bashio::config 'ha_token')
export EMPORIA_EMAIL=$(bashio::config 'emporia_email')
export EMPORIA_PASSWORD=$(bashio::config 'emporia_password')
export UPDATE_INTERVAL=$(bashio::config 'update_interval')
export LOG_LEVEL=$(bashio::config 'log_level')
export TZ=$(bashio::config 'timezone')

# Email configuration
export ENABLE_EMAIL=$(bashio::config 'enable_email_notifications')
export EMAIL_FROM=$(bashio::config 'email_from')
export EMAIL_TO=$(bashio::config 'email_to')
export EMAIL_PASSWORD=$(bashio::config 'email_password')

# Set paths for Home Assistant environment
export DATA_DIR="/share/ha_energy_analyzer"
export OUTPUT_DIR="/share/ha_energy_analyzer/output"
export CONFIG_DIR="/app/config"

# Create directories
mkdir -p "$DATA_DIR"
mkdir -p "$OUTPUT_DIR"

# Log configuration
bashio::log.info "Starting HA Energy Data Analyzer..."
bashio::log.info "Home Assistant URL: $HA_URL"
bashio::log.info "Update interval: $UPDATE_INTERVAL hours"
bashio::log.info "Log level: $LOG_LEVEL"
bashio::log.info "Timezone: $TZ"

# Validate required configuration
if bashio::var.is_empty "$HA_TOKEN"; then
    bashio::exit.nok "Home Assistant token is required!"
fi

# Change to app directory
cd /app

# Start the energy analyzer with health check server
exec python3 -m src.ha_energy_analyzer.main --addon-mode