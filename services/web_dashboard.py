import logging
from aiohttp import web
import asyncio
from config import Config
import json
import time
import os
from datetime import datetime
from pathlib import Path
from collections import deque
from dotenv import dotenv_values, set_key
# Sound effects service removed - feature was never fully integrated
# from services.sound_effects import get_sound_effects_service

logger = logging.getLogger(__name__)

class WebDashboard:
    def __init__(self, bot):
        self.bot = bot
        self.app = web.Application()
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_get('/api/logs', self.handle_logs)
        self.app.router.add_post('/api/control', self.handle_control)
        self.app.router.add_get('/api/config', self.handle_get_config)
        self.app.router.add_post('/api/config', self.handle_set_config)
        # Sound effects routes
        self.app.router.add_get('/api/sounds', self.handle_get_sounds)
        self.app.router.add_post('/api/sounds/upload', self.handle_upload_sound)
        self.app.router.add_post('/api/sounds/config', self.handle_update_sound_config)
        self.app.router.add_post('/api/sounds/delete', self.handle_delete_sound)
        self.app.router.add_post('/api/sounds/toggle', self.handle_toggle_sounds)
        self.runner = None
        self.site = None
        self.start_time = time.time()
        
        # Activity tracking
        self.current_activity = "Idle"
        self.activity_history = deque(maxlen=20)
        self.last_activity_time = time.time()

    def set_status(self, status: str, details: str = None):
        """Update current bot status."""
        self.current_activity = status
        self.last_activity_time = time.time()
        
        # Add to history
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "time": timestamp,
            "status": status,
            "details": details or ""
        }
        self.activity_history.appendleft(entry)
        
    async def handle_index(self, request):
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Acore Bot Dashboard</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --bg-color: #111827;
                    --card-bg: #1f2937;
                    --text-color: #f3f4f6;
                    --text-muted: #9ca3af;
                    --accent-color: #6366f1;
                    --accent-hover: #4f46e5;
                    --success-color: #10b981;
                    --error-color: #ef4444;
                    --warning-color: #f59e0b;
                    --border-color: #374151;
                }
                body {
                    font-family: 'Inter', sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: var(--bg-color);
                    color: var(--text-color);
                    min-height: 100vh;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }
                header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 1px solid var(--border-color);
                }
                h1 {
                    margin: 0;
                    color: var(--accent-color);
                    font-size: 1.8rem;
                }
                .grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .card {
                    background-color: var(--card-bg);
                    padding: 20px;
                    border-radius: 12px;
                    border: 1px solid var(--border-color);
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                }
                .card h2 {
                    margin-top: 0;
                    font-size: 1.1rem;
                    color: var(--text-muted);
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    margin-bottom: 15px;
                }
                .stat {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 12px;
                    padding-bottom: 8px;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                }
                .stat:last-child {
                    border-bottom: none;
                    margin-bottom: 0;
                    padding-bottom: 0;
                }
                .stat-label {
                    color: var(--text-muted);
                }
                .stat-value {
                    font-weight: 600;
                    font-size: 1.1rem;
                }
                .status-ok { color: var(--success-color); }
                .status-err { color: var(--error-color); }
                
                /* Live Activity Styles */
                .activity-feed {
                    max-height: 300px;
                    overflow-y: auto;
                }
                .activity-item {
                    display: flex;
                    align-items: flex-start;
                    padding: 10px 0;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                    animation: fadeIn 0.3s ease-in;
                }
                .activity-time {
                    font-family: 'Consolas', monospace;
                    color: var(--text-muted);
                    font-size: 0.85rem;
                    min-width: 70px;
                }
                .activity-content {
                    flex: 1;
                }
                .activity-status {
                    font-weight: 600;
                    color: var(--accent-color);
                    margin-bottom: 2px;
                }
                .activity-details {
                    font-size: 0.9rem;
                    color: var(--text-muted);
                }
                .current-status-badge {
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 20px;
                    background-color: rgba(99, 102, 241, 0.2);
                    color: var(--accent-color);
                    font-weight: 600;
                    font-size: 0.9rem;
                    margin-bottom: 15px;
                    border: 1px solid rgba(99, 102, 241, 0.3);
                }
                .pulse {
                    animation: pulse 2s infinite;
                }
                
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.6; }
                    100% { opacity: 1; }
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(-5px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                .logs-container {
                    background-color: #000;
                    border-radius: 8px;
                    padding: 15px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 0.9rem;
                    height: 300px;
                    overflow-y: auto;
                    color: #d1d5db;
                    border: 1px solid var(--border-color);
                }
                .log-entry {
                    margin-bottom: 4px;
                    white-space: pre-wrap;
                    word-break: break-all;
                }
                .log-info { color: #60a5fa; }
                .log-warn { color: #fbbf24; }
                .log-error { color: #f87171; }

                .controls {
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                }
                button {
                    background-color: var(--card-bg);
                    border: 1px solid var(--accent-color);
                    color: var(--accent-color);
                    padding: 8px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: all 0.2s;
                }
                button:hover {
                    background-color: var(--accent-color);
                    color: white;
                }
                button:active {
                    transform: translateY(1px);
                }

                /* Config Editor Styles */
                .config-tabs {
                    display: flex;
                    gap: 5px;
                    margin-bottom: 15px;
                    border-bottom: 1px solid var(--border-color);
                    padding-bottom: 10px;
                }
                .tab-btn {
                    padding: 6px 12px;
                    font-size: 0.85rem;
                    border: none;
                    background: transparent;
                    color: var(--text-muted);
                    cursor: pointer;
                }
                .tab-btn.active {
                    color: var(--accent-color);
                    border-bottom: 2px solid var(--accent-color);
                }
                .config-section {
                    display: none;
                }
                .config-section.active {
                    display: block;
                }
                .config-field {
                    margin-bottom: 12px;
                }
                .config-field label {
                    display: block;
                    font-size: 0.85rem;
                    color: var(--text-muted);
                    margin-bottom: 4px;
                }
                .config-field input[type="text"],
                .config-field input[type="number"],
                .config-field select {
                    width: 100%;
                    padding: 8px;
                    background: var(--bg-color);
                    border: 1px solid var(--border-color);
                    border-radius: 4px;
                    color: var(--text-color);
                    font-size: 0.9rem;
                }
                .config-field input[type="checkbox"] {
                    width: 18px;
                    height: 18px;
                }
                .channel-list {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 5px;
                    margin-bottom: 8px;
                }
                .channel-tag {
                    display: inline-flex;
                    align-items: center;
                    gap: 5px;
                    background: rgba(99, 102, 241, 0.2);
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 0.8rem;
                }
                .channel-tag button {
                    background: none;
                    border: none;
                    color: var(--error-color);
                    cursor: pointer;
                    padding: 0;
                    font-size: 1rem;
                }
                .channel-add {
                    display: flex;
                    gap: 5px;
                }
                .channel-add input {
                    flex: 1;
                    padding: 6px;
                    background: var(--bg-color);
                    border: 1px solid var(--border-color);
                    border-radius: 4px;
                    color: var(--text-color);
                }
                .channel-add button {
                    padding: 6px 12px;
                    font-size: 0.8rem;
                }
                .config-actions {
                    margin-top: 15px;
                    display: flex;
                    gap: 10px;
                }
                .config-actions button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                footer {
                    text-align: center;
                    margin-top: 50px;
                    color: var(--text-muted);
                    font-size: 0.9rem;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <header>
                    <h1>🤖 Acore Bot Dashboard</h1>
                    <div id="connection-status" class="status-ok">Connected</div>
                </header>
                
                <div class="grid">
                    <!-- Live Activity Card (New) -->
                    <div class="card" style="grid-column: span 2;">
                        <h2>Live Processing Pipeline</h2>
                        <div id="current-status-container">
                            <span id="current-status" class="current-status-badge">Idle</span>
                        </div>
                        <div id="activity-feed" class="activity-feed">
                            <!-- Activity items will be injected here -->
                            <div class="activity-item">
                                <span class="activity-time">--:--</span>
                                <div class="activity-content">
                                    <div class="activity-status">Waiting for events...</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="card">
                        <h2>System Status</h2>
                        <div id="system-status">Loading...</div>
                    </div>
                </div>
                
                <div class="grid">
                    <div class="card">
                        <h2>Bot Statistics</h2>
                        <div id="bot-stats">Loading...</div>
                    </div>
                    
                    <div class="card">
                        <h2>AI Configuration</h2>
                        <div id="ai-config">Loading...</div>
                    </div>
                </div>

                <!-- Metrics Section -->
                <div class="grid" style="margin-top: 20px;">
                    <div class="card">
                        <h2>📊 Performance Metrics</h2>
                        <div id="performance-metrics">Loading...</div>
                    </div>

                    <div class="card">
                        <h2>💾 Cache Performance</h2>
                        <div id="cache-metrics">Loading...</div>
                    </div>
                </div>

                <div class="grid">
                    <div class="card">
                        <h2>👥 Activity Stats</h2>
                        <div id="activity-metrics">Loading...</div>
                    </div>

                    <div class="card">
                        <h2>⚠️ Error Monitoring</h2>
                        <div id="error-metrics">Loading...</div>
                    </div>
                </div>

                <div class="card" style="margin-bottom: 30px;">
                    <h2>Quick Actions</h2>
                    <div class="controls">
                        <button onclick="sendControl('clear_temp')">🧹 Clear Temp Files</button>
                        <button onclick="sendControl('disconnect_voice')">🔌 Disconnect Voice</button>
                    </div>
                </div>

                <div class="card" style="margin-bottom: 30px;">
                    <h2>⚙️ Configuration</h2>
                    <div id="config-editor">
                        <div class="config-tabs">
                            <button class="tab-btn active" onclick="showConfigTab('ambient')">Ambient</button>
                            <button class="tab-btn" onclick="showConfigTab('chat')">Chat</button>
                            <button class="tab-btn" onclick="showConfigTab('voice')">Voice</button>
                            <button class="tab-btn" onclick="showConfigTab('sounds')">🔊 Sounds</button>
                            <button class="tab-btn" onclick="showConfigTab('llm')">🧠 LLM Settings</button>
                        </div>

                        <div id="config-ambient" class="config-section active">
                            <div class="config-field">
                                <label>Enabled</label>
                                <input type="checkbox" id="AMBIENT_MODE_ENABLED" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Channels (IDs)</label>
                                <div class="channel-list" id="AMBIENT_CHANNELS_list"></div>
                                <div class="channel-add">
                                    <input type="text" id="AMBIENT_CHANNELS_new" placeholder="Channel ID">
                                    <button onclick="addChannel('AMBIENT_CHANNELS')">Add</button>
                                </div>
                            </div>
                            <div class="config-field">
                                <label>Ignore Users (IDs)</label>
                                <div class="channel-list" id="AMBIENT_IGNORE_USERS_list"></div>
                                <div class="channel-add">
                                    <input type="text" id="AMBIENT_IGNORE_USERS_new" placeholder="User ID">
                                    <button onclick="addChannel('AMBIENT_IGNORE_USERS')">Add</button>
                                </div>
                            </div>
                            <div class="config-field">
                                <label>Lull Timeout (seconds)</label>
                                <input type="number" id="AMBIENT_LULL_TIMEOUT" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Min Interval (seconds)</label>
                                <input type="number" id="AMBIENT_MIN_INTERVAL" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Trigger Chance (0-1)</label>
                                <input type="number" step="0.1" min="0" max="1" id="AMBIENT_CHANCE" onchange="markConfigDirty()">
                            </div>
                        </div>

                        <div id="config-chat" class="config-section">
                            <div class="config-field">
                                <label>Auto-Reply Enabled</label>
                                <input type="checkbox" id="AUTO_REPLY_ENABLED" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Auto-Reply Channels (IDs)</label>
                                <div class="channel-list" id="AUTO_REPLY_CHANNELS_list"></div>
                                <div class="channel-add">
                                    <input type="text" id="AUTO_REPLY_CHANNELS_new" placeholder="Channel ID">
                                    <button onclick="addChannel('AUTO_REPLY_CHANNELS')">Add</button>
                                </div>
                            </div>
                            <div class="config-field">
                                <label>Max History Messages</label>
                                <input type="number" id="CHAT_HISTORY_MAX_MESSAGES" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Conversation Timeout (seconds)</label>
                                <input type="number" id="CONVERSATION_TIMEOUT" onchange="markConfigDirty()">
                            </div>
                        </div>

                        <div id="config-voice" class="config-section">
                            <div class="config-field">
                                <label>TTS Engine</label>
                                <select id="TTS_ENGINE" onchange="markConfigDirty()">
                                    <option value="edge">Edge TTS</option>
                                    <option value="kokoro">Kokoro</option>
                                    <option value="supertonic">Supertonic</option>
                                </select>
                            </div>

                            <h3 style="margin-top: 15px; color: var(--accent-color); font-size: 0.9rem;">Edge TTS Settings</h3>
                            <div class="config-field">
                                <label>Edge Voice</label>
                                <input type="text" id="DEFAULT_TTS_VOICE" onchange="markConfigDirty()">
                            </div>

                            <h3 style="margin-top: 15px; color: var(--accent-color); font-size: 0.9rem;">Kokoro Settings</h3>
                            <div class="config-field">
                                <label>Kokoro Voice</label>
                                <input type="text" id="KOKORO_VOICE" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Kokoro Speed</label>
                                <input type="number" step="0.1" id="KOKORO_SPEED" onchange="markConfigDirty()">
                            </div>

                            <h3 style="margin-top: 15px; color: var(--accent-color); font-size: 0.9rem;">Supertonic Settings</h3>
                            <div class="config-field">
                                <label>Supertonic Voice</label>
                                <input type="text" id="SUPERTONIC_VOICE" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Supertonic Speed</label>
                                <input type="number" step="0.05" id="SUPERTONIC_SPEED" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Supertonic Steps (1-20)</label>
                                <input type="number" step="1" min="1" max="20" id="SUPERTONIC_STEPS" onchange="markConfigDirty()">
                            </div>

                            <h3 style="margin-top: 15px; color: var(--accent-color); font-size: 0.9rem;">RVC Voice Conversion</h3>
                            <div class="config-field">
                                <label>RVC Enabled</label>
                                <input type="checkbox" id="RVC_ENABLED" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Default RVC Model</label>
                                <input type="text" id="DEFAULT_RVC_MODEL" onchange="markConfigDirty()">
                            </div>
                        </div>

                        <div id="config-llm" class="config-section">
                            <div class="config-field">
                                <label>LLM Provider</label>
                                <select id="LLM_PROVIDER" onchange="markConfigDirty()">
                                    <option value="ollama">Ollama (Local)</option>
                                    <option value="openrouter">OpenRouter (Cloud)</option>
                                </select>
                            </div>

                            <h3 style="margin-top: 15px; color: var(--accent-color); font-size: 0.9rem;">Ollama Settings</h3>
                            <div class="config-field">
                                <label>Local Model</label>
                                <input type="text" id="OLLAMA_MODEL" onchange="markConfigDirty()">
                            </div>

                            <h3 style="margin-top: 15px; color: var(--accent-color); font-size: 0.9rem;">OpenRouter Settings</h3>
                            <div class="config-field">
                                <label>API Key</label>
                                <input type="password" id="OPENROUTER_API_KEY" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Cloud Model</label>
                                <input type="text" id="OPENROUTER_MODEL" onchange="markConfigDirty()">
                            </div>

                            <h3 style="margin-top: 15px; color: var(--accent-color); font-size: 0.9rem;">Sampling Parameters</h3>
                            <div class="config-field">
                                <label>Temperature (0.0 - 2.0)</label>
                                <input type="number" step="0.01" min="0" max="2" id="OLLAMA_TEMPERATURE" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Max Tokens</label>
                                <input type="number" id="OLLAMA_MAX_TOKENS" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Top P (0.0 - 1.0)</label>
                                <input type="number" step="0.01" min="0" max="1" id="LLM_TOP_P" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Frequency Penalty (-2.0 - 2.0)</label>
                                <input type="number" step="0.01" min="-2" max="2" id="LLM_FREQUENCY_PENALTY" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Presence Penalty (-2.0 - 2.0)</label>
                                <input type="number" step="0.01" min="-2" max="2" id="LLM_PRESENCE_PENALTY" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Repetition Penalty (0.0 - 2.0)</label>
                                <input type="number" step="0.01" min="0" max="2" id="OLLAMA_REPEAT_PENALTY" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Min P (0.0 - 1.0)</label>
                                <input type="number" step="0.01" min="0" max="1" id="OLLAMA_MIN_P" onchange="markConfigDirty()">
                            </div>
                            <div class="config-field">
                                <label>Top K</label>
                                <input type="number" step="1" id="OLLAMA_TOP_K" onchange="markConfigDirty()">
                            </div>
                        </div>

                        <div id="config-sounds" class="config-section">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                                <div>
                                    <label style="display: inline-flex; align-items: center; gap: 8px; cursor: pointer;">
                                        <input type="checkbox" id="sounds-enabled" onchange="toggleSounds()">
                                        <span style="font-weight: 600;">Sound Effects Enabled</span>
                                    </label>
                                </div>
                                <div>
                                    <label style="display: inline-flex; align-items: center; gap: 8px;">
                                        Global Volume:
                                        <input type="range" id="sounds-global-volume" min="0" max="100" value="50"
                                               onchange="updateGlobalVolume(this.value)" style="width: 120px;">
                                        <span id="sounds-volume-display">50%</span>
                                    </label>
                                </div>
                            </div>

                            <div style="background-color: var(--bg-color); padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                                <h3 style="margin: 0 0 10px 0; font-size: 1rem;">📤 Upload Sound File</h3>
                                <div style="display: flex; gap: 10px; align-items: center;">
                                    <input type="file" id="sound-file-input" accept=".mp3,.wav,.ogg,.m4a"
                                           style="flex: 1; padding: 8px; background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-color);">
                                    <button onclick="uploadSound()" style="white-space: nowrap;">Upload</button>
                                </div>
                                <div id="upload-status" style="margin-top: 8px; font-size: 0.85rem;"></div>
                            </div>

                            <div style="margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
                                <h3 style="margin: 0; font-size: 1rem;">🎵 Sound Effects</h3>
                                <button onclick="loadSounds()" style="font-size: 0.85rem; padding: 4px 10px;">🔄 Refresh</button>
                            </div>

                            <div id="sounds-list" style="display: grid; gap: 15px;">
                                Loading sounds...
                            </div>

                            <div id="add-sound-form" style="background-color: var(--bg-color); padding: 15px; border-radius: 6px; margin-top: 20px; display: none;">
                                <h3 style="margin: 0 0 15px 0; font-size: 1rem;">➕ Add Sound Effect</h3>
                                <div class="config-field">
                                    <label>Name</label>
                                    <input type="text" id="new-sound-name" placeholder="e.g., Bruh">
                                </div>
                                <div class="config-field">
                                    <label>File (uploaded)</label>
                                    <select id="new-sound-file" style="width: 100%; padding: 8px; background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-color);">
                                        <option value="">Select a file...</option>
                                    </select>
                                </div>
                                <div class="config-field">
                                    <label>Triggers (comma-separated)</label>
                                    <input type="text" id="new-sound-triggers" placeholder="e.g., bruh, bruh moment">
                                </div>
                                <div class="config-field">
                                    <label>Cooldown (seconds)</label>
                                    <input type="number" id="new-sound-cooldown" value="10" min="1">
                                </div>
                                <div class="config-field">
                                    <label>Volume</label>
                                    <input type="range" id="new-sound-volume" min="0" max="100" value="50">
                                    <span id="new-sound-volume-display">50%</span>
                                </div>
                                <div style="display: flex; gap: 10px; margin-top: 15px;">
                                    <button onclick="addSoundEffect()">✅ Add Effect</button>
                                    <button onclick="document.getElementById('add-sound-form').style.display='none'"
                                            style="background-color: var(--card-bg); border-color: var(--text-muted);">Cancel</button>
                                </div>
                            </div>

                            <button onclick="document.getElementById('add-sound-form').style.display='block'"
                                    style="width: 100%; margin-top: 15px;">➕ Add New Sound Effect</button>
                        </div>

                        <div class="config-actions">
                            <button id="save-config-btn" onclick="saveConfig()" disabled>💾 Save Changes</button>
                            <button onclick="loadConfig()">🔄 Reload</button>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h2>Live Logs</h2>
                    <div id="logs" class="logs-container">
                        Loading logs...
                    </div>
                </div>

                <footer>
                    Auto-refreshing every 2 seconds • Acore Bot v1.1
                </footer>
            </div>

            <script>
                function formatUptime(seconds) {
                    const d = Math.floor(seconds / (3600*24));
                    const h = Math.floor(seconds % (3600*24) / 3600);
                    const m = Math.floor(seconds % 3600 / 60);
                    const s = Math.floor(seconds % 60);
                    
                    const parts = [];
                    if (d > 0) parts.push(`${d}d`);
                    if (h > 0) parts.push(`${h}h`);
                    if (m > 0) parts.push(`${m}m`);
                    parts.push(`${s}s`);
                    
                    return parts.join(' ');
                }

                async function updateStatus() {
                    try {
                        const response = await fetch('/api/status');
                        const data = await response.json();
                        
                        // Update Current Status Badge
                        const statusBadge = document.getElementById('current-status');
                        statusBadge.innerText = data.current_activity;
                        if (data.current_activity !== 'Idle') {
                            statusBadge.classList.add('pulse');
                            statusBadge.style.borderColor = 'var(--success-color)';
                            statusBadge.style.color = 'var(--success-color)';
                            statusBadge.style.backgroundColor = 'rgba(16, 185, 129, 0.2)';
                        } else {
                            statusBadge.classList.remove('pulse');
                            statusBadge.style.borderColor = 'var(--border-color)';
                            statusBadge.style.color = 'var(--text-muted)';
                            statusBadge.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                        }

                        // Update Activity Feed
                        const feed = document.getElementById('activity-feed');
                        const activityHtml = data.activity_history.map(item => `
                            <div class="activity-item">
                                <span class="activity-time">${item.time}</span>
                                <div class="activity-content">
                                    <div class="activity-status">${item.status}</div>
                                    ${item.details ? `<div class="activity-details">${item.details}</div>` : ''}
                                </div>
                            </div>
                        `).join('');
                        
                        // Only update if changed to avoid jitter
                        if (feed.innerHTML !== activityHtml && activityHtml.trim() !== '') {
                            feed.innerHTML = activityHtml;
                        }

                        // System Status
                        document.getElementById('system-status').innerHTML = `
                            <div class="stat">
                                <span class="stat-label">Bot Status</span>
                                <span class="stat-value status-ok">Online</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Uptime</span>
                                <span class="stat-value">${formatUptime(data.uptime)}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Latency</span>
                                <span class="stat-value">${Math.round(data.latency * 1000)}ms</span>
                            </div>
                        `;
                        
                        // Bot Stats
                        document.getElementById('bot-stats').innerHTML = `
                            <div class="stat">
                                <span class="stat-label">Guilds</span>
                                <span class="stat-value">${data.guilds}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Users</span>
                                <span class="stat-value">${data.users}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Active Voice</span>
                                <span class="stat-value">${data.voice_clients}</span>
                            </div>
                        `;
                        
                        // AI Config
                        document.getElementById('ai-config').innerHTML = `
                            <div class="stat">
                                <span class="stat-label">LLM Provider</span>
                                <span class="stat-value">${data.llm_provider}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Model</span>
                                <span class="stat-value" style="font-size: 0.85rem;">${data.active_model}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">TTS</span>
                                <span class="stat-value">${data.tts_engine}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Voice</span>
                                <span class="stat-value" style="font-size: 0.85rem;">${data.tts_voice}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">RVC</span>
                                <span class="stat-value ${data.rvc_enabled ? 'status-ok' : 'status-err'}">${data.rvc_enabled ? 'Enabled' : 'Disabled'}</span>
                            </div>
                        `;

                        // Performance Metrics - Enhanced with LLM stats
                        let perfHTML = '';

                        // LLM Performance (OpenRouter/Ollama specific)
                        if (data.llm_performance) {
                            const llm = data.llm_performance;
                            perfHTML += `
                                <div class="stat">
                                    <span class="stat-label">Last Response Time</span>
                                    <span class="stat-value ${llm.last_response_time_seconds > 10 ? 'status-err' : llm.last_response_time_seconds > 5 ? 'status-warn' : 'status-ok'}">${llm.last_response_time_seconds}s (${llm.last_response_time_ms}ms)</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Tokens/Second (TPS)</span>
                                    <span class="stat-value ${llm.last_tps < 15 ? 'status-err' : llm.last_tps < 30 ? 'status-warn' : 'status-ok'}">${llm.last_tps.toFixed(1)}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Avg Response Time</span>
                                    <span class="stat-value">${llm.average_response_time_seconds}s (${llm.average_response_time_ms}ms)</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Total Requests</span>
                                    <span class="stat-value">${llm.total_requests}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Total Tokens Generated</span>
                                    <span class="stat-value">${llm.total_tokens_generated.toLocaleString()}</span>
                                </div>
                            `;
                        } else if (data.metrics && data.metrics.response_times) {
                            // Fallback to general metrics
                            const rt = data.metrics.response_times;
                            perfHTML += `
                                <div class="stat">
                                    <span class="stat-label">Avg Response Time</span>
                                    <span class="stat-value">${rt.avg > 0 ? rt.avg.toFixed(0) : '0'}ms</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">P95 Response Time</span>
                                    <span class="stat-value">${rt.p95 > 0 ? rt.p95.toFixed(0) : '0'}ms</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Messages Processed</span>
                                    <span class="stat-value">${data.metrics.active_stats.messages_processed}</span>
                                </div>
                            `;
                        } else {
                            perfHTML = '<div class="stat"><span class="stat-label">No performance data yet</span><span class="stat-value">-</span></div>';
                        }

                        document.getElementById('performance-metrics').innerHTML = perfHTML;

                        // Cache Metrics
                        if (data.metrics && data.metrics.cache_stats) {
                            const cache = data.metrics.cache_stats;
                            const historyHitRate = cache.history_cache.hit_rate.toFixed(1);
                            document.getElementById('cache-metrics').innerHTML = `
                                <div class="stat">
                                    <span class="stat-label">History Cache Hit Rate</span>
                                    <span class="stat-value ${cache.history_cache.hit_rate > 80 ? 'status-ok' : cache.history_cache.hit_rate > 50 ? 'status-warn' : 'status-err'}">${historyHitRate}%</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Cache Hits</span>
                                    <span class="stat-value">${cache.history_cache.hits}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Cache Misses</span>
                                    <span class="stat-value">${cache.history_cache.misses}</span>
                                </div>
                            `;
                        } else {
                            document.getElementById('cache-metrics').innerHTML = '<div class="stat"><span class="stat-label">No cache data yet</span></div>';
                        }

                        // Activity Metrics
                        if (data.metrics && data.metrics.active_stats) {
                            const activity = data.metrics.active_stats;
                            document.getElementById('activity-metrics').innerHTML = `
                                <div class="stat">
                                    <span class="stat-label">Active Users</span>
                                    <span class="stat-value">${activity.active_users}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Active Channels</span>
                                    <span class="stat-value">${activity.active_channels}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Commands Executed</span>
                                    <span class="stat-value">${activity.commands_executed}</span>
                                </div>
                            `;
                        } else {
                            document.getElementById('activity-metrics').innerHTML = '<div class="stat"><span class="stat-label">No activity data yet</span></div>';
                        }

                        // Error Metrics
                        if (data.metrics && data.metrics.errors) {
                            const errors = data.metrics.errors;
                            const errorRateFormatted = errors.error_rate.toFixed(2);
                            document.getElementById('error-metrics').innerHTML = `
                                <div class="stat">
                                    <span class="stat-label">Total Errors</span>
                                    <span class="stat-value ${errors.total_errors === 0 ? 'status-ok' : errors.total_errors > 10 ? 'status-err' : 'status-warn'}">${errors.total_errors}</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Error Rate</span>
                                    <span class="stat-value ${errors.error_rate === 0 ? 'status-ok' : errors.error_rate > 5 ? 'status-err' : 'status-warn'}">${errorRateFormatted}%</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-label">Status</span>
                                    <span class="stat-value ${errors.total_errors === 0 ? 'status-ok' : errors.total_errors > 10 ? 'status-err' : 'status-warn'}">${errors.total_errors === 0 ? 'Healthy' : errors.total_errors > 10 ? 'Issues Detected' : 'Minor Issues'}</span>
                                </div>
                            `;
                        } else {
                            document.getElementById('error-metrics').innerHTML = '<div class="stat"><span class="stat-label">No error data yet</span></div>';
                        }
                        
                        document.getElementById('connection-status').className = 'status-ok';
                        document.getElementById('connection-status').innerText = 'Connected';
                    } catch (e) {
                        console.error("Failed to fetch status", e);
                        document.getElementById('connection-status').className = 'status-err';
                        document.getElementById('connection-status').innerText = 'Disconnected';
                    }
                }

                async function updateLogs() {
                    try {
                        const response = await fetch('/api/logs');
                        const data = await response.json();
                        
                        const logsContainer = document.getElementById('logs');
                        // Check if scrolled to bottom before update
                        const wasScrolledToBottom = Math.abs(logsContainer.scrollHeight - logsContainer.scrollTop - logsContainer.clientHeight) < 50;
                        
                        logsContainer.innerHTML = data.logs.map(line => {
                            let className = 'log-entry';
                            if (line.includes('INFO')) className += ' log-info';
                            if (line.includes('WARNING')) className += ' log-warn';
                            if (line.includes('ERROR')) className += ' log-error';
                            return `<div class="${className}">${line}</div>`;
                        }).join('');
                        
                        if (wasScrolledToBottom) {
                            logsContainer.scrollTop = logsContainer.scrollHeight;
                        }
                    } catch (e) {
                        console.error("Failed to fetch logs", e);
                    }
                }

                async function sendControl(action) {
                    if (!confirm(`Are you sure you want to ${action.replace('_', ' ')}?`)) return;
                    
                    try {
                        const response = await fetch('/api/control', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ action })
                        });
                        const result = await response.json();
                        if (result.success) {
                            // alert('Action completed successfully!');
                        } else {
                            alert('Error: ' + result.error);
                        }
                    } catch (e) {
                        alert('Failed to send command: ' + e);
                    }
                }
                
                // Config Editor Functions
                let configData = {};
                let configDirty = false;

                async function loadConfig() {
                    try {
                        const response = await fetch('/api/config');
                        configData = await response.json();

                        // Populate fields
                        for (const [section, values] of Object.entries(configData)) {
                            for (const [key, value] of Object.entries(values)) {
                                // Skip resolved fields
                                if (key.endsWith('_RESOLVED')) continue;

                                const element = document.getElementById(key);
                                if (element) {
                                    if (element.type === 'checkbox') {
                                        element.checked = value;
                                    } else if (Array.isArray(value)) {
                                        // Handle channel/user lists - use resolved names
                                        const resolvedKey = key + '_RESOLVED';
                                        const resolved = values[resolvedKey] || value.map(v => ({id: v, name: v}));
                                        renderChannelList(key, resolved);
                                    } else {
                                        element.value = value;
                                    }
                                }
                            }
                        }
                        configDirty = false;
                        document.getElementById('save-config-btn').disabled = true;
                    } catch (e) {
                        console.error('Failed to load config', e);
                    }
                }

                function renderChannelList(key, values) {
                    const listEl = document.getElementById(key + '_list');
                    if (!listEl) return;

                    if (!values || values.length === 0) {
                        listEl.innerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">None configured</span>';
                        return;
                    }

                    listEl.innerHTML = values.map(v => `
                        <span class="channel-tag">
                            ${v.name} <span style="opacity:0.5">(${v.id})</span>
                            <button onclick="removeChannel('${key}', ${v.id})">×</button>
                        </span>
                    `).join('');
                }

                function addChannel(key) {
                    const input = document.getElementById(key + '_new');
                    const value = input.value.trim();
                    if (!value) return;

                    const intValue = parseInt(value);
                    if (isNaN(intValue)) {
                        alert('Please enter a valid numeric ID');
                        return;
                    }

                    // Find the config section containing this key
                    for (const section of Object.values(configData)) {
                        if (key in section) {
                            // Initialize array if needed
                            if (!Array.isArray(section[key])) {
                                section[key] = [];
                            }

                            if (!section[key].includes(intValue)) {
                                section[key].push(intValue);

                                // Also update the resolved list for display
                                const resolvedKey = key + '_RESOLVED';
                                const newItem = {id: intValue, name: `ID: ${intValue}`};

                                if (Array.isArray(section[resolvedKey])) {
                                    section[resolvedKey].push(newItem);
                                } else {
                                    section[resolvedKey] = [newItem];
                                }

                                renderChannelList(key, section[resolvedKey]);
                                markConfigDirty();
                            } else {
                                alert('This ID is already in the list');
                            }
                            break;
                        }
                    }
                    input.value = '';
                }

                function removeChannel(key, value) {
                    for (const section of Object.values(configData)) {
                        if (key in section) {
                            section[key] = section[key].filter(v => v !== value);
                            // Also update the resolved list
                            const resolvedKey = key + '_RESOLVED';
                            if (section[resolvedKey]) {
                                section[resolvedKey] = section[resolvedKey].filter(v => v.id !== value);
                            }
                            renderChannelList(key, section[resolvedKey] || []);
                            markConfigDirty();
                            break;
                        }
                    }
                }

                function markConfigDirty() {
                    configDirty = true;
                    document.getElementById('save-config-btn').disabled = false;
                }

                async function saveConfig() {
                    try {
                        // Gather all config values
                        const updates = {};

                        for (const [section, values] of Object.entries(configData)) {
                            for (const key of Object.keys(values)) {
                                const element = document.getElementById(key);
                                if (element) {
                                    if (element.type === 'checkbox') {
                                        updates[key] = element.checked;
                                    } else if (Array.isArray(configData[section][key])) {
                                        updates[key] = configData[section][key];
                                    } else {
                                        updates[key] = element.value;
                                    }
                                }
                            }
                        }

                        const response = await fetch('/api/config', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(updates)
                        });

                        const result = await response.json();
                        if (result.success) {
                            configDirty = false;
                            document.getElementById('save-config-btn').disabled = true;
                            // Reload to get fresh values
                            await loadConfig();
                        } else {
                            alert('Error: ' + result.error);
                        }
                    } catch (e) {
                        alert('Failed to save: ' + e);
                    }
                }

                function showConfigTab(tab) {
                    // Update buttons
                    document.querySelectorAll('.tab-btn').forEach(btn => {
                        btn.classList.remove('active');
                        if (btn.textContent.toLowerCase().includes(tab)) {
                            btn.classList.add('active');
                        }
                    });

                    // Update sections
                    document.querySelectorAll('.config-section').forEach(sec => {
                        sec.classList.remove('active');
                    });
                    document.getElementById('config-' + tab).classList.add('active');

                    // Load sounds when sounds tab is shown
                    if (tab === 'sounds') {
                        loadSounds();
                    }
                }

                // Initial load
                updateStatus();
                updateLogs();
                loadConfig();

                // Refresh loops
                setInterval(updateStatus, 1000); // Faster updates for activity
                setInterval(updateLogs, 3000);

                // Sound Effects Management
                async function loadSounds() {
                    try {
                        const resp = await fetch('/api/sounds');
                        const data = await resp.json();

                        if (!data.success) {
                            document.getElementById('sounds-list').innerHTML =
                                `<div style="color: var(--error-color);">Error: ${data.error}</div>`;
                            return;
                        }

                        // Update global settings
                        document.getElementById('sounds-enabled').checked = data.enabled;
                        document.getElementById('sounds-global-volume').value = data.global_volume * 100;
                        document.getElementById('sounds-volume-display').textContent =
                            Math.round(data.global_volume * 100) + '%';

                        // Render sounds list
                        if (data.effects.length === 0) {
                            document.getElementById('sounds-list').innerHTML =
                                '<div style="color: var(--text-muted); text-align: center; padding: 20px;">No sound effects configured yet. Upload a file and add one!</div>';
                            return;
                        }

                        const soundsHtml = data.effects.map(effect => `
                            <div style="background-color: var(--bg-color); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color);">
                                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                                    <div>
                                        <h4 style="margin: 0 0 5px 0; font-size: 1rem;">${effect.name}</h4>
                                        <div style="font-size: 0.85rem; color: var(--text-muted);">
                                            📁 ${effect.file}
                                        </div>
                                    </div>
                                    <div style="display: flex; gap: 8px;">
                                        <span style="font-size: 0.8rem; padding: 3px 8px; border-radius: 4px; background-color: ${effect.ready ? 'var(--success-color)' : 'var(--warning-color)'}; color: white;">
                                            ${effect.ready ? '✅ Ready' : '⏳ Cooldown'}
                                        </span>
                                        <button onclick="deleteSound('${effect.name}')"
                                                style="font-size: 0.8rem; padding: 3px 8px; background-color: var(--error-color); border-color: var(--error-color); color: white;">
                                            🗑️ Delete
                                        </button>
                                    </div>
                                </div>
                                <div style="font-size: 0.9rem; margin-bottom: 8px;">
                                    <strong>Triggers:</strong> ${effect.triggers.map(t => `<code style="background-color: var(--card-bg); padding: 2px 6px; border-radius: 3px; font-size: 0.85rem;">${t}</code>`).join(' ')}
                                </div>
                                <div style="font-size: 0.85rem; color: var(--text-muted); display: flex; gap: 15px;">
                                    <span>⏱️ Cooldown: ${effect.cooldown}s</span>
                                    <span>🔊 Volume: ${Math.round(effect.volume * 100)}%</span>
                                </div>
                            </div>
                        `).join('');

                        document.getElementById('sounds-list').innerHTML = soundsHtml;

                    } catch (err) {
                        console.error('Load sounds failed:', err);
                        document.getElementById('sounds-list').innerHTML =
                            `<div style="color: var(--error-color);">Failed to load sounds</div>`;
                    }
                }

                async function toggleSounds() {
                    try {
                        const resp = await fetch('/api/sounds/toggle', { method: 'POST' });
                        const data = await resp.json();

                        if (data.success) {
                            showNotification(data.message, 'success');
                        } else {
                            showNotification('Failed to toggle sounds', 'error');
                        }
                    } catch (err) {
                        console.error('Toggle sounds failed:', err);
                        showNotification('Failed to toggle sounds', 'error');
                    }
                }

                async function updateGlobalVolume(value) {
                    document.getElementById('sounds-volume-display').textContent = value + '%';

                    try {
                        const resp = await fetch('/api/sounds/config', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                action: 'global',
                                global_volume: value / 100
                            })
                        });

                        const data = await resp.json();
                        if (data.success) {
                            showNotification('Volume updated', 'success');
                        }
                    } catch (err) {
                        console.error('Update volume failed:', err);
                    }
                }

                async function uploadSound() {
                    const fileInput = document.getElementById('sound-file-input');
                    const file = fileInput.files[0];

                    if (!file) {
                        showNotification('Please select a file', 'error');
                        return;
                    }

                    const statusDiv = document.getElementById('upload-status');
                    statusDiv.innerHTML = '<span style="color: var(--warning-color);">Uploading...</span>';

                    try {
                        const formData = new FormData();
                        formData.append('file', file);

                        const resp = await fetch('/api/sounds/upload', {
                            method: 'POST',
                            body: formData
                        });

                        const data = await resp.json();

                        if (data.success) {
                            statusDiv.innerHTML = `<span style="color: var(--success-color);">✅ ${data.message}</span>`;
                            fileInput.value = '';
                            showNotification(data.message, 'success');

                            // Add to file select dropdown
                            const select = document.getElementById('new-sound-file');
                            const option = document.createElement('option');
                            option.value = data.filename;
                            option.textContent = data.filename;
                            select.appendChild(option);
                        } else {
                            statusDiv.innerHTML = `<span style="color: var(--error-color);">❌ ${data.error}</span>`;
                            showNotification(data.error, 'error');
                        }
                    } catch (err) {
                        console.error('Upload failed:', err);
                        statusDiv.innerHTML = '<span style="color: var(--error-color);">❌ Upload failed</span>';
                        showNotification('Upload failed', 'error');
                    }
                }

                async function addSoundEffect() {
                    const name = document.getElementById('new-sound-name').value.trim();
                    const file = document.getElementById('new-sound-file').value;
                    const triggers = document.getElementById('new-sound-triggers').value
                        .split(',').map(t => t.trim()).filter(t => t);
                    const cooldown = parseInt(document.getElementById('new-sound-cooldown').value);
                    const volume = parseInt(document.getElementById('new-sound-volume').value) / 100;

                    if (!name || !file || triggers.length === 0) {
                        showNotification('Please fill all fields', 'error');
                        return;
                    }

                    try {
                        const resp = await fetch('/api/sounds/config', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                action: 'add',
                                name,
                                file,
                                triggers,
                                cooldown,
                                volume
                            })
                        });

                        const data = await resp.json();

                        if (data.success) {
                            showNotification('Sound effect added!', 'success');
                            document.getElementById('add-sound-form').style.display = 'none';
                            // Clear form
                            document.getElementById('new-sound-name').value = '';
                            document.getElementById('new-sound-file').value = '';
                            document.getElementById('new-sound-triggers').value = '';
                            loadSounds();
                        } else {
                            showNotification(data.error || 'Failed to add sound', 'error');
                        }
                    } catch (err) {
                        console.error('Add sound failed:', err);
                        showNotification('Failed to add sound', 'error');
                    }
                }

                async function deleteSound(name) {
                    if (!confirm(`Delete sound effect "${name}"?`)) return;

                    try {
                        const resp = await fetch('/api/sounds/delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name, delete_file: false })
                        });

                        const data = await resp.json();

                        if (data.success) {
                            showNotification(data.message, 'success');
                            loadSounds();
                        } else {
                            showNotification(data.error || 'Failed to delete', 'error');
                        }
                    } catch (err) {
                        console.error('Delete sound failed:', err);
                        showNotification('Failed to delete sound', 'error');
                    }
                }

                function showNotification(message, type) {
                    const color = type === 'success' ? 'var(--success-color)' :
                                 type === 'error' ? 'var(--error-color)' : 'var(--accent-color)';

                    const notification = document.createElement('div');
                    notification.style.cssText = `
                        position: fixed; top: 20px; right: 20px; z-index: 1000;
                        background-color: ${color}; color: white; padding: 12px 20px;
                        border-radius: 6px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                        animation: slideIn 0.3s ease-out;
                    `;
                    notification.textContent = message;
                    document.body.appendChild(notification);

                    setTimeout(() => {
                        notification.style.animation = 'slideOut 0.3s ease-out';
                        setTimeout(() => notification.remove(), 300);
                    }, 3000);
                }

                // Volume slider update for new sound form
                document.getElementById('new-sound-volume').addEventListener('input', (e) => {
                    document.getElementById('new-sound-volume-display').textContent = e.target.value + '%';
                });

            </script>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')

    async def handle_status(self, request):
        uptime = time.time() - self.start_time

        # Auto-reset status to Idle if no activity for 30 seconds
        if self.current_activity != "Idle" and time.time() - self.last_activity_time > 30:
            self.current_activity = "Idle"

        # Determine active model based on LLM provider
        if Config.LLM_PROVIDER == "openrouter":
            active_model = Config.OPENROUTER_MODEL
            provider_name = "OpenRouter"
        else:
            active_model = Config.OLLAMA_MODEL
            provider_name = "Ollama"

        # Determine TTS engine display name
        tts_display = Config.TTS_ENGINE.capitalize()
        if Config.TTS_ENGINE == "edge":
            tts_voice = Config.DEFAULT_TTS_VOICE
        elif Config.TTS_ENGINE == "kokoro":
            tts_voice = Config.KOKORO_VOICE
        elif Config.TTS_ENGINE == "supertonic":
            tts_voice = Config.SUPERTONIC_VOICE
        else:
            tts_voice = "Unknown"

        status = {
            "uptime": uptime,
            "latency": self.bot.latency,
            "guilds": len(self.bot.guilds),
            "users": sum(g.member_count for g in self.bot.guilds),
            "voice_clients": len(self.bot.voice_clients),
            "llm_provider": provider_name,
            "active_model": active_model,
            "tts_engine": tts_display,
            "tts_voice": tts_voice,
            "rvc_enabled": Config.RVC_ENABLED,
            # New fields
            "current_activity": self.current_activity,
            "activity_history": list(self.activity_history)
        }

        # Add metrics if available
        if hasattr(self.bot, 'metrics'):
            metrics_summary = self.bot.metrics.get_summary()
            status['metrics'] = {
                'response_times': metrics_summary['response_times'],
                'active_stats': metrics_summary['active_stats'],
                'cache_stats': metrics_summary['cache_stats'],
                'errors': {
                    'total_errors': metrics_summary['errors']['total_errors'],
                    'error_rate': metrics_summary['errors']['error_rate'],
                },
                'token_usage': metrics_summary['token_usage'],
            }

        # Add OpenRouter/Ollama performance stats
        if hasattr(self.bot, 'ollama') and hasattr(self.bot.ollama, 'get_performance_stats'):
            try:
                perf_stats = self.bot.ollama.get_performance_stats()
                status['llm_performance'] = perf_stats
            except Exception as e:
                logger.debug(f"Could not get LLM performance stats: {e}")

        return web.json_response(status)

    async def handle_logs(self, request):
        try:
            log_file = Path("bot.log")
            if not log_file.exists():
                return web.json_response({"logs": ["No log file found."]})
            
            # Read last 100 lines
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                last_lines = lines[-100:]
            
            return web.json_response({"logs": last_lines})
        except Exception as e:
            return web.json_response({"logs": [f"Error reading logs: {str(e)}"]})

    async def handle_control(self, request):
        try:
            data = await request.json()
            action = data.get('action')
            
            if action == 'clear_temp':
                if self.bot.memory_manager:
                    await self.bot.memory_manager.cleanup_temp_files()
                    self.set_status("Maintenance", "Cleared temporary files")
                    return web.json_response({"success": True, "message": "Temp files cleared"})
                else:
                    return web.json_response({"success": False, "error": "Memory manager not enabled"})
            
            elif action == 'disconnect_voice':
                count = 0
                for vc in list(self.bot.voice_clients):
                    await vc.disconnect()
                    count += 1
                self.set_status("Maintenance", f"Disconnected from {count} voice channels")
                return web.json_response({"success": True, "message": f"Disconnected from {count} channels"})
                
            else:
                return web.json_response({"success": False, "error": "Unknown action"})
                
        except Exception as e:
            logger.error(f"Control action failed: {e}")
            return web.json_response({"success": False, "error": str(e)})

    def reload_config_from_env(self):
        """Reload Config class values from .env file."""
        try:
            env_values = dotenv_values(".env")

            # Reload list values
            for key in ["AMBIENT_CHANNELS", "AUTO_REPLY_CHANNELS", "AMBIENT_IGNORE_USERS"]:
                if key in env_values:
                    value = env_values[key]
                    if value:
                        setattr(Config, key, [int(x.strip()) for x in value.split(",") if x.strip()])
                    else:
                        setattr(Config, key, [])

            # Reload other ambient settings
            if "AMBIENT_MODE_ENABLED" in env_values:
                Config.AMBIENT_MODE_ENABLED = env_values["AMBIENT_MODE_ENABLED"].lower() == "true"
            if "AMBIENT_LULL_TIMEOUT" in env_values:
                Config.AMBIENT_LULL_TIMEOUT = int(env_values["AMBIENT_LULL_TIMEOUT"])
            if "AMBIENT_MIN_INTERVAL" in env_values:
                Config.AMBIENT_MIN_INTERVAL = int(env_values["AMBIENT_MIN_INTERVAL"])
            if "AMBIENT_CHANCE" in env_values:
                Config.AMBIENT_CHANCE = float(env_values["AMBIENT_CHANCE"])

            # Reload chat settings
            if "AUTO_REPLY_ENABLED" in env_values:
                Config.AUTO_REPLY_ENABLED = env_values["AUTO_REPLY_ENABLED"].lower() == "true"
            if "CHAT_HISTORY_MAX_MESSAGES" in env_values:
                Config.CHAT_HISTORY_MAX_MESSAGES = int(env_values["CHAT_HISTORY_MAX_MESSAGES"])
            if "CONVERSATION_TIMEOUT" in env_values:
                Config.CONVERSATION_TIMEOUT = int(env_values["CONVERSATION_TIMEOUT"])

            # Reload TTS settings
            if "TTS_ENGINE" in env_values:
                Config.TTS_ENGINE = env_values["TTS_ENGINE"]
            if "DEFAULT_TTS_VOICE" in env_values:
                Config.DEFAULT_TTS_VOICE = env_values["DEFAULT_TTS_VOICE"]
            if "KOKORO_VOICE" in env_values:
                Config.KOKORO_VOICE = env_values["KOKORO_VOICE"]
            if "KOKORO_SPEED" in env_values:
                Config.KOKORO_SPEED = float(env_values["KOKORO_SPEED"])
            if "SUPERTONIC_VOICE" in env_values:
                Config.SUPERTONIC_VOICE = env_values["SUPERTONIC_VOICE"]
            if "SUPERTONIC_SPEED" in env_values:
                Config.SUPERTONIC_SPEED = float(env_values["SUPERTONIC_SPEED"])
            if "SUPERTONIC_STEPS" in env_values:
                Config.SUPERTONIC_STEPS = int(env_values["SUPERTONIC_STEPS"])
            if "RVC_ENABLED" in env_values:
                Config.RVC_ENABLED = env_values["RVC_ENABLED"].lower() == "true"
            if "DEFAULT_RVC_MODEL" in env_values:
                Config.DEFAULT_RVC_MODEL = env_values["DEFAULT_RVC_MODEL"]

            # Reload LLM settings
            if "LLM_PROVIDER" in env_values:
                Config.LLM_PROVIDER = env_values["LLM_PROVIDER"]
            if "OLLAMA_MODEL" in env_values:
                Config.OLLAMA_MODEL = env_values["OLLAMA_MODEL"]
            if "OLLAMA_TEMPERATURE" in env_values:
                Config.OLLAMA_TEMPERATURE = float(env_values["OLLAMA_TEMPERATURE"])
            if "OLLAMA_MAX_TOKENS" in env_values:
                Config.OLLAMA_MAX_TOKENS = int(env_values["OLLAMA_MAX_TOKENS"])
            if "OPENROUTER_API_KEY" in env_values:
                Config.OPENROUTER_API_KEY = env_values["OPENROUTER_API_KEY"]
            if "OPENROUTER_MODEL" in env_values:
                Config.OPENROUTER_MODEL = env_values["OPENROUTER_MODEL"]
            if "LLM_FREQUENCY_PENALTY" in env_values:
                Config.LLM_FREQUENCY_PENALTY = float(env_values["LLM_FREQUENCY_PENALTY"])
            if "LLM_PRESENCE_PENALTY" in env_values:
                Config.LLM_PRESENCE_PENALTY = float(env_values["LLM_PRESENCE_PENALTY"])
            if "LLM_TOP_P" in env_values:
                Config.LLM_TOP_P = float(env_values["LLM_TOP_P"])
            if "OLLAMA_REPEAT_PENALTY" in env_values:
                Config.OLLAMA_REPEAT_PENALTY = float(env_values["OLLAMA_REPEAT_PENALTY"])
            if "OLLAMA_MIN_P" in env_values:
                Config.OLLAMA_MIN_P = float(env_values["OLLAMA_MIN_P"])
            if "OLLAMA_TOP_K" in env_values:
                Config.OLLAMA_TOP_K = int(env_values["OLLAMA_TOP_K"])

            logger.info("Reloaded config from .env file")
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")

    async def handle_get_config(self, request):
        """Get current configuration values."""
        try:
            # Reload from .env to ensure we have latest values
            self.reload_config_from_env()

            # Debug: Log what Config has loaded
            logger.debug(f"Config.AMBIENT_CHANNELS = {Config.AMBIENT_CHANNELS}")
            logger.debug(f"Config.AUTO_REPLY_CHANNELS = {Config.AUTO_REPLY_CHANNELS}")
            logger.debug(f"Config.AMBIENT_IGNORE_USERS = {Config.AMBIENT_IGNORE_USERS}")

            # Helper to resolve channel IDs to names
            def resolve_channels(channel_ids):
                logger.debug(f"Resolving channels: {channel_ids}")
                resolved = []
                for cid in channel_ids:
                    channel = self.bot.get_channel(cid)
                    if channel:
                        resolved.append({"id": cid, "name": f"#{channel.name}"})
                    else:
                        # Try to find in all guilds
                        found = False
                        for guild in self.bot.guilds:
                            channel = guild.get_channel(cid)
                            if channel:
                                resolved.append({"id": cid, "name": f"#{channel.name}"})
                                found = True
                                break
                        if not found:
                            resolved.append({"id": cid, "name": f"ID: {cid}"})
                return resolved

            # Helper to resolve user IDs to names
            def resolve_users(user_ids):
                resolved = []
                for uid in user_ids:
                    user = self.bot.get_user(uid)
                    if user:
                        resolved.append({"id": uid, "name": user.display_name})
                    else:
                        # Try to find in guild members
                        found = False
                        for guild in self.bot.guilds:
                            member = guild.get_member(uid)
                            if member:
                                resolved.append({"id": uid, "name": member.display_name})
                                found = True
                                break
                        if not found:
                            resolved.append({"id": uid, "name": f"ID: {uid}"})
                return resolved

            # Editable config sections
            config = {
                "ambient": {
                    "AMBIENT_MODE_ENABLED": Config.AMBIENT_MODE_ENABLED,
                    "AMBIENT_CHANNELS": Config.AMBIENT_CHANNELS,
                    "AMBIENT_CHANNELS_RESOLVED": resolve_channels(Config.AMBIENT_CHANNELS),
                    "AMBIENT_IGNORE_USERS": Config.AMBIENT_IGNORE_USERS,
                    "AMBIENT_IGNORE_USERS_RESOLVED": resolve_users(Config.AMBIENT_IGNORE_USERS),
                    "AMBIENT_LULL_TIMEOUT": Config.AMBIENT_LULL_TIMEOUT,
                    "AMBIENT_MIN_INTERVAL": Config.AMBIENT_MIN_INTERVAL,
                    "AMBIENT_CHANCE": Config.AMBIENT_CHANCE,
                },
                "chat": {
                    "AUTO_REPLY_ENABLED": Config.AUTO_REPLY_ENABLED,
                    "AUTO_REPLY_CHANNELS": Config.AUTO_REPLY_CHANNELS,
                    "AUTO_REPLY_CHANNELS_RESOLVED": resolve_channels(Config.AUTO_REPLY_CHANNELS),
                    "CHAT_HISTORY_MAX_MESSAGES": Config.CHAT_HISTORY_MAX_MESSAGES,
                    "CONVERSATION_TIMEOUT": Config.CONVERSATION_TIMEOUT,
                },
                "voice": {
                    "TTS_ENGINE": Config.TTS_ENGINE,
                    "DEFAULT_TTS_VOICE": Config.DEFAULT_TTS_VOICE,
                    "KOKORO_VOICE": Config.KOKORO_VOICE,
                    "KOKORO_SPEED": Config.KOKORO_SPEED,
                    "SUPERTONIC_VOICE": Config.SUPERTONIC_VOICE,
                    "SUPERTONIC_SPEED": Config.SUPERTONIC_SPEED,
                    "SUPERTONIC_STEPS": Config.SUPERTONIC_STEPS,
                    "RVC_ENABLED": Config.RVC_ENABLED,
                    "DEFAULT_RVC_MODEL": Config.DEFAULT_RVC_MODEL,
                },
                "llm": {
                    "LLM_PROVIDER": Config.LLM_PROVIDER,
                    "OLLAMA_MODEL": Config.OLLAMA_MODEL,
                    "OLLAMA_TEMPERATURE": Config.OLLAMA_TEMPERATURE,
                    "OLLAMA_MAX_TOKENS": Config.OLLAMA_MAX_TOKENS,
                    "OPENROUTER_API_KEY": Config.OPENROUTER_API_KEY,
                    "OPENROUTER_MODEL": Config.OPENROUTER_MODEL,
                    "LLM_FREQUENCY_PENALTY": Config.LLM_FREQUENCY_PENALTY,
                    "LLM_PRESENCE_PENALTY": Config.LLM_PRESENCE_PENALTY,
                    "LLM_TOP_P": Config.LLM_TOP_P,
                    "OLLAMA_REPEAT_PENALTY": Config.OLLAMA_REPEAT_PENALTY,
                    "OLLAMA_MIN_P": Config.OLLAMA_MIN_P,
                    "OLLAMA_TOP_K": Config.OLLAMA_TOP_K,
                },
            }
            return web.json_response(config)
        except Exception as e:
            logger.error(f"Get config failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_set_config(self, request):
        """Update configuration values and save to .env file."""
        try:
            data = await request.json()
            env_path = Path(".env")

            if not env_path.exists():
                return web.json_response({"success": False, "error": ".env file not found"})

            updated = []

            for key, value in data.items():
                # Convert lists to comma-separated strings
                if isinstance(value, list):
                    value = ",".join(str(v) for v in value)
                # Convert booleans to lowercase strings
                elif isinstance(value, bool):
                    value = "true" if value else "false"
                else:
                    value = str(value)

                # Update .env file
                set_key(str(env_path), key, value)
                updated.append(key)

                # Update runtime config
                if hasattr(Config, key):
                    current_type = type(getattr(Config, key))
                    if current_type == bool:
                        setattr(Config, key, value.lower() == "true")
                    elif current_type == int:
                        setattr(Config, key, int(value) if value else 0)
                    elif current_type == float:
                        setattr(Config, key, float(value) if value else 0.0)
                    elif current_type == list:
                        if value:
                            setattr(Config, key, [int(x.strip()) for x in value.split(",") if x.strip()])
                        else:
                            setattr(Config, key, [])
                    else:
                        setattr(Config, key, value)

            self.set_status("Config Updated", f"Updated: {', '.join(updated)}")
            logger.info(f"Config updated: {updated}")

            return web.json_response({
                "success": True,
                "message": f"Updated {len(updated)} setting(s)",
                "updated": updated,
                "note": "Some changes may require bot restart"
            })

        except Exception as e:
            logger.error(f"Set config failed: {e}")
            return web.json_response({"success": False, "error": str(e)})

    async def handle_get_sounds(self, request):
        """Get all sound effects and their config."""
        # Sound effects feature disabled
        return web.json_response({"error": "Sound effects feature is currently disabled"}, status=501)
        try:
            pass  # sound_service = await get_sound_effects_service()

            # Get all effects with their details
            effects = []
            for effect in sound_service.effects:
                effects.append({
                    "name": effect.name,
                    "file": os.path.basename(effect.file_path),
                    "triggers": effect.triggers,
                    "cooldown": effect.cooldown,
                    "volume": effect.volume,
                    "ready": effect.can_play(),
                    "last_played": effect.last_played.isoformat() if effect.last_played else None
                })

            return web.json_response({
                "success": True,
                "effects": effects,
                "enabled": sound_service.enabled,
                "global_volume": sound_service.global_volume
            })
        except Exception as e:
            logger.error(f"Get sounds failed: {e}")
            return web.json_response({"success": False, "error": str(e)})

    async def handle_upload_sound(self, request):
        """Handle sound file upload."""
        return web.json_response({"error": "Sound effects feature is currently disabled"}, status=501)
        try:
            reader = await request.multipart()

            # Read the file data
            field = await reader.next()
            if not field or field.name != 'file':
                return web.json_response({"success": False, "error": "No file uploaded"})

            filename = field.filename
            if not filename:
                return web.json_response({"success": False, "error": "No filename provided"})

            # Validate file extension
            allowed_extensions = {'.mp3', '.wav', '.ogg', '.m4a'}
            ext = os.path.splitext(filename)[1].lower()
            if ext not in allowed_extensions:
                return web.json_response({
                    "success": False,
                    "error": f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
                })

            # Save the file
            sound_effects_dir = Path("sound_effects")
            sound_effects_dir.mkdir(exist_ok=True)

            # Sanitize filename
            safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
            file_path = sound_effects_dir / safe_filename

            # Write file
            size = 0
            with open(file_path, 'wb') as f:
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    size += len(chunk)
                    f.write(chunk)

            logger.info(f"Uploaded sound file: {safe_filename} ({size} bytes)")

            return web.json_response({
                "success": True,
                "filename": safe_filename,
                "size": size,
                "message": f"Uploaded {safe_filename}. Now add it to config!"
            })

        except Exception as e:
            logger.error(f"Upload sound failed: {e}")
            return web.json_response({"success": False, "error": str(e)})

    async def handle_update_sound_config(self, request):
        """Update sound effects configuration."""
        return web.json_response({"error": "Sound effects feature is currently disabled"}, status=501)
        try:
            data = await request.json()

            config_path = Path("sound_effects/config.json")

            # Read current config
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Update based on action
            action = data.get('action')

            if action == 'add':
                # Add new effect
                new_effect = {
                    "name": data.get('name'),
                    "file": data.get('file'),
                    "triggers": data.get('triggers', []),
                    "cooldown": data.get('cooldown', 10),
                    "volume": data.get('volume', 0.5)
                }
                config['effects'].append(new_effect)

            elif action == 'update':
                # Update existing effect
                name = data.get('name')
                for effect in config['effects']:
                    if effect['name'] == name:
                        effect['triggers'] = data.get('triggers', effect['triggers'])
                        effect['cooldown'] = data.get('cooldown', effect['cooldown'])
                        effect['volume'] = data.get('volume', effect['volume'])
                        break

            elif action == 'global':
                # Update global settings
                if 'global_volume' in data:
                    config['global_volume'] = data['global_volume']
                if 'enabled' in data:
                    config['enabled'] = data['enabled']

            # Save config
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)

            # Reload sound service
            sound_service = await get_sound_effects_service()
            await sound_service.reload_config()

            logger.info(f"Sound config updated: {action}")

            return web.json_response({
                "success": True,
                "message": "Config updated and reloaded"
            })

        except Exception as e:
            logger.error(f"Update sound config failed: {e}")
            return web.json_response({"success": False, "error": str(e)})

    async def handle_delete_sound(self, request):
        """Delete a sound effect."""
        return web.json_response({"error": "Sound effects feature is currently disabled"}, status=501)
        try:
            data = await request.json()
            name = data.get('name')

            if not name:
                return web.json_response({"success": False, "error": "No name provided"})

            config_path = Path("sound_effects/config.json")

            # Read config
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Find and remove effect
            effect_to_remove = None
            for effect in config['effects']:
                if effect['name'] == name:
                    effect_to_remove = effect
                    break

            if not effect_to_remove:
                return web.json_response({"success": False, "error": "Effect not found"})

            # Remove from config
            config['effects'].remove(effect_to_remove)

            # Optionally delete the file
            if data.get('delete_file', False):
                file_path = Path("sound_effects") / effect_to_remove['file']
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted sound file: {file_path}")

            # Save config
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)

            # Reload
            sound_service = await get_sound_effects_service()
            await sound_service.reload_config()

            logger.info(f"Deleted sound effect: {name}")

            return web.json_response({
                "success": True,
                "message": f"Deleted {name}"
            })

        except Exception as e:
            logger.error(f"Delete sound failed: {e}")
            return web.json_response({"success": False, "error": str(e)})

    async def handle_toggle_sounds(self, request):
        """Toggle sound effects on/off."""
        return web.json_response({"error": "Sound effects feature is currently disabled"}, status=501)
        try:
            sound_service = await get_sound_effects_service()
            sound_service.enabled = not sound_service.enabled

            # Update config file
            config_path = Path("sound_effects/config.json")
            with open(config_path, 'r') as f:
                config = json.load(f)
            config['enabled'] = sound_service.enabled
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)

            status = "enabled" if sound_service.enabled else "disabled"
            logger.info(f"Sound effects {status}")

            return web.json_response({
                "success": True,
                "enabled": sound_service.enabled,
                "message": f"Sound effects {status}"
            })

        except Exception as e:
            logger.error(f"Toggle sounds failed: {e}")
            return web.json_response({"success": False, "error": str(e)})

    async def start(self, port=8080):
        try:
            # Disable access log to avoid cluttering the console with status checks
            self.runner = web.AppRunner(self.app, access_log=None)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, '0.0.0.0', port)
            await self.site.start()
            logger.info(f"Web dashboard started on http://localhost:{port}")
        except Exception as e:
            logger.error(f"Failed to start web dashboard: {e}")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
