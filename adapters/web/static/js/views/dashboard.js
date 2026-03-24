/**
 * Dashboard View
 * 
 * Overview page with runtime status and quick stats.
 */

import api from '../api.js';

class DashboardView {
    constructor() {
        this.status = null;
        this.refreshInterval = null;
    }

    async mount() {
        const content = document.getElementById('content');
        content.innerHTML = this._render();

        // Cache DOM elements
        this.runtimeModel = document.getElementById('dash-model');
        this.runtimeCache = document.getElementById('dash-cache');
        this.runtimeTokens = document.getElementById('dash-tokens');
        this.runtimeProvider = document.getElementById('dash-provider');
        this.personaCount = document.getElementById('dash-personas');
        this.commandCount = document.getElementById('dash-commands');
        this.approvalCount = document.getElementById('dash-pending');
        this.quickActions = document.getElementById('quick-actions');

        // Initial load
        await this.loadDashboard();

        // Auto-refresh every 5 seconds
        this.refreshInterval = setInterval(() => this.loadDashboard(), 5000);
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
                <h2>Dashboard</h2>
                <p>Runtime overview and quick stats</p>
            </div>
            
            <div class="runtime-panel">
                <div class="runtime-card">
                    <span class="label">Cache Model</span>
                    <div class="value" id="dash-model">--</div>
                    <div class="meta">stable prefix caching</div>
                </div>
                <div class="runtime-card">
                    <span class="label">Last Cache</span>
                    <div class="value" id="dash-cache">--</div>
                    <div class="meta">hit/miss status</div>
                </div>
                <div class="runtime-card">
                    <span class="label">Tokens Saved</span>
                    <div class="value" id="dash-tokens">0</div>
                    <div class="meta">cached input tokens</div>
                </div>
                <div class="runtime-card">
                    <span class="label">Provider</span>
                    <div class="value" id="dash-provider">--</div>
                    <div class="meta">active provider</div>
                </div>
            </div>
            
            <div class="card-grid">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">📦 Personas</span>
                        <span class="badge badge-info" id="dash-personas">--</span>
                    </div>
                    <div class="card-body">
                        Available personas in the catalog
                        <div class="mt-4">
                            <a href="#/chat" class="btn btn-primary btn-sm">Go to Chat</a>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">⌨️ Commands</span>
                        <span class="badge badge-info" id="dash-commands">--</span>
                    </div>
                    <div class="card-body">
                        Registered runtime commands
                        <div class="mt-4">
                            <span class="text-muted">Use /help in chat</span>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">⏳ Pending Approvals</span>
                        <span class="badge badge-warning" id="dash-pending">--</span>
                    </div>
                    <div class="card-body">
                        Tool executions awaiting approval
                        <div class="mt-4">
                            <a href="#/approvals" class="btn btn-secondary btn-sm">Review</a>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card mt-4">
                <div class="card-header">
                    <span class="card-title">⚡ Quick Actions</span>
                </div>
                <div class="card-body" id="quick-actions">
                    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                        <a href="#/chat" class="btn btn-primary">Open Chat</a>
                        <a href="#/sessions" class="btn btn-secondary">View Sessions</a>
                        <a href="#/context" class="btn btn-secondary">Check Cache</a>
                        <a href="#/approvals" class="btn btn-secondary">Review Approvals</a>
                    </div>
                </div>
            </div>
        `;
    }

    async loadDashboard() {
        try {
            // Load multiple endpoints in parallel
            const [statusData, commandsData, personasData, approvalsData] = await Promise.all([
                api.getStatus(),
                api.getCommands(),
                api.listPersonas(),
                api.getApprovals().catch(() => ({ outputs: [] }))
            ]);

            const snapshot = statusData.snapshot || {};
            const providerUsage = snapshot.provider_usage || {};

            // Update cards
            this.runtimeModel.textContent = snapshot.cache_model || 'stable_prefix';
            this.runtimeCache.textContent = this.formatCacheHit(snapshot.last_cache_hit);
            this.runtimeTokens.textContent = String(snapshot.tokens_saved_estimate || 0);
            this.runtimeProvider.textContent = `${snapshot.provider || 'default'} · ${snapshot.model || 'default'}`;
            
            this.personaCount.textContent = String((personasData.personas || []).length);
            this.commandCount.textContent = String((commandsData.commands || []).length);

            // Extract approval count
            let approvalCount = 0;
            for (const output of approvalsData.outputs || []) {
                if (output.type === 'StructuredOutput' && output.data) {
                    approvalCount = output.data.count || 0;
                    break;
                }
            }
            this.approvalCount.textContent = String(approvalCount);

        } catch (error) {
            console.error('Dashboard load error:', error);
        }
    }

    formatCacheHit(lastHit) {
        if (lastHit === true) return '✓ hit';
        if (lastHit === false) return '✗ miss';
        return '--';
    }
}

const dashboardView = new DashboardView();
export default dashboardView;
