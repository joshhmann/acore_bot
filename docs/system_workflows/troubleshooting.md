# Troubleshooting System Workflow

This document describes comprehensive troubleshooting procedures for acore_bot, including common issues, diagnostic tools, debugging techniques, and recovery procedures.

## Overview

The troubleshooting system provides **systematic problem resolution** through **diagnostic tools**, **error analysis**, **performance debugging**, and **recovery procedures** for efficient issue resolution.

## Architecture

### Component Structure
```
troubleshooting/
├── diagnostics/
│   ├── bot_diagnostic.py     # Bot health diagnostics
│   ├── system_check.py        # System environment checks
│   ├── dependency_check.py    # Dependency verification
│   └── network_test.py       # Network connectivity tests
├── tools/
│   ├── log_analyzer.py       # Log analysis tools
│   ├── performance_profiler.py # Performance profiling
│   ├── memory_profiler.py     # Memory usage analysis
│   └── debug_console.py      # Interactive debugging console
├── recovery/
│   ├── auto_recovery.py       # Automatic error recovery
│   ├── state_restoration.py   # State restoration procedures
│   └── data_repair.py        # Data corruption repair
└── guides/
    ├── common_issues.md       # Common problems and solutions
    ├── performance_issues.md   # Performance troubleshooting
    ├── deployment_issues.md   # Deployment problems
    └── integration_issues.md # Integration troubleshooting
```

### Service Dependencies
```
Troubleshooting Dependencies:
├── Diagnostic Tools       # System and service diagnostics
├── Log Analysis          # Log parsing and analysis
├── Performance Monitoring # Resource usage tracking
├── Error Tracking        # Error pattern analysis
├── Debug Logging         # Detailed debugging output
└── Recovery Systems      # Automated recovery procedures
```

## Diagnostic Tools

### 1. Comprehensive Bot Diagnostics
**File**: `troubleshooting/diagnostics/bot_diagnostic.py:45-234`

