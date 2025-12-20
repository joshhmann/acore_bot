# System Administration Workflow

This document describes the complete system administration capabilities in acore_bot, including bot management commands, system monitoring, configuration management, and maintenance workflows.

## Overview

The system administration module provides **comprehensive bot control** through **administrative commands**, **system monitoring**, **performance tracking**, and **maintenance operations** for managing the entire Discord bot ecosystem.

## Architecture

### Component Structure
```
cogs/
├── system.py               # SystemCog - admin commands and bot management
├── help.py                 # Help system and command documentation
└── event_listeners.py      # System event monitoring

services/core/
├── health.py              # Health check and monitoring service
├── metrics.py             # Performance metrics collection
├── factory.py             # Service factory and dependency injection
└── rate_limiter.py        # Rate limiting and abuse prevention

utils/
├── error_handlers.py      # Error handling and recovery
├── logging_config.py      # Logging system configuration
└── helpers.py             # Administrative utility functions

scripts/
├── analyze_performance.py # Performance analysis tools
├── benchmark_optimizations.py # System benchmarking
└── run_all_tests.sh       # Test suite runner
```

### Service Dependencies
```
Administration Dependencies:
├── Discord Permissions     # Admin role verification
├── System Health Checks   # Service monitoring
├── Performance Metrics     # Usage statistics
├── Configuration Manager   # Dynamic configuration
├── Logging System          # Activity tracking
├── Error Recovery          # Automated healing
└── Maintenance Tools      # System upkeep
```

## Administrative Command System

### 1. SystemCog Core
**File**: `cogs/system.py:45-345`

