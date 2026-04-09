#!/bin/bash

set -e

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root"
    exit 1
fi

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting application setup..."

# ============================================
# 1. Update & Upgrade
# ============================================
log "Updating package lists..."
apt-get update -y
log "Upgrading system packages..."
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# ============================================
# 2. Create Application Group & User
# ============================================
log "Creating application group and user..."
groupadd -f csye6225
if ! id -u csye6225 > /dev/null 2>&1; then
    useradd -r -g csye6225 -s /usr/sbin/nologin csye6225
    log "User csye6225 created"
else
    log "User csye6225 already exists"
fi

# ============================================
# 3. Deploy Application Files
# ============================================
log "Installing unzip..."
apt-get install -y unzip

log "Creating application directory..."
mkdir -p /opt/csye6225

log "Extracting application files..."
unzip -o /home/ubuntu/webapp.zip -d /opt/csye6225

# ============================================
# 4. Install Python Dependencies
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
# 5. Create Log Directory
# ============================================
log "Creating application log directory..."
mkdir -p /var/log/webapp
chown csye6225:csye6225 /var/log/webapp
chmod 755 /var/log/webapp

# ============================================
# 6. Set File Permissions
# ============================================
log "Setting file permissions..."
chown -R csye6225:csye6225 /opt/csye6225
find /opt/csye6225 -type d -exec chmod 755 {} \;
find /opt/csye6225 -type f -exec chmod 644 {} \;
chmod 755 /opt/csye6225/run.py
find /opt/csye6225/venv/bin -type f -exec chmod 755 {} \;
log "File permissions set successfully"

# ============================================
# 7. Create Placeholder .env
# ============================================
log "Creating placeholder environment file..."
cat > /opt/csye6225/.env << EOF
# Database and S3 config will be injected by EC2 user data at launch
EOF
chown csye6225:csye6225 /opt/csye6225/.env
chmod 600 /opt/csye6225/.env

# ============================================
# 8. Create SystemD Service File
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

# ============================================
# 9. Install AWS CLI
# ============================================
log "Installing AWS CLI v2..."
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/awscliv2.zip /tmp/aws
log "AWS CLI installed successfully"

# ============================================
# 10. Install CloudWatch Agent
# ============================================
log "Downloading CloudWatch Unified Agent..."
wget -q https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb \
    -O /tmp/amazon-cloudwatch-agent.deb
log "Installing CloudWatch Agent..."
dpkg -i /tmp/amazon-cloudwatch-agent.deb
rm -f /tmp/amazon-cloudwatch-agent.deb
log "CloudWatch Agent installed successfully"

# ============================================
# 11. Copy CloudWatch Agent Configuration
# ============================================
log "Copying CloudWatch Agent configuration..."
cp /opt/csye6225/cloudwatch-config.json \
    /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
log "CloudWatch Agent configuration copied"

# ============================================
# 12. Enable Services
# ============================================
log "Reloading SystemD daemon..."
systemctl daemon-reload

log "Enabling csye6225 service..."
systemctl enable csye6225.service

log "Enabling CloudWatch Agent service..."
systemctl enable amazon-cloudwatch-agent.service

# ============================================
# NOTE: Do NOT start services here.
# EC2 user data will write .env, apply the
# CloudWatch config, and start both services.
# ============================================

log "============================================"
log "Application setup completed successfully!"
log "============================================"
log ""
log "Services enabled: csye6225, amazon-cloudwatch-agent"
log "EC2 user data must inject config and start services."