#### 1.1 Bot Health Diagnostics
```python
#!/usr/bin/env python3
"""Comprehensive bot diagnostic tool."""

import asyncio
import sys
import os
import json
import subprocess
import sqlite3
import psutil
from pathlib import Path
from datetime import datetime
import aiohttp

class BotDiagnostic:
    """Comprehensive diagnostic system for acore_bot."""
    
    def __init__(self):
        self.bot_dir = Path(__file__).parent.parent
        self.issues = []
        self.warnings = []
        self.info = []
        
    async def run_full_diagnostic(self) -> Dict:
        """Run comprehensive diagnostic checks."""
        
        print("🔍 Starting comprehensive bot diagnostic...")
        print("=" * 60)
        
        # Core system checks
        await self._check_python_environment()
        await self._check_dependencies()
        await self._check_configuration()
        await self._check_file_permissions()
        await self._check_disk_space()
        await self._check_memory_usage()
        
        # Service connectivity checks
        await self._check_discord_connectivity()
        await self._check_llm_services()
        await self._check_tts_services()
        await self._check_database_connectivity()
        
        # Application-specific checks
        await self._check_persona_files()
        await self._check_data_integrity()
        await self._check_log_health()
        await self._check_performance_metrics()
        
        # Generate report
        report = self._generate_diagnostic_report()
        
        # Save report
        await self._save_diagnostic_report(report)
        
        return report

    async def _check_python_environment(self):
        """Check Python environment and version."""
        
        print("🐍 Checking Python environment...")
        
        try:
            # Python version
            python_version = sys.version_info
            if python_version < (3, 11):
                self.issues.append(
                    f"Python version {python_version.major}.{python_version.minor} "
                    f"is below minimum required (3.11)"
                )
            else:
                self.info.append(
                    f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}"
                )
            
            # Virtual environment
            in_venv = hasattr(sys, 'real_prefix') or (
                hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
            )
            
            if in_venv:
                self.info.append("Running in virtual environment")
            else:
                self.warnings.append("Not running in virtual environment")
            
            # Package manager
            try:
                import uv
                self.info.append("Using uv package manager")
                
                # Check uv version
                result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.info.append(f"uv version: {result.stdout.strip()}")
            except ImportError:
                self.warnings.append("uv not found, using pip instead")
            
            # Key packages
            packages_to_check = [
                ('discord.py', 'discord'),
                ('aiohttp', 'aiohttp'),
                ('aiofiles', 'aiofiles'),
                ('python-dotenv', 'dotenv'),
                ('pillow', 'PIL'),
                ('psutil', 'psutil')
            ]
            
            for package_name, import_name in packages_to_check:
                try:
                    __import__(import_name)
                    self.info.append(f"✓ {package_name} available")
                except ImportError:
                    self.issues.append(f"✗ {package_name} missing")
        
        except Exception as e:
            self.issues.append(f"Python environment check failed: {e}")

    async def _check_dependencies(self):
        """Check external dependencies."""
        
        print("📦 Checking external dependencies...")
        
        dependencies = [
            {
                'name': 'FFmpeg',
                'command': 'ffmpeg -version',
                'required': True,
                'description': 'Audio processing'
            },
            {
                'name': 'SQLite3',
                'command': 'sqlite3 --version',
                'required': True,
                'description': 'Database storage'
            },
            {
                'name': 'Ollama',
                'command': 'ollama --version',
                'required': False,
                'description': 'LLM service'
            },
            {
                'name': 'Docker',
                'command': 'docker --version',
                'required': False,
                'description': 'Containerization'
            }
        ]
        
        for dep in dependencies:
            try:
                result = subprocess.run(
                    dep['command'].split(),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    self.info.append(f"✓ {dep['name']}: {result.stdout.split()[1] if len(result.stdout.split()) > 1 else 'available'}")
                else:
                    if dep['required']:
                        self.issues.append(f"✗ {dep['name']} required but not found")
                    else:
                        self.warnings.append(f"⚠ {dep['name']} not available (optional)")
            
            except subprocess.TimeoutExpired:
                self.warnings.append(f"⚠ {dep['name']} check timed out")
            except FileNotFoundError:
                if dep['required']:
                    self.issues.append(f"✗ {dep['name']} required but not found")
                else:
                    self.warnings.append(f"⚠ {dep['name']} not available (optional)")
            except Exception as e:
                self.issues.append(f"✗ {dep['name']} check failed: {e}")

    async def _check_configuration(self):
        """Check bot configuration."""
        
        print("⚙️ Checking configuration...")
        
        try:
            # Check .env file
            env_file = self.bot_dir / '.env'
            
            if not env_file.exists():
                self.issues.append(".env file not found")
                return
            
            self.info.append(f".env file found: {env_file}")
            
            # Load and validate configuration
            from dotenv import load_dotenv
            load_dotenv(env_file)
            
            # Required configuration
            required_vars = [
                ('DISCORD_TOKEN', 'Discord bot token'),
                ('OLLAMA_HOST', 'Ollama host'),
                ('DATA_DIR', 'Data directory')
            ]
            
            for var_name, description in required_vars:
                value = os.getenv(var_name)
                
                if not value:
                    self.issues.append(f"Required configuration {var_name} ({description}) not set")
                else:
                    self.info.append(f"✓ {var_name} configured")
            
            # Validate Discord token format
            token = os.getenv('DISCORD_TOKEN')
            if token:
                if len(token) < 50 or not token.startswith(('Nj', 'M')):
                    self.warnings.append("Discord token format appears invalid")
                else:
                    self.info.append("Discord token format appears valid")
            
            # Check data directories
            data_dir = Path(os.getenv('DATA_DIR', './data'))
            
            if not data_dir.exists():
                self.warnings.append(f"Data directory {data_dir} does not exist")
            else:
                self.info.append(f"Data directory: {data_dir}")
            
            # Check writable directories
            required_dirs = [
                data_dir,
                data_dir / 'chat_history',
                data_dir / 'user_profiles',
                data_dir / 'temp',
                data_dir / 'logs'
            ]
            
            for directory in required_dirs:
                try:
                    if not directory.exists():
                        directory.mkdir(parents=True, exist_ok=True)
                    
                    # Test write permissions
                    test_file = directory / '.write_test'
                    test_file.write_text('test')
                    test_file.unlink()
                    
                    self.info.append(f"✓ Directory writable: {directory}")
                
                except (PermissionError, OSError) as e:
                    self.issues.append(f"✗ Directory not writable: {directory} - {e}")
        
        except Exception as e:
            self.issues.append(f"Configuration check failed: {e}")

    async def _check_discord_connectivity(self):
        """Check Discord API connectivity."""
        
        print("🌐 Checking Discord connectivity...")
        
        try:
            token = os.getenv('DISCORD_TOKEN')
            if not token:
                self.issues.append("Discord token not configured")
                return
            
            # Test Discord API
            headers = {'Authorization': f'Bot {token}'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://discord.com/api/v10/users/@me',
                    headers=headers,
                    timeout=10
                ) as response:
                    
                    if response.status == 200:
                        self.info.append("✓ Discord API connectivity successful")
                        
                        user_data = await response.json()
                        self.info.append(f"Bot user: {user_data.get('username', 'Unknown')}")
                        
                        # Check bot permissions
                        guild_id = os.getenv('TEST_GUILD_ID')
                        if guild_id:
                            guild_response = await session.get(
                                f'https://discord.com/api/v10/guilds/{guild_id}',
                                headers=headers
                            )
                            
                            if guild_response.status == 200:
                                guild_data = await guild_response.json()
                                permissions = guild_data.get('permissions', 0)
                                
                                # Check essential permissions
                                essential_perms = [
                                    'Send Messages',
                                    'Embed Links',
                                    'Read Message History',
                                    'Add Reactions'
                                ]
                                
                                for perm in essential_perms:
                                    perm_value = {
                                        'Send Messages': 0x800,
                                        'Embed Links': 0x4000,
                                        'Read Message History': 0x10000,
                                        'Add Reactions': 0x40
                                    }.get(perm, 0)
                                    
                                    if permissions & perm_value:
                                        self.info.append(f"✓ Permission: {perm}")
                                    else:
                                        self.warnings.append(f"⚠ Missing permission: {perm}")
                    
                    elif response.status == 401:
                        self.issues.append("✗ Discord token invalid")
                    elif response.status == 403:
                        self.issues.append("✗ Discord API forbidden")
                    else:
                        self.warnings.append(f"Discord API returned status: {response.status}")
        
        except aiohttp.ClientError as e:
            self.issues.append(f"Discord connectivity failed: {e}")
        except Exception as e:
            self.issues.append(f"Discord check failed: {e}")

    async def _check_llm_services(self):
        """Check LLM service connectivity."""
        
        print("🤖 Checking LLM services...")
        
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        try:
            async with aiohttp.ClientSession() as session:
                # Check Ollama
                async with session.get(f"{ollama_host}/api/tags", timeout=5) as response:
                    if response.status == 200:
                        self.info.append(f"✓ Ollama service available at {ollama_host}")
                        
                        # Get available models
                        data = await response.json()
                        models = data.get('models', [])
                        self.info.append(f"✓ Available models: {len(models)}")
                        
                        # Check default model
                        default_model = os.getenv('OLLAMA_MODEL')
                        if default_model:
                            model_available = any(
                                model.get('name') == default_model for model in models
                            )
                            
                            if model_available:
                                self.info.append(f"✓ Default model {default_model} available")
                            else:
                                self.issues.append(f"✗ Default model {default_model} not available")
                    else:
                        self.issues.append(f"Ollama service returned status: {response.status}")
        
        except aiohttp.ClientError as e:
            self.issues.append(f"Ollama service not accessible: {e}")
        except Exception as e:
            self.issues.append(f"LLM service check failed: {e}")

    async def _check_database_connectivity(self):
        """Check database connectivity and integrity."""
        
        print("🗄️ Checking database connectivity...")
        
        data_dir = Path(os.getenv('DATA_DIR', './data'))
        db_file = data_dir / 'bot.db'
        
        try:
            if not db_file.exists():
                self.warnings.append("Database file does not exist")
                return
            
            # Test database connection
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            
            # Check database integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()
            
            if integrity_result[0] == 'ok':
                self.info.append("✓ Database integrity check passed")
            else:
                self.issues.append(f"✗ Database integrity issue: {integrity_result[0]}")
            
            # Check table structure
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['conversations', 'user_profiles', 'reminders', 'notes']
            
            for table in expected_tables:
                if table in tables:
                    self.info.append(f"✓ Table {table} exists")
                else:
                    self.warnings.append(f"⚠ Table {table} missing")
            
            # Check database size
            db_size = db_file.stat().st_size
            db_size_mb = db_size / (1024 * 1024)
            
            self.info.append(f"Database size: {db_size_mb:.2f} MB")
            
            conn.close()
        
        except sqlite3.Error as e:
            self.issues.append(f"Database error: {e}")
        except Exception as e:
            self.issues.append(f"Database check failed: {e}")

    async def _check_performance_metrics(self):
        """Check current performance metrics."""
        
        print("📊 Checking performance metrics...")
        
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            self.info.append(f"CPU usage: {cpu_percent}%")
            self.info.append(f"Memory usage: {memory.percent}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)")
            self.info.append(f"Disk usage: {(disk.used / disk.total) * 100:.1f}%")
            
            # Check for performance warnings
            if cpu_percent > 80:
                self.warnings.append("⚠ High CPU usage detected")
            
            if memory.percent > 85:
                self.warnings.append("⚠ High memory usage detected")
            
            if (disk.used / disk.total) > 90:
                self.warnings.append("⚠ High disk usage detected")
            
            # Process-specific metrics
            bot_processes = [p for p in psutil.process_iter(['name', 'cpu', 'memory']) 
                           if 'python' in p.info['name'].lower()]
            
            if bot_processes:
                bot_process = bot_processes[0]
                self.info.append(f"Bot process CPU: {bot_process.cpu_percent}%")
                self.info.append(f"Bot process memory: {bot_process.memory_info().rss / (1024**2):.1f}MB")
            else:
                self.warnings.append("⚠ Bot process not found")
        
        except Exception as e:
            self.issues.append(f"Performance check failed: {e}")

    def _generate_diagnostic_report(self) -> Dict:
        """Generate comprehensive diagnostic report."""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_issues': len(self.issues),
                'total_warnings': len(self.warnings),
                'total_info': len(self.info),
                'overall_status': 'critical' if self.issues else 'warning' if self.warnings else 'healthy'
            },
            'issues': self.issues,
            'warnings': self.warnings,
            'info': self.info,
            'recommendations': self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on findings."""
        
        recommendations = []
        
        # General recommendations
        if self.issues:
            recommendations.append("🔴 Address critical issues before deployment")
        
        if self.warnings:
            recommendations.append("🟡 Review warnings for potential improvements")
        
        # Specific recommendations based on findings
        issue_texts = ' '.join([issue.lower() for issue in self.issues])
        
        if 'token' in issue_texts:
            recommendations.append("🔑 Ensure Discord token is correctly configured")
        
        if 'permission' in issue_texts:
            recommendations.append("👥 Check bot permissions in Discord server settings")
        
        if 'directory not writable' in issue_texts:
            recommendations.append("📁 Fix directory permissions for bot user")
        
        if 'dependency' in issue_texts:
            recommendations.append("📦 Install missing dependencies using package manager")
        
        if 'memory' in ' '.join([w.lower() for w in self.warnings]):
            recommendations.append("💾 Consider optimizing memory usage or increasing available memory")
        
        if 'cpu' in ' '.join([w.lower() for w in self.warnings]):
            recommendations.append("⚙️ Optimize bot performance or upgrade CPU resources")
        
        return recommendations

    async def _save_diagnostic_report(self, report: Dict):
        """Save diagnostic report to file."""
        
        try:
            reports_dir = self.bot_dir / 'diagnostic_reports'
            reports_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = reports_dir / f"diagnostic_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            self.info.append(f"Diagnostic report saved: {report_file}")
            
            # Display summary
            self._display_diagnostic_summary(report)
        
        except Exception as e:
            self.issues.append(f"Failed to save diagnostic report: {e}")

    def _display_diagnostic_summary(self, report: Dict):
        """Display diagnostic summary to console."""
        
        print("\n" + "=" * 60)
        print("📋 DIAGNOSTIC SUMMARY")
        print("=" * 60)
        
        # Overall status
        status_emoji = {
            'healthy': '🟢',
            'warning': '🟡',
            'critical': '🔴'
        }
        
        overall_status = report['summary']['overall_status']
        print(f"Overall Status: {status_emoji[overall_status]} {overall_status.upper()}")
        print(f"Issues: {report['summary']['total_issues']}")
        print(f"Warnings: {report['summary']['total_warnings']}")
        print(f"Info: {report['summary']['total_info']}")
        
        # Critical issues first
        if self.issues:
            print("\n🔴 CRITICAL ISSUES:")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
        
        # Warnings
        if self.warnings:
            print("\n🟡 WARNINGS:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
        
        # Recommendations
        if report['recommendations']:
            print("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(report['recommendations'], 1):
                print(f"  {i}. {rec}")

# Main execution
async def main():
    """Main diagnostic execution."""
    
    diagnostic = BotDiagnostic()
    
    try:
        report = await diagnostic.run_full_diagnostic()
        
        # Exit with appropriate code
        if report['summary']['total_issues'] > 0:
            sys.exit(2)  # Critical issues found
        elif report['summary']['total_warnings'] > 0:
            sys.exit(1)  # Warnings found
        else:
            sys.exit(0)  # All good
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Diagnostic interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Diagnostic failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
```