#### 1.1 Administrative Commands
```python
class SystemCog(commands.Cog):
    """System administration and management commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.health_service = HealthCheckService()
        self.metrics_service = MetricsService()

        # Admin role checking
        self.admin_roles = Config.ADMIN_ROLES if hasattr(Config, 'ADMIN_ROLES') else []
        self.admin_users = Config.ADMIN_USERS if hasattr(Config, 'ADMIN_USERS') else []

        # Maintenance state
        self.maintenance_mode = False
        self.maintenance_reason = ""

    def _is_admin(self, user: discord.User) -> bool:
        """Check if user has administrative privileges."""
        # Check explicit admin users
        if user.id in self.admin_users:
            return True

        # Check admin roles (if in guild)
        if isinstance(user, discord.Member):
            for role in user.roles:
                if role.id in self.admin_roles:
                    return True

        return False

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        """Handle command errors for admin commands."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
        else:
            logger.error(f"Admin command error: {error}")
            await interaction.response.send_message(
                f"❌ An error occurred: {error}",
                ephemeral=True
            )

@app_commands.command(name="botstatus", description="Show comprehensive bot status")
async def bot_status(self, interaction: discord.Interaction):
    """Display comprehensive bot status information."""
    await interaction.response.defer(thinking=True)

    try:
        # 1. Create status embed
        embed = discord.Embed(
            title="🤖 Bot Status",
            color=discord.Color.green() if not self.maintenance_mode else discord.Color.orange()
        )

        # 2. Basic information
        uptime = datetime.now() - self.bot.start_time if hasattr(self.bot, 'start_time') else None
        embed.add_field(
            name="📊 Basic Info",
            value=f"**Status:** {'🟢 Online' if not self.maintenance_mode else '🟡 Maintenance'}\n"
                  f"**Uptime:** {self._format_uptime(uptime)}\n"
                  f"**Guilds:** {len(self.bot.guilds)}\n"
                  f"**Users:** {sum(g.member_count for g in self.bot.guilds)}\n"
                  f"**Latency:** {round(self.bot.latency * 1000)}ms",
            inline=False
        )

        # 3. Service health
        health_status = await self._get_service_health()
        health_emoji = {
            'healthy': '🟢',
            'degraded': '🟡',
            'unhealthy': '🔴'
        }

        health_text = "\n".join([
            f"{health_emoji.get(status['status'], '⚪')} **{service}:** {status['status']}"
            for service, status in health_status.items()
        ])

        embed.add_field(
            name="🏥 Service Health",
            value=health_text,
            inline=True
        )

        # 4. Performance metrics
        metrics = await self._get_performance_metrics()
        embed.add_field(
            name="📈 Performance",
            value=f"**Responses/min:** {metrics.get('responses_per_minute', 0)}\n"
                  f"**Error Rate:** {metrics.get('error_rate', 0):.2%}\n"
                  f"**Memory Usage:** {metrics.get('memory_usage', 0):.1f}MB\n"
                  f"**Active Chats:** {metrics.get('active_chats', 0)}",
            inline=True
        )

        # 5. Recent activity
        recent_activity = await self._get_recent_activity()
        if recent_activity:
            embed.add_field(
                name="📋 Recent Activity",
                value=recent_activity,
                inline=False
            )

        # 6. Maintenance status
        if self.maintenance_mode:
            embed.add_field(
                name="🔧 Maintenance Mode",
                value=f"**Reason:** {self.maintenance_reason}\n"
                      f"**Duration:** Since maintenance began",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error getting bot status: {e}",
            ephemeral=True
        )

@app_commands.command(name="admin", description="Administrative control panel")
@app_commands.describe(
    action="Administrative action to perform",
    target="Target for the action (user/channel/guild)",
    reason="Reason for the action"
)
async def admin_control(
    self,
    interaction: discord.Interaction,
    action: str,
    target: Optional[str] = None,
    reason: Optional[str] = None
):
    """Perform administrative actions."""
    await interaction.response.defer(thinking=True)

    try:
        # Available actions
        available_actions = [
            'maintenance_on', 'maintenance_off',
            'restart', 'shutdown', 'reload_cogs',
            'clear_cache', 'cleanup', 'backup',
            'block_user', 'unblock_user', 'check_permissions'
        ]

        if action not in available_actions:
            await interaction.followup.send(
                f"❌ Unknown action. Available: {', '.join(available_actions)}",
                ephemeral=True
            )
            return

        # Execute action
        result = await self._execute_admin_action(action, target, reason)

        # Log action
        await self._log_admin_action(interaction.user, action, target, reason)

        if result['success']:
            embed = discord.Embed(
                title="✅ Administrative Action Completed",
                description=result['message'],
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Administrative Action Failed",
                description=result['message'],
                color=discord.Color.red()
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error executing admin action: {e}",
            ephemeral=True
        )

async def _execute_admin_action(self, action: str, target: Optional[str], reason: Optional[str]) -> Dict:
    """Execute specific administrative action."""

    try:
        if action == 'maintenance_on':
            self.maintenance_mode = True
            self.maintenance_reason = reason or "Scheduled maintenance"
            return {
                'success': True,
                'message': f"Maintenance mode enabled: {self.maintenance_reason}"
            }

        elif action == 'maintenance_off':
            self.maintenance_mode = False
            self.maintenance_reason = ""
            return {
                'success': True,
                'message': "Maintenance mode disabled"
            }

        elif action == 'restart':
            # Graceful restart
            await self._prepare_restart()
            return {
                'success': True,
                'message': "Bot restart initiated. Please wait..."
            }

        elif action == 'shutdown':
            # Graceful shutdown
            await self._prepare_shutdown()
            return {
                'success': True,
                'message': "Bot shutdown initiated."
            }

        elif action == 'reload_cogs':
            # Reload all cogs
            reloaded = await self._reload_all_cogs()
            return {
                'success': True,
                'message': f"Reloaded {len(reloaded)} cogs: {', '.join(reloaded)}"
            }

        elif action == 'clear_cache':
            # Clear all caches
            cleared = await self._clear_all_caches()
            return {
                'success': True,
                'message': f"Cache cleared for {cleared} services"
            }

        elif action == 'cleanup':
            # Run cleanup tasks
            cleanup_result = await self._run_cleanup_tasks()
            return {
                'success': True,
                'message': f"Cleanup completed: {cleanup_result}"
            }

        elif action == 'backup':
            # Create backup
            backup_path = await self._create_backup()
            return {
                'success': True,
                'message': f"Backup created: {backup_path}"
            }

        elif action == 'block_user':
            if not target:
                return {'success': False, 'message': 'User ID required for block action'}

            # Block user from bot
            user_id = int(target)
            Config.IGNORED_USERS.append(user_id)
            return {
                'success': True,
                'message': f"User {user_id} blocked from bot interactions"
            }

        elif action == 'unblock_user':
            if not target:
                return {'success': False, 'message': 'User ID required for unblock action'}

            # Unblock user
            user_id = int(target)
            if user_id in Config.IGNORED_USERS:
                Config.IGNORED_USERS.remove(user_id)
                return {
                    'success': True,
                    'message': f"User {user_id} unblocked"
                }
            else:
                return {
                    'success': False,
                    'message': f"User {user_id} was not blocked"
                }

        elif action == 'check_permissions':
            # Check bot permissions in current guild
            if not hasattr(interaction, 'guild') or not interaction.guild:
                return {'success': False, 'message': 'Must be used in a guild'}

            perms = interaction.guild.me.guild_permissions
            missing_permissions = [
                perm for perm, has_perm in perms
                if not has_perm and perm in [
                    'send_messages', 'embed_links', 'attach_files',
                    'read_message_history', 'add_reactions', 'connect', 'speak'
                ]
            ]

            if missing_permissions:
                return {
                    'success': False,
                    'message': f"Missing permissions: {', '.join(missing_permissions)}"
                }
            else:
                return {
                    'success': True,
                    'message': "All required permissions are present"
                }

        else:
            return {
                'success': False,
                'message': f"Unknown action: {action}"
            }

    except Exception as e:
        logger.error(f"Error executing admin action {action}: {e}")
        return {
            'success': False,
            'message': f"Error: {str(e)}"
        }
```

