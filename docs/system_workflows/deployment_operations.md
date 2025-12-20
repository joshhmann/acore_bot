# Deployment and Operations System Workflow

This document describes the complete deployment and operations system for acore_bot, including deployment procedures, operational workflows, maintenance tasks, and production management.

## Overview

The deployment and operations system provides **production-ready deployment** through **automated scripts**, **service management**, **monitoring integration**, and **operational procedures** for reliable bot operation.

## Architecture

### Component Structure
```
deployment/
├── scripts/
│   ├── install_service.sh    # Systemd service installation
│   ├── uninstall_service.sh  # Service removal
│   ├── deploy.sh            # Deployment automation
│   └── backup.sh            # Backup procedures
├── systemd/
│   └── acore_bot.service   # Systemd service definition
├── docker/
│   ├── Dockerfile           # Container definition
│   ├── docker-compose.yml   # Multi-container setup
│   └── nginx.conf          # Reverse proxy config
└── kubernetes/
    ├── deployment.yaml       # K8s deployment
    ├── service.yaml          # K8s service
    └── configmap.yaml        # K8s configuration

operations/
├── monitoring/
│   ├── health_checks.py     # Health monitoring
│   ├── log_rotation.py     # Log management
│   └── backup_manager.py   # Backup automation
├── maintenance/
│   ├── update_bot.py       # Update procedures
│   ├── cleanup.py          # Resource cleanup
│   └── recovery.py         # Disaster recovery
└── security/
    ├── cert_manager.py      # SSL certificate management
    ├── access_control.py    # Access management
    └── audit_logger.py     # Security auditing
```

### Service Dependencies
```
Deployment Dependencies:
├── Systemd                # Service management
├── Docker                 # Container runtime
├── Nginx                  # Reverse proxy
├── SSL/TLS                # Certificate management
├── Process Supervisor       # Process monitoring
├── Log Rotation           # Log management
├── Backup Services        # Automated backups
└── Monitoring             # Health and performance
```

## Deployment Procedures

### 1. Systemd Service Installation
**File**: `deployment/scripts/install_service.sh:23-156`

