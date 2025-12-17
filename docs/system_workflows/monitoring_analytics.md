# Monitoring and Analytics System Workflow

This document describes the complete monitoring and analytics system in acore_bot, including real-time dashboards, performance tracking, user behavior analysis, and operational intelligence workflows.

## Overview

The monitoring and analytics system provides **comprehensive visibility** into bot operations through **real-time dashboards**, **automated metrics collection**, **performance analysis**, and **operational intelligence** for optimal system management.

## Architecture

### Component Structure
```
services/analytics/
└── dashboard.py             # Analytics dashboard web interface

services/core/
├── metrics.py              # Core metrics collection service
└── health.py               # Health monitoring integration

templates/dashboard/
└── index.html              # Dashboard web interface

scripts/
├── analyze_performance.py  # Performance analysis tools
├── profile_performance.py   # User behavior analysis
└── benchmark_optimizations.py # System benchmarking

data/
├── metrics/                # Metrics storage
├── analytics/              # Analysis results
└── dashboard/              # Dashboard data
```

### Service Dependencies
```
Monitoring Dependencies:
├── FastAPI                 # Dashboard web server
├── WebSocket               # Real-time updates
├── Time Series Database    # Metrics storage
├── Chart.js                # Dashboard visualization
├── System Metrics          # CPU, memory, disk usage
├── Application Metrics     # Bot-specific metrics
└── Analytics Engine        # Data analysis and insights
```

## Analytics Dashboard

### 1. Dashboard Server
**File**: `services/analytics/dashboard.py:45-234`

#### 1.1 FastAPI Dashboard Application
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