### 2. Health Monitoring System
**File**: `services/core/health.py:34-156`

#### 2.1 Health Check Service
```python
class HealthCheckService:
    """Comprehensive health monitoring for all bot services."""

    def __init__(self):
        self.check_intervals = {
            'critical': 30,    # Every 30 seconds
            'warning': 60,     # Every minute
            'info': 300        # Every 5 minutes
        }

        self.health_cache = {}
        self.last_checks = {}
        self.alert_thresholds = {
            'error_rate': 0.05,      # 5% error rate
            'response_time': 5000,   # 5 seconds
            'memory_usage': 1000,    # 1GB
            'disk_usage': 0.9        # 90%
        }

        # Start health monitoring loop
        asyncio.create_task(self._health_monitoring_loop())

async def check_all_services(self) -> Dict[str, Dict]:
    """Check health of all bot services."""

    health_results = {
        'discord_api': await self._check_discord_api(),
        'llm_service': await self._check_llm_service(),
        'tts_service': await self._check_tts_service(),
        'voice_system': await self._check_voice_system(),
        'memory_system': await self._check_memory_system(),
        'persona_system': await self._check_persona_system(),
        'music_system': await self._check_music_system(),
        'database': await self._check_database(),
        'file_system': await self._check_file_system(),
        'performance': await self._check_performance()
    }

    # Update cache
    self.health_cache.update(health_results)
    self.last_checks['full_check'] = datetime.now()

    return health_results

async def _check_discord_api(self) -> Dict:
    """Check Discord API connectivity and latency."""

    try:
        # 1. Check WebSocket connection
        ws_status = self.bot.ws

        if not ws_status or ws_status.closed:
            return {
                'status': 'unhealthy',
                'message': 'Discord WebSocket not connected',
                'details': {'connected': False}
            }

        # 2. Check API latency
        start_time = time.time()
        test_guild = self.bot.guilds[0] if self.bot.guilds else None

        if test_guild:
            await test_guild.fetch_channels()  # API call test
            api_latency = (time.time() - start_time) * 1000
        else:
            api_latency = self.bot.latency * 1000

        # 3. Determine status
        if api_latency > self.alert_thresholds['response_time']:
            status = 'degraded'
            message = f'High API latency: {api_latency:.0f}ms'
        else:
            status = 'healthy'
            message = f'API latency: {api_latency:.0f}ms'

        return {
            'status': status,
            'message': message,
            'details': {
                'connected': True,
                'latency_ms': round(api_latency),
                'guilds_count': len(self.bot.guilds)
            }
        }

    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'Discord API error: {e}',
            'details': {'error': str(e)}
        }

async def _check_llm_service(self) -> Dict:
    """Check LLM service availability and performance."""

    try:
        # Check each configured LLM provider
        providers = {}

        # Check Ollama
        if Config.LLM_PROVIDER in ['ollama', '']:
            ollama_status = await self._check_ollama_service()
            providers['ollama'] = ollama_status

        # Check OpenRouter
        if Config.LLM_PROVIDER == 'openrouter':
            openrouter_status = await self._check_openrouter_service()
            providers['openrouter'] = openrouter_status

        # Determine overall status
        if all(p['status'] == 'healthy' for p in providers.values()):
            overall_status = 'healthy'
            message = 'All LLM providers healthy'
        elif any(p['status'] == 'healthy' for p in providers.values()):
            overall_status = 'degraded'
            message = 'Some LLM providers degraded'
        else:
            overall_status = 'unhealthy'
            message = 'All LLM providers unhealthy'

        return {
            'status': overall_status,
            'message': message,
            'details': {
                'providers': providers,
                'active_provider': Config.LLM_PROVIDER
            }
        }

    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'LLM service error: {e}',
            'details': {'error': str(e)}
        }

async def _check_memory_system(self) -> Dict:
    """Check memory system health."""

    try:
        checks = {}

        # Check conversation history
        if hasattr(self.bot, 'conversation_manager'):
            history_status = await self._check_conversation_history()
            checks['conversation_history'] = history_status

        # Check RAG system
        if hasattr(self.bot, 'rag_service'):
            rag_status = await self._check_rag_system()
            checks['rag'] = rag_status

        # Check user profiles
        if hasattr(self.bot, 'profile_service'):
            profiles_status = await self._check_user_profiles()
            checks['user_profiles'] = profiles_status

        # Overall assessment
        if all(check['status'] == 'healthy' for check in checks.values()):
            overall_status = 'healthy'
            message = 'Memory system healthy'
        elif any(check['status'] == 'healthy' for check in checks.values()):
            overall_status = 'degraded'
            message = 'Some memory components degraded'
        else:
            overall_status = 'unhealthy'
            message = 'Memory system unhealthy'

        return {
            'status': overall_status,
            'message': message,
            'details': checks
        }

    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'Memory system error: {e}',
            'details': {'error': str(e)}
        }

async def _health_monitoring_loop(self):
    """Continuous health monitoring loop."""

    while True:
        try:
            # Full health check
            await self.check_all_services()

            # Check for alerts
            await self._check_health_alerts()

            # Sleep until next check
            await asyncio.sleep(self.check_intervals['info'])

        except Exception as e:
            logger.error(f"Health monitoring loop error: {e}")
            await asyncio.sleep(60)  # Wait before retrying

async def _check_health_alerts(self):
    """Check if any health conditions require alerts."""

    # Check for critical issues
    for service, health in self.health_cache.items():
        if health['status'] == 'unhealthy':
            await self._send_health_alert(
                level='critical',
                service=service,
                message=health['message']
            )

    # Check performance alerts
    metrics = await self.metrics_service.get_current_metrics()

    if metrics.get('error_rate', 0) > self.alert_thresholds['error_rate']:
        await self._send_health_alert(
            level='warning',
            service='performance',
            message=f"High error rate: {metrics['error_rate']:.2%}"
        )

    if metrics.get('memory_usage', 0) > self.alert_thresholds['memory_usage']:
        await self._send_health_alert(
            level='warning',
            service='performance',
            message=f"High memory usage: {metrics['memory_usage']:.1f}MB"
        )
```

