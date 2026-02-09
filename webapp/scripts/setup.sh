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

# Create database user with password
sudo -u postgres psql -c "CREATE USER webapp_user WITH PASSWORD 'your_secure_password_here';" 2>/dev/null || log "User webapp_user already exists"

# Create database
sudo -u postgres psql -c "CREATE DATABASE webapp_db OWNER webapp_user;" 2>/dev/null || log "Database webapp_db already exists"

# Grant privileges
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE webapp_db TO webapp_user;"

log "Database setup completed"

# ============================================
# 5. Install Python 3 and Dependencies
# ============================================
log "Installing Python 3 and pip..."
apt-get install -y python3 python3-pip python3-venv

# ============================================
# 6. Create Application Linux Group
# ============================================
log "Creating application group..."
groupadd -f csye6225

# ============================================
# 7. Create Application User Account
# ============================================
log "Creating application user..."
# Create system user (non-login) if it doesn't exist
if ! id -u csye6225 > /dev/null 2>&1; then
    useradd -r -g csye6225 -s /usr/sbin/nologin csye6225
    log "User csye6225 created"
else
    log "User csye6225 already exists"
fi

# ============================================
# 8. Create Application Directory
# ============================================
log "Creating application directory..."
mkdir -p /opt/csye6225

# ============================================
# 9. Deploy Application Files
# ============================================
log "Deploying application files..."

# Copy application files to /opt/csye6225/
# Assuming the script is run from the repository root
cp -r app/ /opt/csye6225/ 2>/dev/null || true
cp requirements.txt /opt/csye6225/ 2>/dev/null || true
cp run.py /opt/csye6225/ 2>/dev/null || true
cp README.md /opt/csye6225/ 2>/dev/null || true

# Create .env file (template - should be customized for production)
log "Creating environment configuration file..."
cat > /opt/csye6225/.env <<EOF
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=webapp_db
DATABASE_USER=webapp_user
DATABASE_PASSWORD=your_secure_password_here
APP_HOST=0.0.0.0
APP_PORT=8080
EOF

# ============================================
# 10. Create Python Virtual Environment
# ============================================
log "Creating Python virtual environment..."
python3 -m venv /opt/csye6225/venv

# ============================================
# 11. Install Python Dependencies
# ============================================
log "Installing Python dependencies in virtual environment..."
/opt/csye6225/venv/bin/pip install --upgrade pip
/opt/csye6225/venv/bin/pip install -r /opt/csye6225/requirements.txt

# ============================================
# 12. Set File Permissions
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

# Make venv binaries executable
chmod 755 /opt/csye6225/venv/bin/*

# Protect .env file (only owner can read/write)
chmod 600 /opt/csye6225/.env

log "File permissions set successfully"

# ============================================
# 13. Verify Installation
# ============================================
log "Verifying installation..."

# Check if PostgreSQL is running
if systemctl is-active --quiet postgresql; then
    log "[OK] PostgreSQL is running"
else
    log "[ERROR] PostgreSQL is not running"
    exit 1
fi

# Check if application directory exists
if [ -d "/opt/csye6225" ]; then
    log "[OK] Application directory exists"
else
    log "[ERROR] Application directory not found"
    exit 1
fi

# Check if user and group exist
if id -u csye6225 > /dev/null 2>&1; then
    log "[OK] Application user exists"
else
    log "[ERROR] Application user not found"
    exit 1
fi

# Check if virtual environment exists
if [ -f "/opt/csye6225/venv/bin/python" ]; then
    log "[OK] Python virtual environment created"
else
    log "[ERROR] Virtual environment not found"
    exit 1
fi

log "============================================"
log "Application setup completed successfully!"
log "============================================"
log ""
log "Application location: /opt/csye6225"
log "Application user: csye6225"
log "Application group: csye6225"
log "Database: webapp_db"
log "Database user: webapp_user"
log "Python virtual environment: /opt/csye6225/venv"
log ""
log "IMPORTANT: Update the database password in /opt/csye6225/.env"
log ""
log "To start the application manually:"
log "  sudo -u csye6225 /opt/csye6225/venv/bin/python /opt/csye6225/run.py"
