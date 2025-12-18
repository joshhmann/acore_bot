# Analytics & Monitoring Guide

**Complete guide to the real-time analytics dashboard, metrics interpretation, and health monitoring in acore_bot**

---

## Table of Contents

1. [Overview](#overview)
2. [Dashboard Setup](#dashboard-setup)
3. [Real-Time Analytics](#real-time-analytics)
4. [Metrics Interpretation](#metrics-interpretation)
5. [Health Monitoring](#health-monitoring)
6. [Performance Analytics](#performance-analytics)
7. [Persona Analytics](#persona-analytics)
8. [Alerting & Notifications](#alerting--notifications)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Analytics & Monitoring System provides comprehensive real-time insights into bot performance, user engagement, and system health. Built with FastAPI and WebSocket technology, it delivers live metrics through an interactive web dashboard.

### Key Features

- **Real-Time Dashboard**: Live metrics with WebSocket updates every second
- **Performance Monitoring**: Response times, token usage, error rates
- **Persona Analytics**: Individual character statistics and interaction patterns
- **Health Checks**: Service status and system diagnostics
- **Historical Data**: Time-series metrics with customizable ranges
- **Alert System**: Configurable thresholds with notifications
- **Export Capabilities**: Download metrics as CSV/JSON for analysis

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Bot Events     │ →  │  Metrics Service │ →  │  InfluxDB       │
│                 │    │                  │    │  (Time Series)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                ↓
                        ┌──────────────────┐
                        │ Analytics API    │
                        │ (FastAPI)        │
                        └──────────────────┘
                                ↓
                        ┌──────────────────┐
                        │ Web Dashboard    │
                        │ (WebSocket)      │
                        └──────────────────┘
```

---

## Dashboard Setup

### Prerequisites

- **Python 3.11+** with FastAPI dependencies
- **Network Access** for dashboard (default port 8000)
- **Optional**: Reverse proxy for production deployment

### Enable Analytics

```env
# Enable analytics system
ANALYTICS_ENABLED=true

# Dashboard configuration
ANALYTICS_HOST=localhost
ANALYTICS_PORT=8000
ANALYTICS_API_KEY=your_secure_key_here  # Optional authentication

# Data retention
METRICS_RETENTION_DAYS=30
ANALYTICS_CORS_ORIGINS=["http://localhost:3000"]
```

### Access the Dashboard

#### Local Development

```bash
# Dashboard will be available at:
http://localhost:8000

# With API key authentication:
http://localhost:8000?api_key=your_secure_key_here
```

#### Production Deployment

```bash
# Using reverse proxy (nginx)
https://your-domain.com/analytics

# Behind authentication gateway
https://your-domain.com/dashboard
```

### Dashboard Navigation

The dashboard consists of several sections:

1. **Overview**: Real-time system status and key metrics
2. **Performance**: Response times, throughput, and efficiency metrics  
3. **Personas**: Character-specific analytics and relationships
4. **Users**: User engagement and activity patterns
5. **System**: Resource usage and health monitoring
6. **History**: Historical trends and time-series data

---

## Real-Time Analytics

### WebSocket Updates

The dashboard uses WebSockets for real-time updates:

```javascript
// WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws/metrics');

// Message format
{
  "type": "metrics_update",
  "timestamp": "2025-12-12T10:30:00Z",
  "data": {
    "active_users": 45,
    "messages_per_minute": 12.5,
    "avg_response_time_ms": 1850,
    "error_rate": 0.02,
    "personas": {
      "dagoth_ur": {"messages": 23, "sentiment": 0.3},
      "scav": {"messages": 17, "sentiment": -0.1}
    }
  }
}
```

### Live Metrics

#### System Overview Panel

```json
{
  "uptime": "2 days, 5:32:10",
  "bot_status": "healthy",
  "active_guilds": 3,
  "active_users": 45,
  "total_messages_today": 1234,
  "current_response_time": "1.2s",
  "error_rate_24h": "0.5%"
}
```

#### Real-Time Performance Graphs

- **Response Time Chart**: Last hour of response times (milliseconds)
- **Message Rate**: Messages per minute over last 24 hours
- **Error Rate**: Rolling error rate percentage
- **Token Usage**: Real-time token consumption by model

#### Activity Heatmap

- **Hourly Activity**: Heatmap showing busiest hours
- **Day-of-Week Patterns**: Activity by day of week
- **Channel Activity**: Most active channels
- **User Engagement**: Top active users

---

## Metrics Interpretation

### Response Time Metrics

#### Key Indicators

| Metric | Good | Warning | Critical |
|--------|------|----------|-----------|
| **Avg Response Time** | <2s | 2-5s | >5s |
| **P95 Response Time** | <3s | 3-8s | >8s |
| **P99 Response Time** | <5s | 5-15s | >15s |
| **Time to First Token** | <1s | 1-3s | >3s |

#### Response Time Breakdown

```json
{
  "total_response_time": 1850,  // milliseconds
  "components": {
    "context_building": 150,
    "llm_inference": 1200,
    "response_processing": 100,
    "tts_generation": 300,
    "discord_send": 100
  },
  "percentiles": {
    "p50": 1600,
    "p95": 2800,
    "p99": 4500
  }
}
```

### Token Usage Analytics

#### Consumption Patterns

```json
{
  "token_usage": {
    "daily": {
      "prompt_tokens": 15420,
      "completion_tokens": 8930,
      "total_tokens": 24350,
      "estimated_cost": "$0.12"
    },
    "by_model": {
      "llama3.2": {
        "prompt_tokens": 12000,
        "completion_tokens": 7000,
        "avg_response_time": 1.8
      },
      "claude-3-sonnet": {
        "prompt_tokens": 3420,
        "completion_tokens": 1930,
        "avg_response_time": 2.1
      }
    }
  }
}
```

#### Cost Optimization Insights

- **Model Efficiency**: Compare cost vs performance per model
- **Prompt Optimization**: Identify opportunities for shorter prompts
- **Token Budgeting**: Project monthly costs based on usage

### Error Analysis

#### Error Categories

| Error Type | Common Causes | Severity |
|------------|----------------|-----------|
| **API Timeout** | LLM provider issues | Medium |
| **Rate Limit** | Too many requests | High |
| **Memory Error** | Context overflow | High |
| **Network Error** | Connection issues | Medium |
| **Validation Error** | Invalid input | Low |

#### Error Metrics Dashboard

```json
{
  "error_analysis": {
    "total_errors_24h": 12,
    "error_rate": 0.02,
    "top_errors": [
      {
        "type": "API Timeout",
        "count": 5,
        "percentage": 41.7,
        "last_occurrence": "2025-12-12T09:45:00Z"
      },
      {
        "type": "Rate Limit",
        "count": 3,
        "percentage": 25.0,
        "last_occurrence": "2025-12-12T08:30:00Z"
      }
    ],
    "trend": "decreasing"  // increasing/decreasing/stable
  }
}
```

---

## Health Monitoring

### Service Health Checks

#### Health Endpoint

```bash
# Overall health status
GET /api/health

# Individual service health
GET /api/health/{service_name}
```

#### Health Response Format

```json
{
  "status": "healthy",  // healthy, degraded, unhealthy
  "timestamp": "2025-12-12T10:30:00Z",
  "uptime": "2 days, 5:32:10",
  "services": {
    "ollama": {
      "status": "healthy",
      "response_time_ms": 150,
      "last_check": "2025-12-12T10:29:55Z",
      "details": "Model: llama3.2, GPU: available"
    },
    "tts": {
      "status": "healthy",
      "engine": "kokoro",
      "voice": "am_adam",
      "last_generation": "2025-12-12T10:28:30Z"
    },
    "rag": {
      "status": "healthy",
      "documents_count": 1250,
      "embedding_model": "all-MiniLM-L6-v2",
      "last_query": "2025-12-12T10:29:00Z"
    }
  }
}
```

#### System Resource Monitoring

```json
{
  "system_resources": {
    "cpu": {
      "usage_percent": 25.3,
      "cores": 8,
      "load_average": [1.2, 1.5, 1.8]
    },
    "memory": {
      "total_gb": 16.0,
      "used_gb": 8.2,
      "usage_percent": 51.3,
      "available_gb": 7.8
    },
    "disk": {
      "total_gb": 500.0,
      "used_gb": 125.4,
      "usage_percent": 25.1,
      "free_gb": 374.6
    },
    "network": {
      "bytes_sent": 1048576,
      "bytes_received": 2097152,
      "connections": 45
    }
  }
}
```

### Database Health

#### RAG/Vector Store Status

```json
{
  "database_health": {
    "rag": {
      "status": "healthy",
      "documents_count": 1250,
      "collections_count": 8,
      "vector_dimension": 384,
      "index_status": "ready",
      "last_indexed": "2025-12-12T08:00:00Z"
    },
    "sqlite": {
      "status": "healthy",
      "file_size_mb": 45.2,
      "connections": 3,
      "queries_per_second": 12.5,
      "last_backup": "2025-12-12T06:00:00Z"
    }
  }
}
```

---

## Performance Analytics

### Conversation Analytics

#### Engagement Metrics

```json
{
  "conversation_analytics": {
    "daily_stats": {
      "total_conversations": 234,
      "avg_conversation_length": 8.5,  // messages
      "avg_session_duration": 12.3,  // minutes
      "user_retention_rate": 0.73
    },
    "quality_metrics": {
      "meaningful_responses": 0.85,  // percentage
      "user_satisfaction_score": 4.2,  // 1-5 scale
      "repeat_interaction_rate": 0.45
    }
  }
}
```

#### Response Quality Analysis

- **Coherence Score**: AI model confidence and response coherence
- **Relevance Score**: How well response matches user intent
- **Helpfulness Score**: User feedback on response usefulness
- **Engagement Score**: Follow-up question rate

### LLM Performance

#### Model Comparison

```json
{
  "llm_performance": {
    "models": {
      "llama3.2": {
        "avg_response_time": 1.8,
        "tokens_per_second": 45.2,
        "cost_per_1k_tokens": 0.001,
        "user_satisfaction": 4.1,
        "usage_percentage": 75.3
      },
      "claude-3-sonnet": {
        "avg_response_time": 2.1,
        "tokens_per_second": 38.7,
        "cost_per_1k_tokens": 0.015,
        "user_satisfaction": 4.5,
        "usage_percentage": 24.7
      }
    }
  }
}
```

#### Efficiency Recommendations

Based on performance data, the system provides:

1. **Model Selection**: Recommend best model for use case
2. **Prompt Optimization**: Suggest prompt improvements
3. **Resource Allocation**: Recommend scaling decisions
4. **Cost Optimization**: Identify cost-saving opportunities

---

## Persona Analytics

### Individual Character Metrics

#### Persona Performance Dashboard

```json
{
  "persona_analytics": {
    "dagoth_ur": {
      "basic_stats": {
        "total_messages": 1234,
        "daily_messages": 45.2,
        "avg_response_length": 156,  // characters
        "avg_response_time": 2.1
      },
      "engagement": {
        "user_interactions": 234,
        "repeat_users": 89,
        "relationship_growth": 0.65,  // monthly change
        "banter_participation": 0.42
      },
      "content_analysis": {
        "top_topics": ["morrowind", "philosophy", "divinity"],
        "sentiment_distribution": {
          "positive": 0.35,
          "neutral": 0.50,
          "negative": 0.15
        },
        "response_patterns": {
          "questions_asked": 156,
          "emojis_used": 89,
          "mentions_others": 67
        }
      },
      "evolution": {
        "current_level": 12,
        "total_xp": 2450,
        "milestones_completed": 8,
        "unlocked_traits": ["empathy", "wisdom", "mentoring"]
      }
    }
  }
}
```

### Inter-Persona Relationships

#### Relationship Matrix

```json
{
  "persona_relationships": {
    "relationship_matrix": {
      "dagoth_ur": {
        "scav": {"affinity": 72, "stage": "friends", "interactions": 45},
        "toad": {"affinity": 55, "stage": "frenemies", "interactions": 23},
        "hal9000": {"affinity": 68, "stage": "friends", "interactions": 31}
      },
      "scav": {
        "dagoth_ur": {"affinity": 72, "stage": "friends", "interactions": 45},
        "toad": {"affinity": 85, "stage": "besties", "interactions": 67}
      }
    },
    "analytics": {
      "total_interactions": 1247,
      "avg_affinity": 61.3,
      "relationship_trends": "improving",
      "most_active_pair": ["scav", "toad"]
    }
  }
}
```

#### Banter Analysis

```json
{
  "banter_analytics": {
    "daily_banter_exchanges": 23,
    "success_rate": 0.78,  // led to continued conversation
    "avg_exchange_length": 3.2,  // messages per exchange
    "popular_topics": ["gaming", "movies", "food"],
    "sentiment_impact": {
      "positive_exchanges": 0.65,
      "neutral_exchanges": 0.30,
      "negative_exchanges": 0.05
    }
  }
}
```

### User-Persona Interaction Patterns

#### User Preference Analysis

```json
{
  "user_persona_analytics": {
    "user_preferences": {
      "user_123": {
        "favorite_persona": "scav",
        "interaction_frequency": 12.3,  // per week
        "relationship_levels": {
          "dagoth_ur": 65,
          "scav": 85,
          "toad": 45
        },
        "preferred_topics": ["gaming", "humor"],
        "interaction_times": ["20:00", "21:00", "22:00"]
      }
    },
    "persona_popularity": {
      "most_engaged": "scav",
      "highest_satisfaction": "hal9000",
      "fastest_response": "dagoth_ur"
    }
  }
}
```

---

## Alerting & Notifications

### Alert Configuration

```env
# Alert thresholds
ALERT_RESPONSE_TIME_MS=5000      # Alert if avg response time > 5s
ALERT_ERROR_RATE_PERCENT=5.0       # Alert if error rate > 5%
ALERT_CPU_PERCENT=80.0           # Alert if CPU > 80%
ALERT_MEMORY_PERCENT=85.0        # Alert if memory > 85%
ALERT_DISK_PERCENT=90.0           # Alert if disk > 90%

# Notification settings
ALERT_WEBHOOK_URL=https://hooks.slack.com/your-webhook
ALERT_EMAIL_SMTP=smtp.gmail.com
ALERT_EMAIL_RECIPIENTS=admin@example.com
```

### Alert Types

#### Performance Alerts

```json
{
  "alert_type": "performance",
  "severity": "warning",
  "message": "Average response time exceeded threshold",
  "details": {
    "current_avg": 5200,  // milliseconds
    "threshold": 5000,
    "duration": "5 minutes",
    "affected_service": "ollama"
  },
  "timestamp": "2025-12-12T10:30:00Z"
}
```

#### Health Alerts

```json
{
  "alert_type": "health",
  "severity": "critical",
  "message": "Service unhealthy detected",
  "details": {
    "service": "tts",
    "status": "unhealthy",
    "last_successful_check": "2025-12-12T10:25:00Z",
    "error_message": "Connection timeout to Kokoro API"
  },
  "timestamp": "2025-12-12T10:30:00Z"
}
```

#### Resource Alerts

```json
{
  "alert_type": "resource",
  "severity": "warning", 
  "message": "High memory usage detected",
  "details": {
    "resource": "memory",
    "current_usage": 87.2,  // percentage
    "threshold": 85.0,
    "available_gb": 2.1,
    "trend": "increasing"
  },
  "timestamp": "2025-12-12T10:30:00Z"
}
```

### Notification Channels

#### Slack Integration

```bash
# Configure Slack webhook
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Alert message format
{
  "text": "🚨 Bot Alert",
  "attachments": [
    {
      "color": "danger",
      "fields": [
        {"title": "Type", "value": "Performance"},
        {"title": "Message", "value": "High response time detected"},
        {"title": "Current", "value": "5.2s"},
        {"title": "Threshold", "value": "5.0s"}
      ]
    }
  ]
}
```

#### Email Notifications

```bash
# SMTP configuration
ALERT_EMAIL_SMTP=smtp.gmail.com
ALERT_EMAIL_PORT=587
ALERT_EMAIL_USERNAME=your-email@gmail.com
ALERT_EMAIL_PASSWORD=your-app-password
ALERT_EMAIL_RECIPIENTS=admin@example.com,ops@example.com
```

#### Discord Notifications

```bash
# Send alerts to Discord channel
ALERT_DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR/WEBHOOK
ALERT_DISCORD_CHANNEL_ID=123456789012345678
```

---

## Troubleshooting

### Common Analytics Issues

#### Dashboard Not Loading

**Symptoms:**
- Dashboard shows loading spinner
- WebSocket connection failed
- 502 Bad Gateway error

**Solutions:**

1. **Check Analytics Service:**
```bash
# Verify analytics is enabled
grep ANALYTICS_ENABLED .env

# Check if service is running
curl http://localhost:8000/api/health
```

2. **Check Port Availability:**
```bash
# Verify port is not blocked
netstat -tlnp | grep 8000

# Check firewall settings
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS
```

3. **Check CORS Configuration:**
```env
# Allow dashboard origin
ANALYTICS_CORS_ORIGINS=["http://localhost:3000", "https://your-domain.com"]
```

#### Metrics Not Updating

**Symptoms:**
- Stale data shown on dashboard
- WebSocket messages not receiving
- Last updated timestamp old

**Solutions:**

1. **Check Metrics Service:**
```bash
# Check metrics service health
curl http://localhost:8000/api/metrics

# Verify metrics are being recorded
grep "metrics.record" logs/bot.log | tail -10
```

2. **Check Background Tasks:**
```bash
# Check if metrics auto-save is running
ps aux | grep "metrics.*save"

# Verify background task status
curl http://localhost:8000/api/background-tasks
```

3. **Restart Services:**
```bash
# Restart bot to refresh analytics
python main.py

# Or just restart metrics if isolated
kill -USR2 <bot_pid>  # Send reload signal
```

#### High Memory Usage in Analytics

**Symptoms:**
- Dashboard using excessive memory
- Slow loading times
- Browser crashes

**Solutions:**

1. **Reduce Data Retention:**
```env
# Keep less historical data
METRICS_RETENTION_DAYS=7  # Instead of 30
```

2. **Optimize Dashboard Settings:**
```javascript
// In browser console, adjust chart settings
localStorage.setItem('maxDataPoints', '100');  // Reduce from 1000
localStorage.setItem('refreshInterval', '5000');  // Slower updates
```

3. **Enable Data Compression:**
```env
# Compress WebSocket data
WEBSOCKET_COMPRESSION=true
```

### Debug Commands

#### Analytics Debug Endpoint

```bash
# Detailed system status
GET /api/debug/analytics

# Response includes:
# - Service status
# - Memory usage by component
# - WebSocket connection stats
# - Background task status
# - Recent errors
```

#### Performance Profiling

```bash
# Enable profiling
curl -X POST http://localhost:8000/api/profiling/enable \
  -H "Content-Type: application/json" \
  -d '{"duration": 300}'  # 5 minutes

# Get profiling results
GET /api/profiling/results
```

#### Log Analysis

```bash
# Analytics-specific logs
grep "analytics" logs/bot.log | tail -50

# Performance logs
grep "performance" logs/bot.log | tail -50

# Error logs
grep "ERROR" logs/bot.log | tail -20
```

### Getting Help

1. **Dashboard Debug Info**: Access `/api/debug` for system status
2. **Check Logs**: `logs/bot.log` for analytics-related errors
3. **Verify Configuration**: Use `/api/config` to check settings
4. **Community Support**: GitHub Issues with dashboard screenshots

---

## Best Practices

### Monitoring Setup

1. **Set Appropriate Thresholds**: Configure alerts based on your baseline
2. **Monitor Trends**: Watch for gradual performance degradation
3. **Correlate Metrics**: Look for relationships between different metrics
4. **Regular Health Checks**: Schedule periodic system reviews

### Performance Optimization

1. **Track Response Times**: Identify slow components
2. **Monitor Resource Usage**: Prevent resource exhaustion
3. **Analyze User Behavior**: Understand usage patterns
4. **Optimize Based on Data**: Use analytics for optimization decisions

### Alert Management

1. **Avoid Alert Fatigue**: Set meaningful thresholds
2. **Use Severity Levels**: Prioritize critical alerts
3. **Monitor Alert Effectiveness**: Adjust based on false positives
4. **Document Alert Procedures**: Clear response procedures for each alert type

---

**Ready to monitor your bot?** Follow the [Dashboard Setup](#dashboard-setup) section and gain deep insights into your bot's performance and user engagement!