### 3. Metrics and Analytics
**File**: `services/core/metrics.py:45-189`

#### 3.1 Metrics Collection
```python
class MetricsService:
    """Comprehensive metrics collection and analysis."""

    def __init__(self):
        self.metrics = {
            'messages_processed': 0,
            'responses_generated': 0,
            'commands_used': defaultdict(int),
            'errors_occurred': 0,
            'voice_connections': 0,
            'songs_played': 0,
            'tts_requests': 0,
            'start_time': datetime.now(),
            'response_times': deque(maxlen=1000),
            'hourly_activity': defaultdict(int),
            'daily_activity': defaultdict(int)
        }

        self.performance_metrics = {
            'cpu_usage': deque(maxlen=60),      # Last 60 minutes
            'memory_usage': deque(maxlen=60),
            'disk_usage': deque(maxlen=60),
            'network_io': deque(maxlen=60)
        }

        # Start collection loops
        asyncio.create_task(self._metrics_collection_loop())
        asyncio.create_task(self._performance_monitoring_loop())

async def record_message(self, user_id: int, channel_id: int, message_type: str = 'text'):
    """Record a message processing event."""

    self.metrics['messages_processed'] += 1

    # Record hourly activity
    hour = datetime.now().hour
    self.metrics['hourly_activity'][hour] += 1

    # Record daily activity
    date = datetime.now().strftime('%Y-%m-%d')
    self.metrics['daily_activity'][date] += 1

async def record_response(self, response_time_ms: float, persona_id: str = None):
    """Record a response generation event."""

    self.metrics['responses_generated'] += 1
    self.metrics['response_times'].append(response_time_ms)

    # Record persona usage if provided
    if persona_id:
        key = f"persona_{persona_id}"
        self.metrics['commands_used'][key] += 1

async def record_error(self, error_type: str, context: Dict = None):
    """Record an error occurrence."""

    self.metrics['errors_occurred'] += 1
    error_key = f"error_{error_type}"
    self.metrics['commands_used'][error_key] += 1

    # Log error with context
    logger.error(f"Error recorded: {error_type}", extra=context)

async def get_current_metrics(self) -> Dict:
    """Get current metrics snapshot."""

    # Calculate derived metrics
    total_time = (datetime.now() - self.metrics['start_time']).total_seconds()
    messages_per_minute = (self.metrics['messages_processed'] / total_time) * 60 if total_time > 0 else 0

    avg_response_time = (
        sum(self.metrics['response_times']) / len(self.metrics['response_times'])
        if self.metrics['response_times'] else 0
    )

    recent_errors = [
        rt for rt in self.metrics['response_times']
        if rt > self.metrics['response_times'][-1] - 3600  # Last hour
    ]

    error_rate = len(recent_errors) / max(self.metrics['responses_generated'], 1)

    return {
        'uptime_hours': total_time / 3600,
        'messages_processed': self.metrics['messages_processed'],
        'responses_generated': self.metrics['responses_generated'],
        'responses_per_minute': messages_per_minute,
        'error_rate': error_rate,
        'average_response_time': avg_response_time,
        'errors_occurred': self.metrics['errors_occurred'],
        'voice_connections': self.metrics['voice_connections'],
        'songs_played': self.metrics['songs_played'],
        'tts_requests': self.metrics['tts_requests'],
        'active_chats': len(set(self.metrics['active_channels'])) if hasattr(self.metrics, 'active_channels') else 0,
        'memory_usage': self.performance_metrics['memory_usage'][-1] if self.performance_metrics['memory_usage'] else 0
    }

async def _metrics_collection_loop(self):
    """Periodic metrics collection and cleanup."""

    while True:
        try:
            # Save metrics to file
            await self._save_metrics()

            # Cleanup old data
            await self._cleanup_old_metrics()

            # Calculate and store aggregates
            await self._calculate_aggregates()

            # Sleep until next collection
            await asyncio.sleep(Config.METRICS_SAVE_INTERVAL_MINUTES * 60)

        except Exception as e:
            logger.error(f"Metrics collection error: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error

async def _performance_monitoring_loop(self):
    """Monitor system performance metrics."""

    while True:
        try:
            import psutil

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.performance_metrics['cpu_usage'].append(cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            self.performance_metrics['memory_usage'].append(memory.used / 1024 / 1024)  # MB

            # Disk usage
            disk = psutil.disk_usage('./')
            self.performance_metrics['disk_usage'].append(disk.percent)

            # Network I/O (simplified)
            network = psutil.net_io_counters()
            self.performance_metrics['network_io'].append(network.bytes_sent + network.bytes_recv)

            await asyncio.sleep(60)  # Update every minute

        except Exception as e:
            logger.error(f"Performance monitoring error: {e}")
            await asyncio.sleep(60)
```