class AnalyticsDashboard:
    """Real-time analytics dashboard for bot monitoring."""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.app = FastAPI(title="Bot Analytics Dashboard")
        self.active_connections: list[WebSocket] = []
        self.metrics_service = None
        self.health_service = None
        
        # Configure routes
        self._setup_routes()
        
        # Setup static files
        self.app.mount("/static", StaticFiles(directory="templates/dashboard"), name="static")
        
        # Background data update task
        self.update_task = None

    def _setup_routes(self):
        """Setup dashboard API routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_page():
            """Serve dashboard HTML page."""
            template_path = Path("templates/dashboard/index.html")
            if template_path.exists():
                with open(template_path, 'r') as f:
                    return HTMLResponse(content=f.read())
            else:
                return HTMLResponse(content="<h1>Dashboard template not found</h1>", status_code=404)
        
        @self.app.get("/api/metrics/realtime")
        async def get_realtime_metrics():
            """Get current real-time metrics."""
            if not self.metrics_service:
                return {"error": "Metrics service not available"}
            
            return await self._get_realtime_data()
        
        @self.app.get("/api/metrics/historical")
        async def get_historical_metrics(hours: int = 24):
            """Get historical metrics data."""
            if not self.metrics_service:
                return {"error": "Metrics service not available"}
            
            return await self._get_historical_data(hours)
        
        @self.app.get("/api/health/status")
        async def get_health_status():
            """Get current health status."""
            if not self.health_service:
                return {"error": "Health service not available"}
            
            return await self.health_service.check_all_services()
        
        @self.app.get("/api/analytics/insights")
        async def get_analytics_insights():
            """Get analytics insights and recommendations."""
            return await self._generate_analytics_insights()
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket for real-time updates."""
            await websocket.accept()
            self.active_connections.append(websocket)
            
            try:
                while True:
                    # Send real-time updates
                    data = await self._get_realtime_data()
                    await websocket.send_text(json.dumps(data))
                    await asyncio.sleep(2)  # Update every 2 seconds
                    
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)

    async def start_dashboard(self):
        """Start the dashboard server."""
        import uvicorn
        
        # Start background update task
        self.update_task = asyncio.create_task(self._background_updates())
        
        # Start FastAPI server
        config = uvicorn.Config(
            app=self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        await server.serve()

    async def _get_realtime_data(self) -> Dict:
        """Collect real-time dashboard data."""
        
        try:
            # Basic metrics
            current_metrics = await self.metrics_service.get_current_metrics()
            
            # System metrics
            import psutil
            system_metrics = {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'network_sent': psutil.net_io_counters().bytes_sent,
                'network_recv': psutil.net_io_counters().bytes_recv
            }
            
            # Service health
            health_status = await self.health_service.check_all_services()
            
            # Active conversations
            active_conversations = self._get_active_conversations()
            
            # Recent activity
            recent_activity = self._get_recent_activity()
            
            return {
                'timestamp': datetime.now().isoformat(),
                'metrics': current_metrics,
                'system': system_metrics,
                'health': health_status,
                'conversations': active_conversations,
                'activity': recent_activity
            }
            
        except Exception as e:
            logger.error(f"Error getting real-time data: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    async def _get_historical_data(self, hours: int) -> Dict:
        """Get historical metrics data for charts."""
        
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            # Time series data
            historical_data = {
                'messages_over_time': await self._get_messages_timeline(start_time, end_time),
                'response_times': await self._get_response_times_timeline(start_time, end_time),
                'error_rates': await self._get_error_rates_timeline(start_time, end_time),
                'active_users': await self._get_active_users_timeline(start_time, end_time),
                'voice_usage': await self._get_voice_usage_timeline(start_time, end_time)
            }
            
            # Aggregate statistics
            aggregate_stats = {
                'total_messages': historical_data['messages_over_time']['total'],
                'avg_response_time': historical_data['response_times']['average'],
                'error_rate': historical_data['error_rates']['current'],
                'peak_users': historical_data['active_users']['peak'],
                'total_voice_minutes': historical_data['voice_usage']['total_minutes']
            }
            
            return {
                'period': f"{hours}h",
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'timeline': historical_data,
                'aggregates': aggregate_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return {'error': str(e)}

    async def _generate_analytics_insights(self) -> Dict:
        """Generate AI-powered analytics insights."""
        
        try:
            insights = {
                'performance': await self._analyze_performance_trends(),
                'user_behavior': await self._analyze_user_behavior(),
                'system_health': await self._analyze_system_health(),
                'recommendations': await self._generate_recommendations()
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return {'error': str(e)}

    async def _analyze_performance_trends(self) -> Dict:
        """Analyze performance trends and patterns."""
        
        # Get performance data
        metrics = await self.metrics_service.get_current_metrics()
        
        performance_analysis = {
            'trend': 'stable',  # improving, degrading, stable
            'response_time_status': 'normal',  # fast, normal, slow
            'error_rate_status': 'healthy',    # excellent, healthy, concerning
            'efficiency_score': 0.0,          # 0-100
            'bottlenecks': []
        }
        
        # Analyze response times
        if metrics['average_response_time'] < 1000:
            performance_analysis['response_time_status'] = 'fast'
        elif metrics['average_response_time'] > 3000:
            performance_analysis['response_time_status'] = 'slow'
            performance_analysis['bottlenecks'].append('LLM response time')
        
        # Analyze error rates
        if metrics['error_rate'] < 0.01:
            performance_analysis['error_rate_status'] = 'excellent'
        elif metrics['error_rate'] > 0.05:
            performance_analysis['error_rate_status'] = 'concerning'
            performance_analysis['bottlenecks'].append('High error rate')
        
        # Calculate efficiency score
        response_score = max(0, 100 - (metrics['average_response_time'] / 100))  # Max 100, min 0
        error_score = max(0, 100 - (metrics['error_rate'] * 1000))  # Max 100, min 0
        performance_analysis['efficiency_score'] = (response_score + error_score) / 2
        
        return performance_analysis

    async def _analyze_user_behavior(self) -> Dict:
        """Analyze user behavior patterns."""
        
        behavior_analysis = {
            'active_users': 0,
            'peak_hours': [],
            'popular_features': {},
            'user_retention': 'stable',  # improving, declining, stable
            'engagement_score': 0.0      # 0-100
        }
        
        # Get user activity data
        if hasattr(self.metrics_service, 'metrics'):
            metrics = self.metrics_service.metrics
            
            # Calculate active users
            recent_activity = metrics.get('daily_activity', {})
            if recent_activity:
                latest_date = max(recent_activity.keys())
                behavior_analysis['active_users'] = recent_activity[latest_date]
            
            # Analyze peak hours
            hourly_activity = metrics.get('hourly_activity', {})
            if hourly_activity:
                sorted_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)
                behavior_analysis['peak_hours'] = [hour for hour, count in sorted_hours[:3]]
            
            # Analyze popular features
            command_usage = metrics.get('commands_used', {})
            behavior_analysis['popular_features'] = dict(
                sorted(command_usage.items(), key=lambda x: x[1], reverse=True)[:5]
            )
            
            # Calculate engagement score
            total_messages = metrics.get('messages_processed', 0)
            total_responses = metrics.get('responses_generated', 0)
            
            if total_messages > 0:
                response_ratio = total_responses / total_messages
                behavior_analysis['engagement_score'] = min(100, response_ratio * 100)
        
        return behavior_analysis

    async def _generate_recommendations(self) -> List[Dict]:
        """Generate actionable recommendations based on analytics."""
        
        recommendations = []
        
        try:
            metrics = await self.metrics_service.get_current_metrics()
            health_status = await self.health_service.check_all_services()
            
            # Performance recommendations
            if metrics['average_response_time'] > 3000:
                recommendations.append({
                    'type': 'performance',
                    'priority': 'high',
                    'title': 'High Response Times Detected',
                    'description': 'Average response time exceeds 3 seconds',
                    'action': 'Consider optimizing LLM configuration or upgrading hardware'
                })
            
            # Error rate recommendations
            if metrics['error_rate'] > 0.05:
                recommendations.append({
                    'type': 'reliability',
                    'priority': 'medium',
                    'title': 'High Error Rate',
                    'description': f'Error rate is {metrics["error_rate"]:.1%}',
                    'action': 'Review error logs and implement better error handling'
                })
            
            # Resource recommendations
            if metrics['memory_usage'] > 800:  # 800MB
                recommendations.append({
                    'type': 'resource',
                    'priority': 'medium',
                    'title': 'High Memory Usage',
                    'description': f'Memory usage is {metrics["memory_usage"]:.1f}MB',
                    'action': 'Consider implementing memory cleanup or increasing available memory'
                })
            
            # Health recommendations
            unhealthy_services = [
                service for service, status in health_status.items()
                if status['status'] == 'unhealthy'
            ]
            
            if unhealthy_services:
                recommendations.append({
                    'type': 'health',
                    'priority': 'high',
                    'title': 'Unhealthy Services Detected',
                    'description': f'Services with issues: {", ".join(unhealthy_services)}',
                    'action': 'Check service configuration and restart if necessary'
                })
            
            # Engagement recommendations
            if metrics.get('responses_per_minute', 0) < 1:
                recommendations.append({
                    'type': 'engagement',
                    'priority': 'low',
                    'title': 'Low Engagement',
                    'description': 'Bot responses per minute is low',
                    'action': 'Consider adjusting response triggers or improving content relevance'
                })
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append({
                'type': 'system',
                'priority': 'high',
                'title': 'Analytics Error',
                'description': f'Error generating recommendations: {e}',
                'action': 'Check analytics service configuration'
            })
        
        return recommendations

    async def _background_updates(self):
        """Background task for updating dashboard data."""
        
        while True:
            try:
                # Update all connected clients
                if self.active_connections:
                    data = await self._get_realtime_data()
                    
                    # Send to all connected clients
                    disconnected_clients = []
                    for connection in self.active_connections:
                        try:
                            await connection.send_text(json.dumps(data))
                        except Exception:
                            disconnected_clients.append(connection)
                    
                    # Remove disconnected clients
                    for client in disconnected_clients:
                        self.active_connections.remove(client)
                
                await asyncio.sleep(2)  # Update every 2 seconds
                
            except Exception as e:
                logger.error(f"Background update error: {e}")
                await asyncio.sleep(10)  # Wait before retrying
```

### 2. Dashboard Frontend
**File**: `templates/dashboard/index.html:1-345`

#### 2.1 HTML Dashboard Interface
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Analytics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a1a; color: #fff; 
        }
        .header { 
            background: #2d3748; padding: 1rem; 
            border-bottom: 2px solid #4299e1; 
        }
        .header h1 { color: #4299e1; }
        .container { max-width: 1400px; margin: 0 auto; padding: 1rem; }
        .metrics-grid { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 1rem; margin-bottom: 2rem; 
        }
        .metric-card { 
            background: #2d3748; border-radius: 8px; padding: 1.5rem; 
            border: 1px solid #4a5568; 
        }
        .metric-card h3 { color: #63b3ed; margin-bottom: 0.5rem; }
        .metric-value { font-size: 2rem; font-weight: bold; color: #68d391; }
        .metric-change { font-size: 0.9rem; margin-top: 0.5rem; }
        .positive { color: #68d391; }
        .negative { color: #fc8181; }
        .charts-grid { 
            display: grid; grid-template-columns: 1fr 1fr; 
            gap: 1rem; margin-bottom: 2rem; 
        }
        .chart-container { 
            background: #2d3748; border-radius: 8px; padding: 1rem; 
            border: 1px solid #4a5568; 
        }
        .chart-container h3 { color: #63b3ed; margin-bottom: 1rem; }
        .health-status { 
            background: #2d3748; border-radius: 8px; padding: 1rem; 
            margin-bottom: 2rem; 
        }
        .service-status { 
            display: flex; justify-content: space-between; 
            align-items: center; padding: 0.5rem 0; 
        }
        .status-indicator { 
            width: 12px; height: 12px; border-radius: 50%; 
            display: inline-block; margin-right: 0.5rem; 
        }
        .status-healthy { background: #68d391; }
        .status-degraded { background: #f6ad55; }
        .status-unhealthy { background: #fc8181; }
        .insights { 
            background: #2d3748; border-radius: 8px; padding: 1rem; 
        }
        .recommendation { 
            background: #4a5568; border-radius: 6px; padding: 1rem; 
            margin-bottom: 1rem; 
        }
        .high-priority { border-left: 4px solid #fc8181; }
        .medium-priority { border-left: 4px solid #f6ad55; }
        .low-priority { border-left: 4px solid #68d391; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Bot Analytics Dashboard</h1>
        <p>Real-time monitoring and analytics for acore_bot</p>
    </div>

    <div class="container">
        <!-- Real-time Metrics -->
        <div class="metrics-grid">
            <div class="metric-card">
                <h3>📊 Messages Processed</h3>
                <div class="metric-value" id="messages-processed">-</div>
                <div class="metric-change" id="messages-change">-</div>
            </div>
            <div class="metric-card">
                <h3>⚡ Avg Response Time</h3>
                <div class="metric-value" id="response-time">-</div>
                <div class="metric-change" id="response-change">-</div>
            </div>
            <div class="metric-card">
                <h3>🔥 Error Rate</h3>
                <div class="metric-value" id="error-rate">-</div>
                <div class="metric-change" id="error-change">-</div>
            </div>
            <div class="metric-card">
                <h3>💾 Memory Usage</h3>
                <div class="metric-value" id="memory-usage">-</div>
                <div class="metric-change" id="memory-change">-</div>
            </div>
        </div>

        <!-- System Health -->
        <div class="health-status">
            <h3>🏥 System Health</h3>
            <div id="health-services">
                <!-- Health status populated by JavaScript -->
            </div>
        </div>

        <!-- Charts -->
        <div class="charts-grid">
            <div class="chart-container">
                <h3>📈 Message Volume</h3>
                <canvas id="messages-chart"></canvas>
            </div>
            <div class="chart-container">
                <h3>⏱️ Response Times</h3>
                <canvas id="response-times-chart"></canvas>
            </div>
        </div>

        <!-- Insights and Recommendations -->
        <div class="insights">
            <h3>💡 Analytics Insights</h3>
            <div id="recommendations">
                <!-- Recommendations populated by JavaScript -->
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection for real-time updates
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        
        // Chart instances
        let messagesChart = null;
        let responseTimesChart = null;
        
        // Initialize charts
        function initCharts() {
            // Messages chart
            const messagesCtx = document.getElementById('messages-chart').getContext('2d');
            messagesChart = new Chart(messagesCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Messages per Minute',
                        data: [],
                        borderColor: '#4299e1',
                        backgroundColor: 'rgba(66, 153, 225, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#4a5568' } },
                        x: { grid: { color: '#4a5568' } }
                    },
                    plugins: {
                        legend: { labels: { color: '#fff' } }
                    }
                }
            });
            
            // Response times chart
            const responseCtx = document.getElementById('response-times-chart').getContext('2d');
            responseTimesChart = new Chart(responseCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Response Time (ms)',
                        data: [],
                        borderColor: '#68d391',
                        backgroundColor: 'rgba(104, 211, 145, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#4a5568' } },
                        x: { grid: { color: '#4a5568' } }
                    },
                    plugins: {
                        legend: { labels: { color: '#fff' } }
                    }
                }
            });
        }
        
        // Update metrics
        function updateMetrics(data) {
            if (!data.metrics) return;
            
            document.getElementById('messages-processed').textContent = data.metrics.messages_processed || '-';
            document.getElementById('response-time').textContent = 
                data.metrics.average_response_time ? `${Math.round(data.metrics.average_response_time)}ms` : '-';
            document.getElementById('error-rate').textContent = 
                data.metrics.error_rate ? `${(data.metrics.error_rate * 100).toFixed(1)}%` : '-';
            document.getElementById('memory-usage').textContent = 
                data.system && data.system.memory_percent ? `${data.system.memory_percent.toFixed(1)}%` : '-';
        }
        
        // Update health status
        function updateHealthStatus(data) {
            if (!data.health) return;
            
            const healthContainer = document.getElementById('health-services');
            healthContainer.innerHTML = '';
            
            for (const [service, status] of Object.entries(data.health)) {
                const statusClass = `status-${status.status}`;
                const statusDiv = document.createElement('div');
                statusDiv.className = 'service-status';
                statusDiv.innerHTML = `
                    <div>
                        <span class="status-indicator ${statusClass}"></span>
                        <span>${service}</span>
                    </div>
                    <div>${status.message || status.status}</div>
                `;
                healthContainer.appendChild(statusDiv);
            }
        }
        
        // Update recommendations
        function updateRecommendations(insights) {
            if (!insights || !insights.recommendations) return;
            
            const recContainer = document.getElementById('recommendations');
            recContainer.innerHTML = '';
            
            insights.recommendations.forEach(rec => {
                const recDiv = document.createElement('div');
                recDiv.className = `recommendation ${rec.priority}-priority`;
                recDiv.innerHTML = `
                    <h4>${rec.title}</h4>
                    <p>${rec.description}</p>
                    <p><strong>Action:</strong> ${rec.action}</p>
                    <p><small>Priority: ${rec.priority} | Type: ${rec.type}</small></p>
                `;
                recContainer.appendChild(recDiv);
            });
        }
        
        // WebSocket message handler
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            updateMetrics(data);
            updateHealthStatus(data);
            
            // Update charts (simplified - would need more sophisticated time handling)
            if (data.metrics && messagesChart) {
                const now = new Date().toLocaleTimeString();
                
                // Update messages chart
                if (messagesChart.data.labels.length > 20) {
                    messagesChart.data.labels.shift();
                    messagesChart.data.datasets[0].data.shift();
                }
                messagesChart.data.labels.push(now);
                messagesChart.data.datasets[0].data.push(data.metrics.responses_per_minute || 0);
                messagesChart.update('none');
                
                // Update response times chart
                if (responseTimesChart.data.labels.length > 20) {
                    responseTimesChart.data.labels.shift();
                    responseTimesChart.data.datasets[0].data.shift();
                }
                responseTimesChart.data.labels.push(now);
                responseTimesChart.data.datasets[0].data.push(data.metrics.average_response_time || 0);
                responseTimesChart.update('none');
            }
        };
        
        // Load initial data
        async function loadInitialData() {
            try {
                // Load historical data
                const response = await fetch('/api/metrics/historical?hours=24');
                const data = await response.json();
                
                // Update charts with historical data
                if (data.timeline && data.timeline.messages_over_time) {
                    // ... populate charts with historical data
                }
                
                // Load insights
                const insightsResponse = await fetch('/api/analytics/insights');
                const insights = await insightsResponse.json();
                updateRecommendations(insights);
                
            } catch (error) {
                console.error('Error loading initial data:', error);
            }
        }
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            initCharts();
            loadInitialData();
        });
    </script>
</body>
</html>
```

### 3. Performance Analysis Tools
**File**: `scripts/analyze_performance.py:34-156`

#### 3.1 Performance Analysis Script
```python
#!/usr/bin/env python3
"""
Performance analysis tool for acore_bot.
Generates detailed performance reports and optimization recommendations.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict

class PerformanceAnalyzer:
    """Advanced performance analysis and reporting."""
    
    def __init__(self, metrics_path: str = "./data/metrics"):
        self.metrics_path = Path(metrics_path)
        self.analysis_results = {}
        
    async def run_comprehensive_analysis(self) -> Dict:
        """Run comprehensive performance analysis."""
        
        print("🔍 Starting comprehensive performance analysis...")
        
        # 1. Load metrics data
        metrics_data = await self._load_metrics_data()
        
        # 2. Analyze different aspects
        self.analysis_results = {
            'overview': await self._analyze_overview(metrics_data),
            'response_performance': await self._analyze_response_performance(metrics_data),
            'resource_usage': await self._analyze_resource_usage(metrics_data),
            'user_engagement': await self._analyze_user_engagement(metrics_data),
            'error_analysis': await self._analyze_errors(metrics_data),
            'optimization_recommendations': await self._generate_optimization_recommendations(metrics_data)
        }
        
        # 3. Generate report
        await self._generate_report()
        
        # 4. Generate visualizations
        await self._generate_visualizations()
        
        return self.analysis_results

    async def _analyze_response_performance(self, metrics_data: Dict) -> Dict:
        """Analyze response time performance."""
        
        response_times = metrics_data.get('response_times', [])
        
        if not response_times:
            return {'error': 'No response time data available'}
        
        # Calculate statistics
        analysis = {
            'count': len(response_times),
            'mean': sum(response_times) / len(response_times),
            'median': sorted(response_times)[len(response_times) // 2],
            'min': min(response_times),
            'max': max(response_times),
            'p95': sorted(response_times)[int(len(response_times) * 0.95)],
            'p99': sorted(response_times)[int(len(response_times) * 0.99)]
        }
        
        # Performance classification
        if analysis['mean'] < 500:
            performance_level = 'excellent'
        elif analysis['mean'] < 1000:
            performance_level = 'good'
        elif analysis['mean'] < 2000:
            performance_level = 'acceptable'
        else:
            performance_level = 'poor'
        
        analysis['performance_level'] = performance_level
        
        # Time-based analysis
        time_analysis = await self._analyze_response_times_by_time(response_times)
        analysis['time_patterns'] = time_analysis
        
        return analysis

    async def _analyze_user_engagement(self, metrics_data: Dict) -> Dict:
        """Analyze user engagement patterns."""
        
        engagement = {
            'daily_activity': metrics_data.get('daily_activity', {}),
            'hourly_activity': metrics_data.get('hourly_activity', {}),
            'popular_commands': metrics_data.get('commands_used', {}),
            'total_interactions': metrics_data.get('messages_processed', 0)
        }
        
        # Calculate engagement metrics
        if engagement['daily_activity']:
            recent_days = sorted(engagement['daily_activity'].items())[-7:]
            if recent_days:
                avg_daily = sum(count for _, count in recent_days) / len(recent_days)
                engagement['avg_daily_interactions'] = avg_daily
                
                # Trend analysis
                if len(recent_days) >= 3:
                    early_avg = sum(count for _, count in recent_days[:3]) / 3
                    recent_avg = sum(count for _, count in recent_days[-3:]) / 3
                    
                    if recent_avg > early_avg * 1.1:
                        engagement['trend'] = 'increasing'
                    elif recent_avg < early_avg * 0.9:
                        engagement['trend'] = 'decreasing'
                    else:
                        engagement['trend'] = 'stable'
        
        # Peak hours analysis
        if engagement['hourly_activity']:
            sorted_hours = sorted(engagement['hourly_activity'].items(), key=lambda x: x[1], reverse=True)
            engagement['peak_hours'] = [hour for hour, _ in sorted_hours[:3]]
            engagement['off_peak_hours'] = [hour for hour, _ in sorted_hours[-3:]]
        
        return engagement

    async def _generate_optimization_recommendations(self, metrics_data: Dict) -> List[Dict]:
        """Generate specific optimization recommendations."""
        
        recommendations = []
        
        # Response time recommendations
        response_performance = await self._analyze_response_performance(metrics_data)
        if response_performance.get('mean', 0) > 2000:
            recommendations.append({
                'category': 'performance',
                'priority': 'high',
                'title': 'Optimize Response Times',
                'description': f"Average response time is {response_performance['mean']:.0f}ms",
                'recommendations': [
                    'Consider using faster LLM models for simple queries',
                    'Implement response caching for common questions',
                    'Optimize context building to reduce token usage',
                    'Consider upgrading hardware resources'
                ]
            })
        
        # Error rate recommendations
        error_analysis = await self._analyze_errors(metrics_data)
        if error_analysis.get('error_rate', 0) > 0.05:
            recommendations.append({
                'category': 'reliability',
                'priority': 'high',
                'title': 'Reduce Error Rate',
                'description': f"Error rate is {error_analysis['error_rate']:.1%}",
                'recommendations': [
                    'Implement better error handling and retry logic',
                    'Add input validation to prevent malformed requests',
                    'Monitor external service dependencies',
                    'Implement circuit breakers for external APIs'
                ]
            })
        
        # Memory usage recommendations
        resource_usage = await self._analyze_resource_usage(metrics_data)
        if resource_usage.get('memory_trend') == 'increasing':
            recommendations.append({
                'category': 'resources',
                'priority': 'medium',
                'title': 'Optimize Memory Usage',
                'description': 'Memory usage showing increasing trend',
                'recommendations': [
                    'Implement memory cleanup routines',
                    'Use bounded collections for caches',
                    'Optimize data structures to reduce memory footprint',
                    'Consider implementing memory pooling'
                ]
            })
        
        # User engagement recommendations
        engagement = await self._analyze_user_engagement(metrics_data)
        if engagement.get('trend') == 'decreasing':
            recommendations.append({
                'category': 'engagement',
                'priority': 'medium',
                'title': 'Improve User Engagement',
                'description': 'User engagement trend is decreasing',
                'recommendations': [
                    'Review and improve response quality',
                    'Add new features or commands',
                    'Implement proactive engagement features',
                    'Survey users for feedback and suggestions'
                ]
            })
        
        return recommendations

    async def _generate_report(self) -> None:
        """Generate comprehensive performance report."""
        
        report_path = Path(f"./reports/performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        report_path.parent.mkdir(exist_ok=True)
        
        report_content = f"""# Performance Analysis Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

{self._generate_executive_summary()}

## Detailed Analysis

### Response Performance
{self._format_response_analysis()}

### Resource Usage
{self._format_resource_analysis()}

### User Engagement
{self._format_engagement_analysis()}

### Error Analysis
{self._format_error_analysis()}

## Optimization Recommendations

{self._format_recommendations()}

## Technical Details

{self._generate_technical_details()}
"""
        
        with open(report_path, 'w') as f:
            f.write(report_content)
        
        print(f"📊 Performance report generated: {report_path}")

    def _generate_executive_summary(self) -> str:
        """Generate executive summary of analysis."""
        
        overview = self.analysis_results.get('overview', {})
        response_perf = self.analysis_results.get('response_performance', {})
        engagement = self.analysis_results.get('user_engagement', {})
        
        summary_points = []
        
        # Overall health
        if response_perf.get('performance_level') == 'excellent':
            summary_points.append("✅ Response times are excellent")
        elif response_perf.get('performance_level') == 'poor':
            summary_points.append("⚠️ Response times need improvement")
        
        # User engagement
        if engagement.get('trend') == 'increasing':
            summary_points.append("📈 User engagement is growing")
        elif engagement.get('trend') == 'decreasing':
            summary_points.append("📉 User engagement is declining")
        
        # Total activity
        total_interactions = engagement.get('total_interactions', 0)
        summary_points.append(f"💬 Total interactions: {total_interactions:,}")
        
        return "\n".join(summary_points)

# Main execution
async def main():
    """Main execution function."""
    analyzer = PerformanceAnalyzer()
    
    try:
        results = await analyzer.run_comprehensive_analysis()
        print("\n✅ Analysis completed successfully!")
        
        # Print summary
        print("\n📋 Summary:")
        print(f"  - Performance level: {results.get('response_performance', {}).get('performance_level', 'unknown')}")
        print(f"  - Total recommendations: {len(results.get('optimization_recommendations', []))}")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
```

## Configuration

### Analytics Settings
```bash
# Dashboard Configuration
ANALYTICS_DASHBOARD_ENABLED=true              # Enable analytics dashboard
ANALYTICS_DASHBOARD_PORT=8080               # Dashboard web server port
ANALYTICS_API_KEY=change_me_in_production    # API authentication key

# Metrics Collection
METRICS_ENABLED=true                          # Enable metrics collection
METRICS_SAVE_INTERVAL_MINUTES=60             # Auto-save interval
METRICS_RETENTION_DAYS=30                    # How long to keep metrics

# Real-time Updates
ANALYTICS_WEBSOCKET_UPDATE_INTERVAL=2.0      # WebSocket update frequency (seconds)
ERROR_SPIKE_WINDOW_SECONDS=300               # Error spike detection window

# Performance Analysis
PERFORMANCE_ALERTS_ENABLED=true               # Enable performance alerts
CPU_WARNING_THRESHOLD=80                     # CPU usage warning (%)
MEMORY_WARNING_THRESHOLD=85                  # Memory usage warning (%)
DISK_WARNING_THRESHOLD=90                   # Disk usage warning (%)

# Analytics Data
ANALYTICS_DATA_PATH=./data/analytics         # Analytics storage location
REPORTS_PATH=./reports                      # Generated reports location
VISUALIZATIONS_PATH=./reports/charts         # Chart storage location
```

## Integration Points

### With All Systems
- **Metrics Collection**: All services report metrics
- **Health Monitoring**: System-wide health visibility
- **Performance Tracking**: Cross-system performance analysis

### With Administration System
- **Admin Dashboard**: Administrative interface integration
- **Alert Routing**: Health alerts to admin channels
- **Configuration Monitoring**: Track configuration changes

### With Chat System
- **Conversation Analytics**: Chat interaction metrics
- **Response Performance**: LLM response time tracking
- **User Behavior**: Engagement pattern analysis

## Performance Considerations

### 1. Dashboard Performance
- **WebSocket Efficiency**: Optimize real-time updates
- **Chart Rendering**: Efficient data visualization
- **Data Caching**: Cache expensive analytics calculations

### 2. Metrics Overhead
- **Sampling Rates**: Balance detail vs performance
- **Storage Efficiency**: Compress historical metrics
- **Batch Processing**: Group metrics operations

### 3. Resource Management
- **Memory Usage**: Bound analytics data structures
- **CPU Usage**: Optimize analysis algorithms
- **Network Bandwidth**: Efficient WebSocket communication

## Security Considerations

### 1. Access Control
- **API Authentication**: Require valid API keys
- **Network Isolation**: Dashboard in isolated network segment
- **Role-Based Access**: Different access levels for different users

### 2. Data Protection
- **Sensitive Metrics**: Filter sensitive information
- **Data Encryption**: Encrypt stored analytics data
- **Audit Logging**: Log all dashboard access

## Common Issues and Troubleshooting

### 1. Dashboard Not Loading
```bash
# Check dashboard service
curl http://localhost:8080/api/health/status

# Verify WebSocket connection
wscat -c ws://localhost:8080/ws

# Check logs
grep "dashboard" logs/bot.log | tail -10
```

### 2. Metrics Not Updating
```python
# Check metrics service
metrics_service = MetricsService()
await metrics_service.get_current_metrics()

# Verify metrics saving
ls -la ./data/metrics/
cat ./data/metrics/current.json
```

### 3. Performance Issues
```bash
# Run performance analysis
python scripts/analyze_performance.py

# Check resource usage
top -p $(pgrep -f "acore_bot")

# Monitor WebSocket connections
netstat -an | grep :8080
```

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `services/analytics/dashboard.py` | Analytics dashboard server |
| `templates/dashboard/index.html` | Dashboard web interface |
| `services/core/metrics.py` | Metrics collection service |
| `scripts/analyze_performance.py` | Performance analysis tool |
| `scripts/profile_performance.py` | User behavior analysis |
| `scripts/benchmark_optimizations.py` | System benchmarking |

---

**Last Updated**: 2025-12-16
**Version**: 1.0