## Common Issues and Solutions

### 1. Bot Not Responding
**Symptoms**: Bot online but doesn't respond to messages or commands

**Diagnostic Steps**:
```bash
# 1. Check if bot is actually running
ps aux | grep python

# 2. Check Discord connection
python troubleshooting/diagnostics/bot_diagnostic.py

# 3. Check logs for errors
tail -f logs/bot.log

# 4. Verify bot has message permissions
# Check Discord server settings -> Bot -> Permissions
```

**Common Causes and Solutions**:
- **Missing Permissions**: Ensure bot has "Send Messages", "Read Message History"
- **Rate Limiting**: Bot sending messages too quickly
- **Missing Intent**: Ensure proper intents are enabled in Discord Developer Portal
- **Blocked by Firewall**: Check network connectivity to Discord

### 2. LLM Service Errors
**Symptoms**: Errors generating responses, slow response times

**Diagnostic Steps**:
```bash
# 1. Test Ollama directly
curl http://localhost:11434/api/tags

# 2. Check if model is available
ollama list

# 3. Test model generation
ollama run llama3.2 "Hello, how are you?"

# 4. Check system resources
top -p $(pgrep -f ollama)
```

**Common Causes and Solutions**:
- **Ollama Not Running**: Start Ollama service
- **Insufficient Memory**: Increase available RAM or use smaller model
- **Model Not Downloaded**: Download required model with `ollama pull`
- **Port Conflicts**: Check if port 11434 is available