#### 1.1 Service Installation Script
```bash
#!/bin/bash
# acore_bot Systemd Service Installation Script

set -e

# Configuration
BOT_USER="acore_bot"
BOT_DIR="/opt/acore_bot"
SERVICE_FILE="/etc/systemd/system/acore_bot.service"
CONFIG_FILE="/etc/acore_bot/.env"
LOG_DIR="/var/log/acore_bot"
DATA_DIR="/var/lib/acore_bot"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log "${RED}Error: This script must be run as root${NC}"
        exit 1
    fi
}

# Create bot user
create_user() {
    log "${YELLOW}Creating bot user...${NC}"

    if ! id "$BOT_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$BOT_DIR" "$BOT_USER"
        log "${GREEN}✓ User $BOT_USER created${NC}"
    else
        log "${YELLOW}⚠ User $BOT_USER already exists${NC}"
    fi
}

# Install dependencies
install_dependencies() {
    log "${YELLOW}Installing dependencies...${NC}"

    # Update package lists
    apt-get update

    # Install Python and tools
    apt-get install -y python3 python3-pip python3-venv git curl wget

    # Install system dependencies
    apt-get install -y ffmpeg sqlite3 systemd-container

    # Install uv (Python package manager)
    if ! command -v uv &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
    fi

    log "${GREEN}✓ Dependencies installed${NC}"
}

# Setup directories
setup_directories() {
    log "${YELLOW}Setting up directories...${NC}"

    # Create directories
    mkdir -p "$BOT_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$(dirname "$CONFIG_FILE")"

    # Set permissions
    chown -R "$BOT_USER:$BOT_USER" "$BOT_DIR"
    chown -R "$BOT_USER:$BOT_USER" "$LOG_DIR"
    chown -R "$BOT_USER:$BOT_USER" "$DATA_DIR"
    chown -R "$BOT_USER:$BOT_USER" "$(dirname "$CONFIG_FILE")"

    log "${GREEN}✓ Directories created and permissions set${NC}"
}

# Clone or update bot code
setup_code() {
    log "${YELLOW}Setting up bot code...${NC}"

    # Backup existing code if present
    if [[ -d "$BOT_DIR/.git" ]]; then
        cd "$BOT_DIR"
        sudo -u "$BOT_USER" git pull
    else
        # Clone fresh copy
        sudo -u "$BOT_USER" git clone https://github.com/your-org/acore_bot.git "$BOT_DIR"
        cd "$BOT_DIR"
    fi

    # Install Python dependencies
    sudo -u "$BOT_USER" uv sync

    log "${GREEN}✓ Bot code updated and dependencies installed${NC}"
}

# Create configuration file
create_config() {
    log "${YELLOW}Creating configuration...${NC}"

    if [[ ! -f "$CONFIG_FILE" ]]; then
        cat > "$CONFIG_FILE" << 'EOF'
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_token_here
COMMAND_PREFIX=!

# LLM Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_TEMPERATURE=1.17

# Bot Configuration
CHAT_HISTORY_ENABLED=true
USER_PROFILES_ENABLED=true
VOICE_ENABLED=true

# Data Directories
DATA_DIR=/var/lib/acore_bot
LOG_DIR=/var/log/acore_bot

# Production Settings
LOG_LEVEL=INFO
METRICS_ENABLED=true
HEALTH_CHECK_ENABLED=true
EOF

        # Set permissions
        chown "$BOT_USER:$BOT_USER" "$CONFIG_FILE"
        chmod 600 "$CONFIG_FILE"

        log "${GREEN}✓ Configuration file created at $CONFIG_FILE${NC}"
        log "${YELLOW}⚠ Please edit $CONFIG_FILE with your bot token${NC}"
    else
        log "${YELLOW}⚠ Configuration file already exists${NC}"
    fi
}

# Create systemd service
create_service() {
    log "${YELLOW}Creating systemd service...${NC}"

    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=acore_bot Discord Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=$BOT_USER
Group=$BOT_USER
WorkingDirectory=$BOT_DIR
Environment=PATH=$BOT_DIR/.venv/bin
EnvironmentFile=$CONFIG_FILE
ExecStart=$BOT_DIR/.venv/bin/python main.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=acore_bot

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$DATA_DIR
ReadWritePaths=$LOG_DIR

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable acore_bot

    log "${GREEN}✓ Systemd service created and enabled${NC}"
}

# Setup log rotation
setup_log_rotation() {
    log "${YELLOW}Setting up log rotation...${NC}"

    cat > "/etc/logrotate.d/acore_bot" << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $BOT_USER $BOT_USER
    postrotate
        systemctl reload acore_bot || true
    endscript
}
EOF

    log "${GREEN}✓ Log rotation configured${NC}"
}

# Health check script
setup_health_check() {
    log "${YELLOW}Setting up health check...${NC}"

    cat > "$BOT_DIR/health_check.py" << 'EOF'
#!/usr/bin/env python3
"""Health check script for acore_bot"""

import aiohttp
import asyncio
import os
import sys

async def check_health():
    try:
        # Check if bot process is running
        with open('/var/run/acore_bot.pid', 'r') as f:
            pid = int(f.read().strip())

        os.kill(pid, 0)  # Check if process exists

        # Check HTTP health endpoint if available
        port = os.getenv('HEALTH_CHECK_PORT', '8080')

        async with aiohttp.ClientSession() as session:
            async with session.get(f'http://localhost:{port}/health', timeout=5) as response:
                if response.status == 200:
                    print("OK")
                    return True
    except:
        pass

    print("UNHEALTHY")
    return False

if __name__ == "__main__":
    result = asyncio.run(check_health())
    sys.exit(0 if result else 1)
EOF

    chmod +x "$BOT_DIR/health_check.py"
    chown "$BOT_USER:$BOT_USER" "$BOT_DIR/health_check.py"

    log "${GREEN}✓ Health check script created${NC}"
}

# Main installation function
main() {
    log "${GREEN}Starting acore_bot installation...${NC}"

    check_root
    create_user
    install_dependencies
    setup_directories
    setup_code
    create_config
    create_service
    setup_log_rotation
    setup_health_check

    log "${GREEN}✓ Installation completed successfully!${NC}"
    log "${YELLOW}Next steps:${NC}"
    log "1. Edit $CONFIG_FILE with your Discord bot token"
    log "2. Start the service: systemctl start acore_bot"
    log "3. Check status: systemctl status acore_bot"
    log "4. View logs: journalctl -u acore_bot -f"
}

# Run main function
main "$@"
```

