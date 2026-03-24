/**
 * Traces View
 * 
 * Runtime trace inspector for debugging and monitoring.
 */

import api from '../api.js';

class TracesView {
    constructor() {
        this.traces = [];
        this.limit = 50;
    }

    async mount() {
        const content = document.getElementById('content');
        content.innerHTML = this._render();

        this.container = document.getElementById('traces-container');
        this.limitSelect = document.getElementById('trace-limit');
        this.refreshBtn = document.getElementById('refresh-traces');

        this.refreshBtn.addEventListener('click', () => this.loadTraces());
        this.limitSelect.addEventListener('change', (e) => {
            this.limit = parseInt(e.target.value);
            this.loadTraces();
        });

        await this.loadTraces();
    }

    unmount() {
        // Cleanup if needed
    }

    _render() {
        return `
            <div class="page-header">
                <h2>Runtime Traces</h2>
                <p>Inspect runtime execution traces</p>
            </div>
            
            <div class="card mb-4">
                <div class="card-header">
                    <span class="card-title">Trace Settings</span>
                    <div style="display: flex; gap: 12px; align-items: center;">
                        <label>Limit:</label>
                        <select id="trace-limit">
                            <option value="25">25</option>
                            <option value="50" selected>50</option>
                            <option value="100">100</option>
                            <option value="200">200</option>
                        </select>
                        <button id="refresh-traces" class="btn btn-secondary btn-sm">Refresh</button>
                    </div>
                </div>
            </div>
            
            <div id="traces-container">
                <div class="loading">
                    <div class="spinner"></div>
                    Loading traces...
                </div>
            </div>
        `;
    }

    async loadTraces() {
        try {
            this.container.innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    Loading traces...
                </div>
            `;

            const data = await api.getTrace(this.limit);
            this.traces = data.trace || [];
            this.renderTraces();
        } catch (error) {
            this.container.innerHTML = `
                <div class="error-message">
                    Failed to load traces: ${error.message}
                </div>
            `;
        }
    }

    renderTraces() {
        if (this.traces.length === 0) {
            this.container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <h3>No Traces</h3>
                    <p>Run some commands to generate traces</p>
                </div>
            `;
            return;
        }

        const traceItems = this.traces.map(trace => this.renderTraceItem(trace)).join('');

        this.container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">${this.traces.length} Trace Entries</span>
                </div>
                <div class="card-body" style="padding: 0;">
                    <div style="max-height: 600px; overflow-y: auto;">
                        ${traceItems}
                    </div>
                </div>
            </div>
        `;
    }

    renderTraceItem(trace) {
        const type = trace.type || 'unknown';
        const timestamp = trace.timestamp 
            ? new Date(trace.timestamp).toLocaleTimeString()
            : '-';
        
        let badgeClass = 'badge-info';
        if (type.includes('error')) badgeClass = 'badge-error';
        else if (type.includes('tool')) badgeClass = 'badge-warning';
        else if (type.includes('chat')) badgeClass = 'badge-success';

        const details = JSON.stringify(trace, null, 2);

        return `
            <div style="border-bottom: 1px solid var(--border-color); padding: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="display: flex; gap: 12px; align-items: center;">
                        <span class="badge ${badgeClass}">${type}</span>
                        <span style="font-size: 12px; color: var(--text-muted);">${timestamp}</span>
                    </div>
                </div>
                <div class="code-block" style="font-size: 12px; max-height: 200px; overflow: auto;">
                    ${this.escapeHtml(details)}
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

const tracesView = new TracesView();
export default tracesView;
