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
# NOTE: No local PostgreSQL installation.
# The application connects to an RDS instance.
# Database credentials are injected via EC2 user data.
# ============================================

# ============================================
# 3. Create Application Linux Group
# ============================================
log "Creating application group..."
groupadd -f csye6225

# ============================================
# 4. Create Application User Account
# ============================================
log "Creating application user..."
if ! id -u csye6225 > /dev/null 2>&1; then
    useradd -r -g csye6225 -s /usr/sbin/nologin csye6225
    log "User csye6225 created"
else
    log "User csye6225 already exists"
fi

# ============================================
# 5. Deploy Application Files
# ============================================
log "Installing unzip..."
apt-get install -y unzip

log "Creating application directory..."
mkdir -p /opt/csye6225

log "Extracting application files..."
unzip -o /home/ubuntu/webapp.zip -d /opt/csye6225

# ============================================
# 6. Install Python Dependencies
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
# 7. Set File Permissions
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
# 8. Create Environment File (placeholder)
# Actual values will be injected by EC2 user data
# ============================================
log "Creating placeholder environment file..."
cat > /opt/csye6225/.env << EOF
# Database and S3 config will be injected by EC2 user data at launch
EOF

chown csye6225:csye6225 /opt/csye6225/.env
chmod 600 /opt/csye6225/.env
log "Environment file created with restricted permissions"

# ============================================
# 9. Create SystemD Service File
# ============================================
log "Creating SystemD service file..."

cat > /etc/systemd/system/csye6225.service << 'EOF'
[Unit]
Description=CSYE 6225 Web Application
After=network.target

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
# 10. Reload SystemD Daemon
# ============================================
log "Reloading SystemD daemon to recognize new service..."
systemctl daemon-reload

# ============================================
# 11. Enable Service (Start on Boot)
# ============================================
log "Enabling csye6225 service to start on boot..."
systemctl enable csye6225.service

# ============================================
# NOTE: Do NOT start the service here.
# The service will start automatically on boot
# when an instance is launched from this image.
# EC2 user data will write the .env file with
# real DB and S3 config before the service starts.
# ============================================

log "============================================"
log "Application setup completed successfully!"
log "============================================"
log ""
log "The csye6225 service is enabled and will start automatically on boot."
log "EC2 user data must inject DATABASE_HOST, DATABASE_PORT, DATABASE_NAME,"
log "DATABASE_USER, DATABASE_PASSWORD, and S3_BUCKET_NAME into /opt/csye6225/.env"
