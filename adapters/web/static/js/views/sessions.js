/**
 * Sessions View
 * 
 * Lists and manages active runtime sessions.
 */

import api from '../api.js';

class SessionsView {
    constructor() {
        this.sessions = [];
        this.refreshInterval = null;
    }

    async mount() {
        const content = document.getElementById('content');
        content.innerHTML = this._render();

        this.container = document.getElementById('sessions-container');
        
        // Initial load
        await this.loadSessions();
        
        // Auto-refresh every 5 seconds
        this.refreshInterval = setInterval(() => this.loadSessions(), 5000);
    }

    unmount() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    _render() {
        return `
            <div class="page-header">
                <h2>Active Sessions</h2>
                <p>View and manage runtime sessions</p>
            </div>
            
            <div id="sessions-container">
                <div class="loading">
                    <div class="spinner"></div>
                    Loading sessions...
                </div>
            </div>
        `;
    }

    async loadSessions() {
        try {
            const data = await api.listSessions(20);
            this.sessions = data.sessions || [];
            this.renderSessions();
        } catch (error) {
            this.container.innerHTML = `
                <div class="error-message">
                    Failed to load sessions: ${error.message}
                </div>
            `;
        }
    }

    renderSessions() {
        if (this.sessions.length === 0) {
            this.container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <h3>No Active Sessions</h3>
                    <p>Start a conversation to create a session</p>
                </div>
            `;
            return;
        }

        const rows = this.sessions.map(session => this.renderSessionRow(session)).join('');

        this.container.innerHTML = `
            <div class="card">
                <div class="table-container">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Session ID</th>
                                <th>Persona</th>
                                <th>Platform</th>
                                <th>Room</th>
                                <th>Mode</th>
                                <th>Provider</th>
                                <th>YOLO</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    renderSessionRow(session) {
        return `
            <tr>
                <td><code>${this.escapeHtml(session.session_id)}</code></td>
                <td>${this.escapeHtml(session.persona_id)}</td>
                <td><span class="badge badge-info">${this.escapeHtml(session.platform)}</span></td>
                <td>${this.escapeHtml(session.room_id || '-')}</td>
                <td>${session.mode ? this.escapeHtml(session.mode) : '-'}</td>
                <td>${this.escapeHtml(session.provider || 'default')}</td>
                <td>${session.yolo ? 'on' : 'off'}</td>
            </tr>
        `;
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

const sessionsView = new SessionsView();
export default sessionsView;
