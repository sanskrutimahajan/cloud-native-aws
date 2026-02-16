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
# 8. Install Python Dependencies
# ============================================
log "Installing Python pip and venv..."
apt-get install -y python3-pip python3-venv

log "Creating Python virtual environment..."
rm -rf /opt/csye6225/venv
python3 -m venv /opt/csye6225/venv

log "Installing Python dependencies..."
/opt/csye6225/venv/bin/pip install -r /opt/csye6225/requirements.txt

log "Python dependencies installed successfully"

# ============================================
# 9. Set File Permissions
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

# Restore execute permissions on venv binaries
find /opt/csye6225/venv/bin -type f -exec chmod 755 {} \;

log "File permissions set successfully"

# ============================================
# 10. Create Environment File
# ============================================
log "Creating environment file..."
cat > /opt/csye6225/.env << EOF
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=webapp_db
DATABASE_USER=webapp_user
DATABASE_PASSWORD=webapp_pass123
EOF

chown csye6225:csye6225 /opt/csye6225/.env
chmod 600 /opt/csye6225/.env
log "Environment file created with restricted permissions"

# ============================================
# 11. Create SystemD Service File
# ============================================
log "Creating SystemD service file..."

cat > /etc/systemd/system/csye6225.service << 'EOF'
[Unit]
Description=CSYE 6225 Web Application
After=network.target postgresql.service

[Service]
Type=simple
User=csye6225
Group=csye6225
WorkingDirectory=/opt/csye6225
EnvironmentFile=/opt/csye6225/.env
ExecStart=/opt/csye6225/venv/bin/python3 /opt/csye6225/run.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=csye6225

[Install]
WantedBy=multi-user.target
EOF

log "SystemD service file created at /etc/systemd/system/csye6225.service"

# ============================================
# 12. Reload SystemD Daemon
# ============================================
log "Reloading SystemD daemon to recognize new service..."
systemctl daemon-reload

# ============================================
# 13. Enable Service (Start on Boot)
# ============================================
log "Enabling csye6225 service to start on boot..."
systemctl enable csye6225.service

# ============================================
# 14. Start the Service
# ============================================
log "Starting csye6225 service..."
systemctl start csye6225.service

# ============================================
# 15. Verify Service Status
# ============================================
log "Verifying service status..."
sleep 2

if systemctl is-active --quiet csye6225.service; then
    log "Service is running successfully"
    systemctl status csye6225.service --no-pager -l
else
    log "WARNING: Service failed to start"
    log "Check logs with: sudo journalctl -u csye6225.service -n 50"
    systemctl status csye6225.service --no-pager -l
fi

log "============================================"
log "Application setup completed successfully!"
log "============================================"
log ""
log "Useful SystemD commands:"
log "  View status:  sudo systemctl status csye6225.service"
log "  Start:        sudo systemctl start csye6225.service"
log "  Stop:         sudo systemctl stop csye6225.service"
log "  Restart:      sudo systemctl restart csye6225.service"
log "  View logs:    sudo journalctl -u csye6225.service -f"
log "  Recent logs:  sudo journalctl -u csye6225.service -n 50"