### 3. Voice System Issues
**Symptoms**: TTS not working, voice connection problems

**Diagnostic Steps**:
```bash
# 1. Check audio dependencies
ffmpeg -version

# 2. Test TTS service
curl http://localhost:8880/voices

# 3. Check bot voice permissions
# Bot must have "Connect", "Speak" permissions

# 4. Test audio output
aplay /usr/share/sounds/alsa/Front_Left.wav  # Linux
```

**Common Causes and Solutions**:
- **Missing FFmpeg**: Install FFmpeg with audio codecs
- **Permission Denied**: Bot lacks voice channel permissions
- **Audio Device Issues**: Check system audio configuration
- **TTS Service Down**: Restart TTS service (Kokoro, Supertonic)

### 4. Memory and Performance Issues
**Symptoms**: Bot becomes slow, memory usage increases

**Diagnostic Steps**:
```bash
# 1. Check memory usage
python troubleshooting/tools/memory_profiler.py

# 2. Monitor process resources
htop

# 3. Check for memory leaks
valgrind --leak-check=full python main.py

# 4. Profile performance
python -m cProfile -o profile.stats main.py
```

**Common Causes and Solutions**:
- **Memory Leaks**: Check for unclosed connections or references
- **Large Context Windows**: Reduce MAX_CONTEXT_TOKENS
- **Inefficient Loops**: Optimize code performance
- **Resource Exhaustion**: Implement proper cleanup routines