### 4. Configuration Management
**File**: `cogs/system.py:346-456`

#### 4.1 Dynamic Configuration
```python
@app_commands.command(name="config", description="Manage bot configuration")
@app_commands.describe(
    action="Configuration action",
    key="Configuration key",
    value="New configuration value"
)
async def config_management(
    self,
    interaction: discord.Interaction,
    action: str,
    key: Optional[str] = None,
    value: Optional[str] = None
):
    """Manage bot configuration dynamically."""
    await interaction.response.defer(thinking=True)

    try:
        available_actions = ['get', 'set', 'list', 'reload', 'backup', 'restore']

        if action not in available_actions:
            await interaction.followup.send(
                f"❌ Unknown action. Available: {', '.join(available_actions)}",
                ephemeral=True
            )
            return

        if action == 'list':
            config_items = await self._list_configuration()
            await self._send_config_list(interaction, config_items)

        elif action == 'get':
            if not key:
                await interaction.followup.send(
                    "❌ Configuration key required for 'get' action",
                    ephemeral=True
                )
                return

            config_value = await self._get_config_value(key)
            await self._send_config_value(interaction, key, config_value)

        elif action == 'set':
            if not key or not value:
                await interaction.followup.send(
                    "❌ Key and value required for 'set' action",
                    ephemeral=True
                )
                return

            result = await self._set_config_value(key, value)
            await self._send_config_result(interaction, key, value, result)

        elif action == 'reload':
            result = await self._reload_configuration()
            await self._send_config_reload_result(interaction, result)

        elif action == 'backup':
            backup_path = await self._backup_configuration()
            await self._send_config_backup_result(interaction, backup_path)

        elif action == 'restore':
            if not key:  # Using key as backup file path
                await interaction.followup.send(
                    "❌ Backup file path required for 'restore' action",
                    ephemeral=True
                )
                return

            result = await self._restore_configuration(key)
            await self._send_config_restore_result(interaction, result)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Configuration error: {e}",
            ephemeral=True
        )

async def _set_config_value(self, key: str, value: str) -> Dict:
    """Set configuration value with validation."""

    try:
        # Get current config type
        if hasattr(Config, key):
            current_value = getattr(Config, key)
            value_type = type(current_value)
        else:
            # New config value - try to infer type
            if value.lower() in ['true', 'false']:
                value_type = bool
            elif value.isdigit():
                value_type = int
            elif self._is_float(value):
                value_type = float
            elif value.startswith('[') and value.endswith(']'):
                value_type = list
            else:
                value_type = str

        # Convert value to correct type
        converted_value = self._convert_config_value(value, value_type)

        # Validate the value
        if key in self._get_validatable_configs():
            validation_result = await self._validate_config_value(key, converted_value)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'message': validation_result['error']
                }

        # Set the value
        setattr(Config, key, converted_value)

        # Update environment file if needed
        await self._update_env_file(key, converted_value)

        return {
            'success': True,
            'message': f"Configuration updated: {key} = {converted_value} ({value_type.__name__})"
        }

    except Exception as e:
        return {
            'success': False,
            'message': f"Error setting {key}: {e}"
        }

async def _validate_config_value(self, key: str, value) -> Dict:
    """Validate configuration value against constraints."""

    validation_rules = {
        'OLLAMA_TEMPERATURE': {'min': 0.0, 'max': 2.0, 'type': float},
        'OLLAMA_MAX_TOKENS': {'min': 1, 'max': 8192, 'type': int},
        'RESPONSE_STREAMING_ENABLED': {'type': bool},
        'USER_PROFILES_ENABLED': {'type': bool},
        'METRICS_RETENTION_DAYS': {'min': 1, 'max': 365, 'type': int},
        'GLOBAL_RESPONSE_CHANCE': {'min': 0.0, 'max': 1.0, 'type': float},
        'ANALYTICS_DASHBOARD_PORT': {'min': 1024, 'max': 65535, 'type': int}
    }

    if key not in validation_rules:
        return {'valid': True}

    rule = validation_rules[key]

    # Type check
    if not isinstance(value, rule['type']):
        return {
            'valid': False,
            'error': f"Expected {rule['type'].__name__}, got {type(value).__name__}"
        }

    # Range check
    if 'min' in rule and value < rule['min']:
        return {
            'valid': False,
            'error': f"Value {value} is below minimum {rule['min']}"
        }

    if 'max' in rule and value > rule['max']:
        return {
            'valid': False,
            'error': f"Value {value} is above maximum {rule['max']}"
        }

    return {'valid': True}
```

