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

# Start health check server in background
python3 health_server.py &

# Copy sensor configuration files to shared directory if they don't exist
if [ ! -f "$DATA_DIR/ha_sensors.csv" ] && [ -f "/app/data/ha_sensors.csv" ]; then
    bashio::log.info "Copying default sensor configuration files..."
    cp /app/data/*.csv "$DATA_DIR/" 2>/dev/null || true
    cp /app/data/*.template "$DATA_DIR/" 2>/dev/null || true
fi

# Check if this is the first run
FIRST_RUN=false
if [ ! -f "$DATA_DIR/output/energy_analysis.csv" ]; then
    FIRST_RUN=true
    bashio::log.info "🔍 First run detected - will perform initial historical data pull from Sept 27, 2025"
    bashio::log.info "⚠️ Initial pull may take 10-30 minutes depending on data volume"
else
    bashio::log.info "📊 Existing data found - will perform incremental updates"
fi

# Main loop - run analyzer every UPDATE_INTERVAL hours
RUN_COUNT=0
while true; do
    RUN_COUNT=$((RUN_COUNT + 1))
    
    if [ "$FIRST_RUN" = true ] && [ $RUN_COUNT -eq 1 ]; then
        bashio::log.info "🚀 Starting initial historical data pull (Run #$RUN_COUNT)..."
        bashio::log.info "📊 This will pull all data from September 27, 2025 to present"
    else
        bashio::log.info "🔄 Running incremental energy analysis (Run #$RUN_COUNT)..."
    fi
    
    # Run the non-interactive analyzer
    if python3 addon_runner.py; then
        if [ "$FIRST_RUN" = true ] && [ $RUN_COUNT -eq 1 ]; then
            bashio::log.info "✅ Initial historical data pull completed successfully!"
            bashio::log.info "📈 Subsequent runs will perform incremental updates"
            FIRST_RUN=false
        else
            bashio::log.info "✅ Incremental energy analysis completed successfully"
        fi
    else
        bashio::log.error "❌ Energy analysis failed (Run #$RUN_COUNT)"
    fi
    
    # Wait for next update interval (convert hours to seconds)
    SLEEP_SECONDS=$((UPDATE_INTERVAL * 3600))
    bashio::log.info "💤 Waiting ${UPDATE_INTERVAL} hours until next analysis..."
    sleep $SLEEP_SECONDS
done