## Recovery Procedures

### 1. Automatic Error Recovery
**File**: `troubleshooting/recovery/auto_recovery.py:45-123`

#### 1.1 Recovery System
```python
import asyncio
import logging
from pathlib import Path
import shutil
from datetime import datetime

class AutoRecovery:
    """Automatic error recovery system."""
    
    def __init__(self):
        self.recovery_log = []
        self.max_recovery_attempts = 3
        self.recovery_cooldown = 300  # 5 minutes
        
    async def attempt_recovery(self, error: Exception, context: Dict) -> bool:
        """Attempt automatic recovery from error."""
        
        error_type = type(error).__name__
        error_message = str(error)
        
        logging.error(f"Attempting recovery for {error_type}: {error_message}")
        
        # Check recent recovery attempts
        if self._recent_recovery_attempt(error_type):
            logging.warning(f"Recent recovery attempt for {error_type}, skipping")
            return False
        
        # Recovery strategies based on error type
        recovery_strategies = {
            'ConnectionError': self._recover_from_connection_error,
            'TimeoutError': self._recover_from_timeout_error,
            'PermissionError': self._recover_from_permission_error,
            'MemoryError': self._recover_from_memory_error,
            'DatabaseError': self._recover_from_database_error,
            'FileNotFoundError': self._recover_from_file_error,
            'DiscordException': self._recover_from_discord_error
        }
        
        recovery_func = recovery_strategies.get(error_type)
        
        if recovery_func:
            try:
                success = await recovery_func(error, context)
                
                # Log recovery attempt
                self._log_recovery_attempt(error_type, success)
                
                return success
            
            except Exception as recovery_error:
                logging.error(f"Recovery failed: {recovery_error}")
                return False
        else:
            logging.warning(f"No recovery strategy for {error_type}")
            return False

    async def _recover_from_connection_error(self, error: Exception, context: Dict) -> bool:
        """Recover from connection errors."""
        
        logging.info("Attempting connection recovery...")
        
        # Strategies:
        # 1. Reconnect Discord client
        if hasattr(context.get('bot'), 'restart'):
            try:
                await context['bot'].close()
                await asyncio.sleep(5)
                await context['bot'].start(Config.DISCORD_TOKEN)
                logging.info("Discord client reconnected")
                return True
            except Exception as e:
                logging.error(f"Failed to reconnect Discord client: {e}")
        
        # 2. Reset external service connections
        if 'services' in context:
            for service_name, service in context['services'].items():
                try:
                    if hasattr(service, 'reconnect'):
                        await service.reconnect()
                        logging.info(f"Reconnected service: {service_name}")
                except Exception as e:
                    logging.error(f"Failed to reconnect {service_name}: {e}")
        
        # 3. Wait and retry
        await asyncio.sleep(10)
        return False  # Indicate recovery not fully successful

    async def _recover_from_memory_error(self, error: Exception, context: Dict) -> bool:
        """Recover from memory errors."""
        
        logging.info("Attempting memory recovery...")
        
        # 1. Force garbage collection
        import gc
        collected = gc.collect()
        logging.info(f"Garbage collection freed {collected} objects")
        
        # 2. Clear caches if available
        if hasattr(context.get('bot'), 'clear_caches'):
            try:
                await context['bot'].clear_caches()
                logging.info("Cleared bot caches")
            except Exception as e:
                logging.error(f"Failed to clear caches: {e}")
        
        # 3. Restart components if available
        if hasattr(context.get('bot'), 'restart_memory_intensive_components'):
            try:
                await context['bot'].restart_memory_intensive_components()
                logging.info("Restarted memory-intensive components")
                return True
            except Exception as e:
                logging.error(f"Failed to restart components: {e}")
        
        return False

    async def _recover_from_discord_error(self, error: Exception, context: Dict) -> bool:
        """Recover from Discord-specific errors."""
        
        logging.info("Attempting Discord error recovery...")
        
        error_message = str(error).lower()
        
        # Rate limiting
        if 'rate limited' in error_message:
            logging.info("Discord rate limit detected, waiting...")
            await asyncio.sleep(60)  # Wait 1 minute
            return True
        
        # Invalid permissions
        if 'permission' in error_message or 'unauthorized' in error_message:
            logging.error("Discord permission error - manual intervention required")
            return False
        
        # Gateway issues
        if 'gateway' in error_message:
            logging.info("Discord gateway issue, attempting reconnection...")
            if hasattr(context.get('bot'), 'reconnect'):
                try:
                    await context['bot'].reconnect()
                    return True
                except Exception as e:
                    logging.error(f"Failed to reconnect: {e}")
        
        return False

    def _recent_recovery_attempt(self, error_type: str) -> bool:
        """Check if there was a recent recovery attempt."""
        
        cutoff_time = datetime.now().timestamp() - self.recovery_cooldown
        
        for attempt in self.recovery_log:
            if (attempt['error_type'] == error_type and 
                attempt['timestamp'] > cutoff_time):
                return True
        
        return False

    def _log_recovery_attempt(self, error_type: str, success: bool):
        """Log recovery attempt."""
        
        self.recovery_log.append({
            'timestamp': datetime.now().timestamp(),
            'error_type': error_type,
            'success': success
        })
        
        # Keep only recent attempts
        if len(self.recovery_log) > 50:
            self.recovery_log = self.recovery_log[-25:]
```

