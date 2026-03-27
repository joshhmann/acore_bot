/**
 * Tools View
 * 
 * Tool registry browser and management.
 */

import api from '../api.js';

class ToolsView {
    constructor() {
        this.tools = [];
    }

    async mount() {
        const content = document.getElementById('content');
        content.innerHTML = this._render();

        this.container = document.getElementById('tools-container');
        this.refreshBtn = document.getElementById('refresh-tools');

        this.refreshBtn.addEventListener('click', () => this.loadTools());

        await this.loadTools();
    }

    unmount() {
        // Cleanup if needed
    }

    _render() {
        return `
            <div class="page-header">
                <h2>Tool Registry</h2>
                <p>Browse available tools and their schemas</p>
            </div>
            
            <div class="card mb-4">
                <div class="card-header">
                    <span class="card-title">Actions</span>
                    <button id="refresh-tools" class="btn btn-secondary btn-sm">Refresh</button>
                </div>
            </div>
            
            <div id="tools-container">
                <div class="loading">
                    <div class="spinner"></div>
                    Loading tools...
                </div>
            </div>
        `;
    }

    async loadTools() {
        try {
            this.container.innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    Loading tools...
                </div>
            `;

            const data = await api.getTools();
            this.tools = data.tools || [];
            this.renderTools();
        } catch (error) {
            this.container.innerHTML = `
                <div class="error-message">
                    Failed to load tools: ${error.message}
                </div>
            `;
        }
    }

    renderTools() {
        if (this.tools.length === 0) {
            this.container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔧</div>
                    <h3>No Tools Available</h3>
                    <p>No tools are registered with the runtime</p>
                </div>
            `;
            return;
        }

        const toolCards = this.tools.map(tool => this.renderToolCard(tool)).join('');

        this.container.innerHTML = `
            <div class="card-grid">
                ${toolCards}
            </div>
        `;
    }

    renderToolCard(tool) {
        const name = tool.name || tool.id || 'Unknown';
        const source = tool.source || 'builtin';
        const riskTier = tool.risk_tier || 'low';
        const enabled = tool.enabled !== false;
        
        let riskBadge = 'badge-success';
        if (riskTier === 'medium') riskBadge = 'badge-warning';
        else if (riskTier === 'high') riskBadge = 'badge-error';

        return `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">${this.escapeHtml(name)}</span>
                    <span class="badge ${riskBadge}">${riskTier}</span>
                </div>
                <div class="card-body">
                    <div style="display: grid; gap: 8px; font-size: 13px;">
                        <div><strong>Source:</strong> ${this.escapeHtml(source)}</div>
                        <div><strong>Enabled:</strong> ${enabled ? 'yes' : 'no'}</div>
                        <div><strong>Policy:</strong> runtime-owned tool registry snapshot</div>
                    </div>
                </div>
            </div>
        `;
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

const toolsView = new ToolsView();
export default toolsView;