### 2. Docker Deployment
**File**: `deployment/docker/Dockerfile:34-89`

#### 2.1 Container Definition
```dockerfile
# acore_bot Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    sqlite3 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for Python package management
RUN pip install uv

# Create app user
RUN useradd --create-home --shell /bin/bash acore_bot

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./

# Install Python dependencies
RUN uv sync --frozen

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/temp && \
    chown -R acore_bot:acore_bot /app

# Switch to app user
USER acore_bot

# Expose health check port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python health_check.py

# Start the bot
CMD ["uv", "run", "python", "main.py"]
```

### 3. Docker Compose Setup
**File**: `deployment/docker/docker-compose.yml:45-123`

#### 3.1 Multi-Container Configuration
```yaml
version: '3.8'

services:
  acore_bot:
    build:
      context: ..
      dockerfile: deployment/docker/Dockerfile
    container_name: acore_bot
    restart: unless-stopped
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - OLLAMA_HOST=ollama:11434
      - OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.2}
      - DATA_DIR=/app/data
      - LOG_DIR=/app/logs
    volumes:
      - acore_bot_data:/app/data
      - acore_bot_logs:/app/logs
      - acore_bot_temp:/app/temp
    depends_on:
      - ollama
      - redis
    networks:
      - acore_bot_network
    healthcheck:
      test: ["CMD", "python", "health_check.py"]
      interval: 30s
      timeout: 10s
      retries: 3

  ollama:
    image: ollama/ollama:latest
    container_name: acore_bot_ollama
    restart: unless-stopped
    volumes:
      - ollama_models:/root/.ollama
    ports:
      - "11434:11434"
    networks:
      - acore_bot_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: acore_bot_redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - acore_bot_network
    command: redis-server --appendonly yes --aof-use-rdb-preamble yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: acore_bot_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - acore_bot
    networks:
      - acore_bot_network

volumes:
  acore_bot_data:
    driver: local
  acore_bot_logs:
    driver: local
  acore_bot_temp:
    driver: local
  ollama_models:
    driver: local
  redis_data:
    driver: local

networks:
  acore_bot_network:
    driver: bridge
```

## Operational Procedures

### 1. Health Monitoring
**File**: `operations/monitoring/health_checks.py:34-145`