## Configuration

### Troubleshooting Settings
```bash
# Diagnostic Configuration
DIAGNOSTIC_ENABLED=true                     # Enable diagnostic tools
DIAGNOSTIC_REPORTS_PATH=./diagnostics     # Diagnostic report storage
AUTO_DIAGNOSTIC_ON_ERROR=true               # Run diagnostic on errors

# Recovery Configuration
AUTO_RECOVERY_ENABLED=true                    # Enable automatic recovery
MAX_RECOVERY_ATTEMPTS=3                     # Max recovery attempts
RECOVERY_COOLDOWN=300                         # Recovery cooldown (seconds)

# Debugging Configuration
DEBUG_MODE=false                               # Enable debug mode
VERBOSE_LOGGING=true                           # Verbose logging
PERFORMANCE_PROFILING=false                     # Enable performance profiling
MEMORY_PROFILING=false                        # Enable memory profiling

# Error Tracking
ERROR_REPORTING_ENABLED=true                   # Enable error reporting
ERROR_REPORT_WEBHOOK=                          # Webhook for error reports
CRITICAL_ERROR_NOTIFICATIONS=true             # Critical error alerts

# Health Monitoring
HEALTH_CHECK_INTERVAL=300                     # Health check interval (seconds)
RESOURCE_MONITORING_ENABLED=true                # Enable resource monitoring
PERFORMANCE_ALERTS=true                       # Enable performance alerts

# Backup and Recovery
AUTO_BACKUP_ON_ERROR=false                    # Auto-backup on critical errors
STATE_BACKUP_ENABLED=true                     # Enable state backups
RECOVERY_STATE_RETENTION=7                     # Days to keep recovery states
```

