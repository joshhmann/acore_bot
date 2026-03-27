/**
 * Context View
 * 
 * Context cache explorer and memory inspection.
 */

import api from '../api.js';

class ContextView {
    constructor() {
        this.snapshot = null;
    }

    async mount() {
        const content = document.getElementById('content');
        content.innerHTML = this._render();

        this.container = document.getElementById('context-container');
        this.refreshBtn = document.getElementById('refresh-context');
        this.resetBtn = document.getElementById('reset-context');

        this.refreshBtn.addEventListener('click', () => this.loadContext());
        this.resetBtn.addEventListener('click', () => this.resetContext());

        await this.loadContext();
    }

    unmount() {
        // Cleanup if needed
    }

    _render() {
        return `
            <div class="page-header">
                <h2>Context Cache</h2>
                <p>Inspect runtime context caching and memory</p>
            </div>
            
            <div class="runtime-panel" id="context-stats">
                <div class="runtime-card">
                    <span class="label">Cache Model</span>
                    <div class="value" id="cache-model">--</div>
                    <div class="meta" id="cache-reason">--</div>
                </div>
                <div class="runtime-card">
                    <span class="label">Cache Hit</span>
                    <div class="value" id="cache-hit">--</div>
                    <div class="meta" id="cache-key">--</div>
                </div>
                <div class="runtime-card">
                    <span class="label">Tokens Saved</span>
                    <div class="value" id="tokens-saved">0</div>
                    <div class="meta" id="provider-cached">provider cached input 0</div>
                </div>
                <div class="runtime-card">
                    <span class="label">Entries</span>
                    <div class="value" id="cache-entries">0</div>
                    <div class="meta">cached entries</div>
                </div>
            </div>
            
            <div class="card mb-4">
                <div class="card-header">
                    <span class="card-title">Actions</span>
                    <div style="display: flex; gap: 12px;">
                        <button id="refresh-context" class="btn btn-secondary btn-sm">Refresh</button>
                        <button id="reset-context" class="btn btn-danger btn-sm">Reset Cache</button>
                    </div>
                </div>
            </div>
            
            <div id="context-container">
                <div class="loading">
                    <div class="spinner"></div>
                    Loading context...
                </div>
            </div>
        `;
    }

    async loadContext() {
        try {
            const data = await api.getContext();
            this.snapshot = data.snapshot || {};
            this.renderContext();
        } catch (error) {
            this.container.innerHTML = `
                <div class="error-message">
                    Failed to load context: ${error.message}
                </div>
            `;
        }
    }

    async resetContext() {
        if (!confirm('Are you sure you want to reset the context cache?')) return;

        try {
            this.resetBtn.disabled = true;
            await api.resetContext();
            await this.loadContext();
        } catch (error) {
            alert(`Failed to reset cache: ${error.message}`);
        } finally {
            this.resetBtn.disabled = false;
        }
    }

    renderContext() {
        const s = this.snapshot;

        // Update stats cards
        document.getElementById('cache-model').textContent = s.cache_model || 'stable_prefix';
        document.getElementById('cache-reason').textContent = s.last_cache_reason || 'No cache activity';
        document.getElementById('cache-hit').textContent = this.formatCacheHit(s.last_cache_hit);
        document.getElementById('cache-key').textContent = s.last_cache_key ? s.last_cache_key.substring(0, 30) + '...' : 'No cache key';
        document.getElementById('tokens-saved').textContent = String(s.tokens_saved_estimate || 0);
        document.getElementById('provider-cached').textContent = `provider cached input ${s.provider_cached_input_tokens || 0}`;
        document.getElementById('cache-entries').textContent = String((s.entries || []).length);

        // Render entries
        const entries = s.entries || [];
        
        if (entries.length === 0) {
            this.container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">💾</div>
                    <h3>No Cache Entries</h3>
                    <p>Context cache is empty</p>
                </div>
            `;
            return;
        }

        const entriesHtml = entries.map(entry => `
            <div style="border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 16px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <code style="font-size: 12px;">${this.escapeHtml(entry.cache_key || 'unknown')}</code>
                    <span class="badge badge-info">${entry.hit_count || 0} hits</span>
                </div>
                <div style="font-size: 13px; color: var(--text-secondary);">
                    <div>Persona: ${this.escapeHtml(entry.persona_id || '-')}</div>
                    <div>Mode: ${this.escapeHtml(entry.mode || '-')}</div>
                    <div>Provider: ${this.escapeHtml(entry.provider || '-')}</div>
                    <div>Tokens: ~${entry.context_tokens_estimate || 0}</div>
                </div>
            </div>
        `).join('');

        this.container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Cache Entries (${entries.length})</span>
                </div>
                <div class="card-body">
                    ${entriesHtml}
                </div>
            </div>
        `;
    }

    formatCacheHit(lastHit) {
        if (lastHit === true) return '✓ hit';
        if (lastHit === false) return '✗ miss';
        return '--';
    }

    escapeHtml(text) {
        if (!text) return '-';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

const contextView = new ContextView();
export default contextView;
