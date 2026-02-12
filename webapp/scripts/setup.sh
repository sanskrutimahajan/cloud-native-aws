#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root"
    echo "Please run: sudo ./setup.sh"
    exit 1
fi

# Log function for better visibility
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting application setup..."

# ============================================
# 1. Update Package Lists
# ============================================
log "Updating package lists..."
apt-get update -y

# ============================================
# 2. Upgrade System Packages
# ============================================
log "Upgrading system packages..."
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# ============================================
# 3. Install PostgreSQL
# ============================================
log "Installing PostgreSQL..."
apt-get install -y postgresql postgresql-contrib

# Start and enable PostgreSQL service
log "Starting PostgreSQL service..."
systemctl start postgresql
systemctl enable postgresql

# ============================================
# 4. Create Application Database and User
# ============================================
log "Creating database and database user..."

sudo -u postgres psql -c "CREATE USER webapp_user WITH PASSWORD 'webapp_pass123';" 2>/dev/null || log "User webapp_user already exists"
sudo -u postgres psql -c "CREATE DATABASE webapp_db OWNER webapp_user;" 2>/dev/null || log "Database webapp_db already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE webapp_db TO webapp_user;"

log "Database setup completed"

# ============================================
# 5. Create Application Linux Group
# ============================================
log "Creating application group..."
groupadd -f csye6225

# ============================================
# 6. Create Application User Account
# ============================================
log "Creating application user..."
if ! id -u csye6225 > /dev/null 2>&1; then
    useradd -r -g csye6225 -s /usr/sbin/nologin csye6225
    log "User csye6225 created"
else
    log "User csye6225 already exists"
fi

# ============================================
# 7. Deploy Application Files
# ============================================
log "Installing unzip..."
apt-get install -y unzip

log "Creating application directory..."
mkdir -p /opt/csye6225

log "Extracting application files..."
unzip -o /home/ubuntu/webapp.zip -d /opt/csye6225

# ============================================
# 8. Set File Permissions
# ============================================
log "Setting file permissions..."

# Change ownership to application user and group
chown -R csye6225:csye6225 /opt/csye6225

# Set directory permissions (755: owner can read/write/execute, others can read/execute)
find /opt/csye6225 -type d -exec chmod 755 {} \;

# Set file permissions (644: owner can read/write, others can only read)
find /opt/csye6225 -type f -exec chmod 644 {} \;

# Make run.py executable
chmod 755 /opt/csye6225/run.py

log "File permissions set successfully"

log "============================================"
log "Application setup completed successfully!"
log "============================================"