## Integration Points

### With All Systems
- **Error Handling**: Comprehensive error detection and recovery
- **Performance Monitoring**: System-wide performance tracking
- **Health Monitoring**: Continuous health status checks

### With Monitoring System
- **Alert Integration**: Troubleshooting alerts to monitoring
- **Diagnostic Reports**: Automated diagnostic reporting
- **Recovery Status**: Recovery system status monitoring

### With Administration System
- **Manual Controls**: Administrative override of recovery
- **Diagnostic Access**: Admin access to diagnostic tools
- **Recovery Configuration**: Admin-configurable recovery settings

## Performance Considerations

### 1. Diagnostic Overhead
- **Minimal Impact**: Diagnostics designed for low overhead
- **Selective Execution**: Only run when issues detected
- **Background Processing**: Non-blocking diagnostic operations

### 2. Recovery Efficiency
- **Fast Recovery**: Quick detection and recovery
- **Minimal Downtime**: Reduce service disruption
- **Progressive Strategies**: Multiple recovery approaches

### 3. Resource Management
- **Memory Conscious**: Recovery operations memory efficient
- **CPU Optimized**: Minimal CPU overhead during recovery
- **Network Efficient**: Low-bandwidth recovery operations

## Security Considerations

### 1. Diagnostic Security
- **Sensitive Data**: Avoid logging sensitive information
- **Access Control**: Diagnostic tools require appropriate permissions
- **Data Sanitization**: Remove sensitive data from reports