#### 1.1 Comprehensive Health Monitoring
```python
#!/usr/bin/env python3
"""Comprehensive health monitoring for acore_bot."""

import asyncio
import aiohttp
import psutil
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import json

class HealthMonitor:
    """Comprehensive health monitoring system."""

    def __init__(self):
        self.config = self._load_config()
        self.health_results = {}
        self.alert_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'disk_usage': 90.0,
            'response_time': 5.0,
            'error_rate': 0.05
        }

    async def run_health_checks(self) -> Dict:
        """Run all health checks."""

        print("🔍 Starting comprehensive health check...")

        checks = {
            'system_resources': await self._check_system_resources(),
            'process_health': await self._check_process_health(),
            'database_health': await self._check_database_health(),
            'external_services': await self._check_external_services(),
            'disk_space': await self._check_disk_space(),
            'memory_usage': await self._check_memory_usage(),
            'network_connectivity': await self._check_network_connectivity(),
            'log_errors': await self._check_log_errors(),
            'service_dependencies': await self._check_service_dependencies()
        }

        # Calculate overall health
        overall_status = self._calculate_overall_health(checks)
        checks['overall_status'] = overall_status

        # Save results
        await self._save_health_results(checks)

        # Send alerts if needed
        await self._send_alerts(checks)

        return checks

    async def _check_system_resources(self) -> Dict:
        """Check system resource usage."""

        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_cores = psutil.cpu_count()

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Load average
            load_avg = psutil.getloadavg()

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100

            result = {
                'status': 'healthy',
                'cpu_usage': cpu_percent,
                'cpu_cores': cpu_cores,
                'memory_usage': memory_percent,
                'memory_total_gb': memory.total / (1024**3),
                'memory_used_gb': memory.used / (1024**3),
                'disk_usage': disk_percent,
                'disk_total_gb': disk.total / (1024**3),
                'disk_used_gb': disk.used / (1024**3),
                'load_average': {
                    '1min': load_avg[0],
                    '5min': load_avg[1],
                    '15min': load_avg[2]
                }
            }

            # Check thresholds
            if cpu_percent > self.alert_thresholds['cpu_usage']:
                result['status'] = 'warning'
                result['cpu_alert'] = f"CPU usage {cpu_percent}% exceeds threshold"

            if memory_percent > self.alert_thresholds['memory_usage']:
                result['status'] = 'warning'
                result['memory_alert'] = f"Memory usage {memory_percent}% exceeds threshold"

            if disk_percent > self.alert_thresholds['disk_usage']:
                result['status'] = 'critical'
                result['disk_alert'] = f"Disk usage {disk_percent}% exceeds threshold"

            return result

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'message': 'Failed to check system resources'
            }

    async def _check_process_health(self) -> Dict:
        """Check bot process health."""

        try:
            # Check if main process is running
            pid_file = Path('/var/run/acore_bot.pid')

            if not pid_file.exists():
                return {
                    'status': 'critical',
                    'message': 'PID file not found - process may not be running'
                }

            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())

            # Check if process exists
            try:
                process = psutil.Process(pid)

                # Get process info
                process_info = {
                    'pid': pid,
                    'status': process.status(),
                    'cpu_percent': process.cpu_percent(),
                    'memory_mb': process.memory_info().rss / (1024**2),
                    'create_time': datetime.fromtimestamp(process.create_time()),
                    'uptime_seconds': (datetime.now() - datetime.fromtimestamp(process.create_time())).total_seconds()
                }

                # Check if process is responsive
                if self.config.get('health_check_port'):
                    responsive = await self._check_process_responsiveness()
                    process_info['responsive'] = responsive
                else:
                    process_info['responsive'] = True

                result = {
                    'status': 'healthy' if process_info['responsive'] else 'critical',
                    'process': process_info
                }

                if not process_info['responsive']:
                    result['message'] = 'Process is running but not responding'

                return result

            except psutil.NoSuchProcess:
                return {
                    'status': 'critical',
                    'message': f'Process with PID {pid} not found'
                }

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'message': 'Failed to check process health'
            }

    async def _check_database_health(self) -> Dict:
        """Check database connectivity and integrity."""

        try:
            db_path = Path(self.config.get('database_path', './data/bot.db'))

            if not db_path.exists():
                return {
                    'status': 'warning',
                    'message': 'Database file not found'
                }

            # Test database connection
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Basic query test
            cursor.execute("SELECT 1")
            test_result = cursor.fetchone()

            # Check database integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()

            # Get database stats
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]

            # Get database size
            db_size = db_path.stat().st_size / (1024**2)  # MB

            conn.close()

            result = {
                'status': 'healthy',
                'database_path': str(db_path),
                'table_count': table_count,
                'size_mb': db_size,
                'integrity_check': integrity_result[0] if integrity_result else 'ok',
                'connectivity': 'ok'
            }

            if integrity_result and integrity_result[0] != 'ok':
                result['status'] = 'critical'
                result['message'] = f'Database integrity issue: {integrity_result[0]}'

            return result

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'message': 'Database health check failed'
            }

    async def _check_external_services(self) -> Dict:
        """Check external service dependencies."""

        services = {}

        # Check Ollama
        try:
            ollama_host = self.config.get('ollama_host', 'http://localhost:11434')

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ollama_host}/api/tags", timeout=5) as response:
                    if response.status == 200:
                        services['ollama'] = {
                            'status': 'healthy',
                            'response_time': response.headers.get('X-Response-Time', 'unknown')
                        }
                    else:
                        services['ollama'] = {
                            'status': 'unhealthy',
                            'error': f'HTTP {response.status}'
                        }
        except Exception as e:
            services['ollama'] = {
                'status': 'error',
                'error': str(e)
            }

        # Check Discord API connectivity
        try:
            if self.config.get('discord_token'):
                async with aiohttp.ClientSession() as session:
                    headers = {'Authorization': f'Bot {self.config["discord_token"]}'}
                    async with session.get('https://discord.com/api/v10/users/@me',
                                         headers=headers, timeout=5) as response:
                        if response.status == 200:
                            services['discord_api'] = {
                                'status': 'healthy',
                                'response_time': response.headers.get('X-Response-Time', 'unknown')
                            }
                        else:
                            services['discord_api'] = {
                                'status': 'unhealthy',
                                'error': f'HTTP {response.status}'
                            }
            else:
                services['discord_api'] = {
                    'status': 'warning',
                    'message': 'Discord token not configured'
                }
        except Exception as e:
            services['discord_api'] = {
                'status': 'error',
                'error': str(e)
            }

        # Calculate overall status
        overall_status = 'healthy'
        for service_name, service_info in services.items():
            if service_info['status'] == 'error':
                overall_status = 'error'
            elif service_info['status'] == 'unhealthy':
                overall_status = 'unhealthy'
            elif service_info['status'] == 'warning' and overall_status == 'healthy':
                overall_status = 'warning'

        return {
            'status': overall_status,
            'services': services
        }

    async def _send_alerts(self, health_results: Dict):
        """Send alerts for health issues."""

        alerts = []

        # Check for critical issues
        for check_name, result in health_results.items():
            if check_name == 'overall_status':
                continue

            if isinstance(result, dict) and result.get('status') == 'critical':
                alerts.append({
                    'level': 'critical',
                    'check': check_name,
                    'message': result.get('message', 'Critical health issue detected'),
                    'timestamp': datetime.now().isoformat()
                })
            elif isinstance(result, dict) and result.get('status') == 'error':
                alerts.append({
                    'level': 'error',
                    'check': check_name,
                    'message': result.get('message', 'Health check error'),
                    'timestamp': datetime.now().isoformat()
                })

        # Send alerts if any
        if alerts:
            await self._send_alert_notifications(alerts)

    async def _send_alert_notifications(self, alerts: List[Dict]):
        """Send alert notifications through configured channels."""

        for alert in alerts:
            # Log alert
            print(f"🚨 {alert['level'].upper()}: {alert['message']} (check: {alert['check']})")

            # Send to webhook if configured
            if self.config.get('alert_webhook_url'):
                await self._send_webhook_alert(alert)

            # Send email if configured
            if self.config.get('alert_email'):
                await self._send_email_alert(alert)

# Main execution
async def main():
    """Main health check execution."""

    monitor = HealthMonitor()
    results = await monitor.run_health_checks()

    # Output results
    print("\n📊 Health Check Results:")
    print(f"Overall Status: {results['overall_status'].upper()}")

    for check_name, result in results.items():
        if check_name == 'overall_status':
            continue

        status_emoji = {
            'healthy': '✅',
            'warning': '⚠️',
            'error': '❌',
            'critical': '🔴'
        }

        emoji = status_emoji.get(result.get('status', 'unknown'), '❓')
        print(f"{emoji} {check_name}: {result.get('status', 'unknown')}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Backup Management
**File**: `operations/monitoring/backup_manager.py:45-189`

#### 2.1 Automated Backup System
```python
#!/usr/bin/env python3
"""Automated backup management for acore_bot."""