## Configuration

### Administration Settings
```bash
# Administrative Access
ADMIN_ROLES=[]                                   # Role IDs with admin access
ADMIN_USERS=[]                                    # User IDs with admin access
MAINTENANCE_MODE=false                            # Enable maintenance mode

# Health Monitoring
HEALTH_CHECK_INTERVAL=60                          # Health check frequency (seconds)
HEALTH_ALERT_WEBHOOK=""                          # Webhook for health alerts
CRITICAL_ALERT_THRESHOLD=3                       # Consecutive failures before alert

# Metrics Collection
METRICS_ENABLED=true                              # Enable metrics collection
METRICS_SAVE_INTERVAL_MINUTES=60                 # Auto-save interval
METRICS_RETENTION_DAYS=30                        # How long to keep metrics

# Performance Monitoring
PERFORMANCE_ALERTS_ENABLED=true                   # Enable performance alerts
CPU_WARNING_THRESHOLD=80                          # CPU usage warning (%)
MEMORY_WARNING_THRESHOLD=85                       # Memory usage warning (%)
DISK_WARNING_THRESHOLD=90                        # Disk usage warning (%)

# Logging
LOG_LEVEL=INFO                                   # Minimum log level
LOG_TO_FILE=true                                 # Enable file logging
LOG_MAX_BYTES=10485760                          # Max log file size (10MB)
LOG_BACKUP_COUNT=5                               # Number of log backups to keep

# Security
RATE_LIMITING_ENABLED=true                       # Enable rate limiting
MAX_COMMANDS_PER_MINUTE=30                       # Rate limit per user
BLACKLIST_ENABLED=true                            # Enable user blacklisting
AUTO_BAN_VIOLATION_THRESHOLD=10                  # Auto-ban after violations
```

