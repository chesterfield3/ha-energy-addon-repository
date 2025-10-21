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
if [ ! -f "$DATA_DIR/output/latest_analysis.csv" ]; then
    FIRST_RUN=true
    bashio::log.info "🔍 First run detected - will perform initial historical data pull from Sept 27, 2025"
    bashio::log.info "⚠️ Initial pull may take 10-30 minutes depending on data volume"
else
    bashio::log.info "📊 Existing data found - will perform incremental updates"
fi

# Function to calculate seconds until next 3:00 AM CT
calculate_sleep_until_3am() {
    local current_epoch=$(date +%s)
    local current_hour=$(TZ="America/Chicago" date +%H)
    local current_minute=$(TZ="America/Chicago" date +%M)
    local current_second=$(TZ="America/Chicago" date +%S)
    
    # Calculate seconds since midnight CT (force decimal interpretation with 10#)
    local seconds_since_midnight=$(( (10#$current_hour * 3600) + (10#$current_minute * 60) + 10#$current_second ))
    
    # Target time: 3:00 AM CT (3 * 3600 = 10800 seconds since midnight)
    local target_seconds=10800
    
    # Calculate seconds until next 3:00 AM
    if [ $seconds_since_midnight -lt $target_seconds ]; then
        # 3:00 AM is today
        local sleep_seconds=$(( target_seconds - seconds_since_midnight ))
    else
        # 3:00 AM is tomorrow (24 hours - current + target)
        local sleep_seconds=$(( 86400 - seconds_since_midnight + target_seconds ))
    fi
    
    echo $sleep_seconds
}

# Function to format sleep duration for display
format_sleep_duration() {
    local total_seconds=$1
    local hours=$(( total_seconds / 3600 ))
    local minutes=$(( (total_seconds % 3600) / 60 ))
    
    if [ $hours -gt 0 ]; then
        echo "${hours}h ${minutes}m"
    else
        echo "${minutes}m"
    fi
}

# Main loop - run analyzer, then wait until 3:00 AM CT
RUN_COUNT=0
while true; do
    RUN_COUNT=$((RUN_COUNT + 1))
    
    # Show current time in CT
    CURRENT_TIME_CT=$(TZ="America/Chicago" date '+%Y-%m-%d %H:%M:%S %Z')
    bashio::log.info "🕐 Current time: $CURRENT_TIME_CT"
    
    if [ "$FIRST_RUN" = true ] && [ $RUN_COUNT -eq 1 ]; then
        bashio::log.info "🚀 Starting initial historical data pull (Run #$RUN_COUNT)..."
        bashio::log.info "📊 This will pull all data from September 27, 2025 to present"
    else
        bashio::log.info "🔄 Running scheduled energy analysis (Run #$RUN_COUNT)..."
    fi
    
    # Run the non-interactive analyzer
    if python3 addon_runner.py; then
        if [ "$FIRST_RUN" = true ] && [ $RUN_COUNT -eq 1 ]; then
            bashio::log.info "✅ Initial historical data pull completed successfully!"
            bashio::log.info "📈 Subsequent runs will be scheduled daily at 3:00 AM CT"
            FIRST_RUN=false
        else
            bashio::log.info "✅ Scheduled energy analysis completed successfully"
        fi
    else
        bashio::log.error "❌ Energy analysis failed (Run #$RUN_COUNT)"
    fi
    
    # Calculate sleep time until next 3:00 AM CT
    SLEEP_SECONDS=$(calculate_sleep_until_3am)
    SLEEP_DURATION=$(format_sleep_duration $SLEEP_SECONDS)
    NEXT_RUN_TIME=$(TZ="America/Chicago" date -d "@$(($(date +%s) + SLEEP_SECONDS))" '+%Y-%m-%d %H:%M:%S %Z')
    
    bashio::log.info "💤 Next analysis scheduled for: $NEXT_RUN_TIME"
    bashio::log.info "⏰ Sleeping for $SLEEP_DURATION until 3:00 AM CT..."
    sleep $SLEEP_SECONDS
done