import asyncio
import shutil
import tarfile
import gzip
from pathlib import Path
from datetime import datetime
import json
import subprocess

class BackupManager:
    """Automated backup management system."""

    def __init__(self):
        self.config = self._load_config()
        self.backup_dir = Path(self.config.get('backup_dir', './backups'))
        self.data_dir = Path(self.config.get('data_dir', './data'))
        self.max_backups = self.config.get('max_backups', 30)

    async def create_backup(self, backup_type: str = 'full') -> Dict:
        """Create a backup of bot data."""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"acore_bot_{backup_type}_{timestamp}"
        backup_path = self.backup_dir / backup_name

        print(f"🔄 Creating {backup_type} backup: {backup_name}")

        try:
            # Create backup directory
            backup_path.mkdir(parents=True, exist_ok=True)

            # Backup different components based on type
            if backup_type == 'full':
                await self._backup_full(backup_path)
            elif backup_type == 'incremental':
                await self._backup_incremental(backup_path)
            elif backup_type == 'config_only':
                await self._backup_config_only(backup_path)

            # Create backup metadata
            metadata = await self._create_backup_metadata(backup_type, backup_path)

            # Compress backup
            compressed_path = await self._compress_backup(backup_path)

            # Create backup manifest
            manifest = {
                'backup_name': backup_name,
                'backup_type': backup_type,
                'created_at': datetime.now().isoformat(),
                'size_bytes': compressed_path.stat().st_size,
                'files_count': len(list(backup_path.rglob('*'))),
                'metadata': metadata
            }

            manifest_path = backup_path / 'manifest.json'
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)

            # Update latest backup symlink
            await self._update_latest_backup(compressed_path)

            # Clean up old backups
            await self._cleanup_old_backups()

            print(f"✅ Backup completed: {compressed_path}")

            return {
                'success': True,
                'backup_path': str(compressed_path),
                'backup_name': backup_name,
                'size_bytes': compressed_path.stat().st_size,
                'manifest': manifest
            }

        except Exception as e:
            print(f"❌ Backup failed: {e}")

            # Clean up failed backup
            if backup_path.exists():
                shutil.rmtree(backup_path)

            return {
                'success': False,
                'error': str(e)
            }

    async def _backup_full(self, backup_path: Path):
        """Create full backup of all data."""

        components = [
            ('data', self.data_dir),
            ('config', Path('./.env')),
            ('logs', Path('./logs')),
            ('models', Path('./models')),
            ('prompts', Path('./prompts'))
        ]

        for component_name, source_path in components:
            if source_path.exists():
                dest_path = backup_path / component_name

                if source_path.is_file():
                    shutil.copy2(source_path, dest_path)
                else:
                    shutil.copytree(source_path, dest_path, ignore=shutil.ignore_patterns('*.pyc', '__pycache__', '.git'))

                print(f"  📁 Backed up {component_name}")

    async def _backup_incremental(self, backup_path: Path):
        """Create incremental backup (files changed since last backup)."""

        # Get last backup time
        last_backup_time = await self._get_last_backup_time()

        if not last_backup_time:
            print("⚠️ No previous backup found, creating full backup instead")
            await self._backup_full(backup_path)
            return

        # Find files modified since last backup
        modified_files = []

        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                file_path = Path(root) / file
                file_mtime = file_path.stat().st_mtime

                if file_mtime > last_backup_time:
                    modified_files.append(file_path)

        if not modified_files:
            print("ℹ️ No files modified since last backup")
            return

        # Copy modified files
        for file_path in modified_files:
            relative_path = file_path.relative_to(self.data_dir)
            dest_path = backup_path / 'data' / relative_path

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dest_path)

        print(f"📁 Backed up {len(modified_files)} modified files")

    async def _backup_config_only(self, backup_path: Path):
        """Create configuration-only backup."""

        config_files = [
            ('.env', Path('./.env')),
            ('config.py', Path('./config.py')),
            ('pyproject.toml', Path('./pyproject.toml')),
            ('prompts', Path('./prompts'))
        ]

        for file_name, source_path in config_files:
            if source_path.exists():
                dest_path = backup_path / file_name

                if source_path.is_file():
                    shutil.copy2(source_path, dest_path)
                else:
                    shutil.copytree(source_path, dest_path, ignore=shutil.ignore_patterns('*.pyc', '__pycache__'))

                print(f"  📄 Backed up {file_name}")

    async def _compress_backup(self, backup_path: Path) -> Path:
        """Compress backup directory."""

        compressed_path = backup_path.with_suffix('.tar.gz')

        print("🗜️ Compressing backup...")

        with tarfile.open(compressed_path, 'w:gz') as tar:
            tar.add(backup_path, arcname=backup_path.name)

        # Remove uncompressed directory
        shutil.rmtree(backup_path)

        print(f"  📦 Compressed to {compressed_path.name} "
              f"({compressed_path.stat().st_size / (1024**2):.1f} MB)")

        return compressed_path

    async def restore_backup(self, backup_name: str) -> Dict:
        """Restore from backup."""

        backup_path = self.backup_dir / backup_name

        if not backup_path.exists():
            backup_path = backup_path.with_suffix('.tar.gz')

        if not backup_path.exists():
            return {
                'success': False,
                'error': f'Backup {backup_name} not found'
            }

        print(f"🔄 Restoring from backup: {backup_name}")

        try:
            # Extract backup
            if backup_path.suffix == '.gz':
                with tarfile.open(backup_path, 'r:gz') as tar:
                    tar.extractall(self.backup_dir)

                extracted_path = self.backup_dir / backup_path.stem
            else:
                extracted_path = backup_path

            # Read manifest
            manifest_path = extracted_path / 'manifest.json'
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            # Confirm restore
            print(f"📋 Backup info:")
            print(f"  Type: {manifest['backup_type']}")
            print(f"  Created: {manifest['created_at']}")
            print(f"  Size: {manifest['size_bytes'] / (1024**2):.1f} MB")

            # Perform restore based on type
            if manifest['backup_type'] == 'full':
                await self._restore_full(extracted_path)
            elif manifest['backup_type'] == 'incremental':
                await self._restore_incremental(extracted_path)
            elif manifest['backup_type'] == 'config_only':
                await self._restore_config_only(extracted_path)

            print(f"✅ Restore completed from {backup_name}")

            return {
                'success': True,
                'backup_name': backup_name,
                'restored_at': datetime.now().isoformat(),
                'manifest': manifest
            }

        except Exception as e:
            print(f"❌ Restore failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _cleanup_old_backups(self):
        """Remove old backups exceeding retention limit."""

        backup_files = list(self.backup_dir.glob('*.tar.gz'))

        if len(backup_files) <= self.max_backups:
            return

        # Sort by modification time (newest first)
        backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Remove oldest backups
        files_to_remove = backup_files[self.max_backups:]

        for backup_file in files_to_remove:
            backup_file.unlink()
            print(f"  🗑️ Removed old backup: {backup_file.name}")

# Main execution
async def main():
    """Main backup management."""

    manager = BackupManager()

    # Parse command line arguments
    import sys

    if len(sys.argv) < 2:
        print("Usage: python backup_manager.py <command> [args]")
        print("Commands:")
        print("  create [full|incremental|config_only] - Create backup")
        print("  restore <backup_name> - Restore from backup")
        print("  list - List available backups")
        print("  cleanup - Clean old backups")
        return

    command = sys.argv[1]

    if command == 'create':
        backup_type = sys.argv[2] if len(sys.argv) > 2 else 'full'
        result = await manager.create_backup(backup_type)

    elif command == 'restore':
        if len(sys.argv) < 3:
            print("Error: backup name required for restore")
            return

        backup_name = sys.argv[2]
        result = await manager.restore_backup(backup_name)

    elif command == 'list':
        await manager.list_backups()

    elif command == 'cleanup':
        await manager.cleanup_old_backups()

    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

### Deployment Settings
```bash
# Service Configuration
SERVICE_NAME=acore_bot                          # Systemd service name
SERVICE_USER=acore_bot                         # Service user
SERVICE_GROUP=acore_bot                        # Service group
BOT_DIR=/opt/acore_bot                         # Installation directory
DATA_DIR=/var/lib/acore_bot                     # Data directory
LOG_DIR=/var/log/acore_bot                        # Log directory

# Process Management
PID_FILE=/var/run/acore_bot.pid               # PID file location
HEALTH_CHECK_PORT=8080                        # Health check port
HEALTH_CHECK_INTERVAL=30                       # Health check interval (seconds)

# Backup Configuration
BACKUP_ENABLED=true                            # Enable automated backups
BACKUP_DIR=/var/backups/acore_bot             # Backup storage directory
BACKUP_SCHEDULE=0 2 * * *                     # Daily at 2 AM (cron format)
BACKUP_TYPE=full                               # Backup type (full, incremental, config_only)
MAX_BACKUPS=30                                 # Maximum backups to retain
BACKUP_RETENTION_DAYS=30                        # Days to keep backups

# Monitoring Configuration
MONITORING_ENABLED=true                         # Enable health monitoring
MONITORING_INTERVAL=300                         # Monitoring check interval (seconds)
ALERT_WEBHOOK_URL=                            # Webhook for alerts
ALERT_EMAIL=                                  # Email for alerts
LOG_ROTATION_ENABLED=true                      # Enable log rotation
LOG_RETENTION_DAYS=30                          # Days to keep logs

# Security Configuration
SSL_ENABLED=true                               # Enable SSL/TLS
SSL_CERT_PATH=/etc/ssl/certs/acore_bot.crt    # SSL certificate path
SSL_KEY_PATH=/etc/ssl/private/acore_bot.key    # SSL private key path
FIREWALL_ENABLED=true                         # Enable firewall rules

# Performance Configuration
WORKER_PROCESSES=4                            # Number of worker processes
MAX_MEMORY_LIMIT=2048                          # Maximum memory limit (MB)
CPU_LIMIT=80                                   # CPU usage limit (%)
MAX_RESPONSE_TIME=30                            # Maximum response time (seconds)

# Update Configuration
AUTO_UPDATE_ENABLED=false                       # Enable automatic updates
UPDATE_SCHEDULE=0 3 * * 1                     # Update schedule (cron format)
UPDATE_CHANNEL=stable                           # Update channel (stable, beta, dev)
ROLLBACK_ENABLED=true                           # Enable rollback capability
```

## Integration Points

### With System Services
- **Systemd Integration**: Service management and lifecycle
- **Log Management**: Integration with journald and logrotate
- **Resource Monitoring**: System resource tracking

### With Container Platforms
- **Docker Support**: Containerized deployment
- **Kubernetes Support**: Orchestration for large deployments
- **Docker Compose**: Multi-container development setups

### With Monitoring Systems
- **Health Checks**: Service health monitoring
- **Metrics Collection**: Performance data collection
- **Alert Integration**: External monitoring systems

## Performance Considerations

### 1. Resource Management
- **Memory Limits**: Bounded memory usage
- **CPU Throttling**: Prevent resource exhaustion
- **I/O Optimization**: Efficient file operations

### 2. Service Reliability
- **Process Monitoring**: Automatic restart on failures
- **Health Checks**: Continuous health monitoring
- **Graceful Shutdown**: Proper cleanup on shutdown

### 3. Backup Performance
- **Incremental Backups**: Efficient backup strategies
- **Compression Optimization**: Balance compression ratio vs speed
- **Parallel Operations**: Concurrent backup operations

## Security Considerations

### 1. Service Security
- **User Isolation**: Non-root service execution
- **File Permissions**: Restricted file access
- **Network Security**: Firewall rules and SSL/TLS

### 2. Data Protection
- **Encryption**: Encrypted backup storage
- **Access Control**: Role-based access to backups
- **Audit Logging**: Comprehensive audit trails

### 3. Operational Security
- **Secret Management**: Secure credential storage
- **Update Security**: Verified update procedures
- **Incident Response**: Security incident handling

## Common Issues and Troubleshooting

### 1. Service Not Starting
```bash
# Check service status
systemctl status acore_bot

# View service logs
journalctl -u acore_bot -n 50

# Check configuration
systemd-analyze verify /etc/systemd/system/acore_bot.service
```

### 2. Health Checks Failing
```python
# Run manual health check
python operations/monitoring/health_checks.py

# Check specific components
curl -f http://localhost:8080/health

# Check system resources
top -p $(pgrep -f acore_bot)
```

### 3. Backup Issues
```bash
# Check backup directory
ls -la /var/backups/acore_bot/

# Test backup creation
python operations/monitoring/backup_manager.py create config_only

# Verify backup integrity
tar -tzf backup_file.tar.gz --verify
```

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `deployment/scripts/install_service.sh` | Systemd service installation |
| `deployment/docker/Dockerfile` | Container definition |
| `deployment/docker/docker-compose.yml` | Multi-container setup |
| `operations/monitoring/health_checks.py` | Health monitoring system |
| `operations/monitoring/backup_manager.py` | Backup management |
| `operations/maintenance/update_bot.py` | Update procedures |
| `deployment/systemd/acore_bot.service` | Service definition |

---

**Last Updated**: 2025-12-16
**Version**: 1.0