## Integration Points

### With All Systems
- **Health Monitoring**: All services report health status
- **Metrics Collection**: System-wide performance tracking
- **Configuration**: Dynamic updates across all modules

### With Chat System
- **Maintenance Mode**: Disable chat during maintenance
- **Performance Monitoring**: Track response times and error rates
- **Rate Limiting**: Prevent abuse and resource exhaustion

### With Voice System
- **Resource Monitoring**: Track voice connections and audio quality
- **Performance Optimization**: Monitor TTS/RVC service health

## Performance Considerations

### 1. Monitoring Overhead
- **Sampling Rates**: Balance monitoring frequency vs overhead
- **Bounded Collections**: Limit memory usage for metrics storage
- **Async Processing**: Non-blocking health checks and metrics

### 2. Alert Fatigue
- **Threshold Tuning**: Set appropriate alert levels
- **Rate Limiting Alerts**: Prevent alert spam
- **Escalation Rules**: Progressive alert severity

### 3. Resource Efficiency
- **Selective Monitoring**: Focus on critical services
- **Batch Operations**: Group health checks together
- **Caching**: Cache health status between checks

## Security Considerations

### 1. Access Control
- **Role-Based Access**: Admin commands restricted to authorized users
- **Command Logging**: All admin actions logged for audit
- **Permission Validation**: Verify permissions before executing actions

### 2. Data Protection
- **Sensitive Config**: Protect configuration with encryption
- **Audit Trail**: Maintain comprehensive action logs
- **Secure Backups**: Encrypt backup files containing sensitive data

## Common Issues and Troubleshooting

### 1. Health Checks Failing
```python
# Manual health check
health_service = HealthCheckService()
health_results = await health_service.check_all_services()
for service, status in health_results.items():
    print(f"{service}: {status['status']} - {status['message']}")

# Check specific service
await health_service._check_discord_api()
```

### 2. Metrics Not Recording
```bash
# Check metrics service status
grep "MetricsService" logs/bot.log | tail -5

# Verify metrics file
ls -la ./data/metrics/
cat ./data/metrics/current.json
```

### 3. Configuration Changes Not Persisting
```python
# Check environment file
import os
print(os.getenv("OLLAMA_TEMPERATURE"))

# Verify config update
print(Config.OLLAMA_TEMPERATURE)

# Manual config reload
Config.validate()
```

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `cogs/system.py` | SystemCog - administrative commands |
| `services/core/health.py` | HealthCheckService - system monitoring |
| `services/core/metrics.py` | MetricsService - performance tracking |
| `utils/error_handlers.py` | Error handling and recovery |
| `utils/logging_config.py` | Logging system configuration |
| `scripts/analyze_performance.py` | Performance analysis tools |

---

**Last Updated**: 2025-12-16
**Version**: 1.0