### 2. Recovery Security
- **Safe Operations**: Recovery doesn't compromise security
- **Validation**: Verify recovery operations are safe
- **Audit Trail**: Log all recovery actions

## Common Issues and Troubleshooting

### 1. Diagnostic Tool Not Working
```bash
# Check diagnostic script
python troubleshooting/diagnostics/bot_diagnostic.py

# Verify permissions
ls -la troubleshooting/diagnostics/

# Check dependencies
python -c "import aiohttp, psutil, sqlite3; print('Dependencies OK')"
```

### 2. Recovery Not Triggering
```python
# Check recovery configuration
python -c "
import os
print(f'Auto recovery enabled: {os.getenv(\"AUTO_RECOVERY_ENABLED\", \"false\")}')
print(f'Recovery cooldown: {os.getenv(\"RECOVERY_COOLDOWN\", \"300\")}')
"

# Check recovery logs
grep "Recovery" logs/bot.log | tail -10
```

### 3. Performance Profiling Issues
```bash
# Check profiling tools
python -c "import cProfile, memory_profiler; print('Profiling tools available')"

# Run simple profile
python -m cProfile -s time troubleshooting/tools/performance_profiler.py
```

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `troubleshooting/diagnostics/bot_diagnostic.py` | Comprehensive bot diagnostics |
| `troubleshooting/tools/log_analyzer.py` | Log analysis and parsing |
| `troubleshooting/tools/performance_profiler.py` | Performance profiling tools |
| `troubleshooting/recovery/auto_recovery.py` | Automatic error recovery |
| `troubleshooting/guides/common_issues.md` | Common issues guide |
| `troubleshooting/guides/performance_issues.md` | Performance troubleshooting |

---

**Last Updated**: 2025-12-16
**Version**: 1.0