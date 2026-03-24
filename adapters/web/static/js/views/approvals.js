/**
 * Approvals View
 * 
 * Pending tool approval queue management.
 */

import api from '../api.js';

class ApprovalsView {
    constructor() {
        this.approvals = [];
        this.refreshInterval = null;
        this.actionInFlight = false;
    }

    async mount() {
        const content = document.getElementById('content');
        content.innerHTML = this._render();

        this.container = document.getElementById('approvals-container');
        this.countEl = document.getElementById('approval-count');
        this.refreshBtn = document.getElementById('refresh-approvals');

        this.refreshBtn.addEventListener('click', () => this.loadApprovals());

        // Initial load
        await this.loadApprovals();

        // Auto-refresh every 3 seconds
        this.refreshInterval = setInterval(() => this.loadApprovals(), 3000);
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
                <h2>Pending Approvals</h2>
                <p>Review and approve tool executions</p>
            </div>
            
            <div class="runtime-panel">
                <div class="runtime-card">
                    <span class="label">Pending</span>
                    <div class="value" id="approval-count">0</div>
                    <div class="meta">awaiting approval</div>
                </div>
            </div>
            
            <div class="card mb-4">
                <div class="card-header">
                    <span class="card-title">Actions</span>
                    <button id="refresh-approvals" class="btn btn-secondary btn-sm">Refresh</button>
                </div>
            </div>
            
            <div id="approvals-container">
                <div class="loading">
                    <div class="spinner"></div>
                    Loading approvals...
                </div>
            </div>
        `;
    }

    async loadApprovals() {
        if (this.actionInFlight) return;

        try {
            const response = await api.getApprovals();
            const outputs = response.outputs || [];
            
            // Extract approvals from command output
            let pendingApprovals = { count: 0, items: [] };
            for (const output of outputs) {
                if (output.type === 'StructuredOutput' && output.data) {
                    pendingApprovals = output.data;
                    break;
                }
            }

            this.approvals = pendingApprovals.items || [];
            this.renderApprovals();
        } catch (error) {
            console.error('Failed to load approvals:', error);
        }
    }

    renderApprovals() {
        this.countEl.textContent = String(this.approvals.length);

        if (this.approvals.length === 0) {
            this.container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">✅</div>
                    <h3>No Pending Approvals</h3>
                    <p>All tool executions have been reviewed</p>
                </div>
            `;
            return;
        }

        const approvalItems = this.approvals.map(approval => this.renderApprovalItem(approval)).join('');

        this.container.innerHTML = `
            <div class="approval-list">
                ${approvalItems}
            </div>
        `;
    }

    renderApprovalItem(approval) {
        const toolName = approval.tool_name || 'unknown_tool';
        const approvalId = approval.approval_id || '';
        const args = approval.arguments || {};
        const argsText = Object.entries(args)
            .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
            .join('\n') || 'No arguments';

        return `
            <div class="approval-item">
                <div class="approval-item-header">
                    <div class="approval-tool">${this.escapeHtml(toolName)}</div>
                    <div class="approval-id">${this.escapeHtml(approvalId)}</div>
                </div>
                <div class="approval-meta">${this.escapeHtml(argsText)}</div>
                <div class="approval-actions">
                    <button class="btn btn-success btn-sm" onclick="window.approvalsView.applyApproval('${this.escapeHtml(approvalId)}')">
                        Approve
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="window.approvalsView.rejectApproval('${this.escapeHtml(approvalId)}')">
                        Reject
                    </button>
                </div>
            </div>
        `;
    }

    async applyApproval(approvalId) {
        if (this.actionInFlight || !approvalId) return;
        
        this.actionInFlight = true;
        try {
            await api.applyApproval(approvalId);
            await this.loadApprovals();
        } catch (error) {
            alert(`Failed to approve: ${error.message}`);
        } finally {
            this.actionInFlight = false;
        }
    }

    async rejectApproval(approvalId) {
        if (this.actionInFlight || !approvalId) return;

        if (!confirm('Are you sure you want to reject this tool execution?')) return;
        
        this.actionInFlight = true;
        try {
            await api.rejectApproval(approvalId);
            await this.loadApprovals();
        } catch (error) {
            alert(`Failed to reject: ${error.message}`);
        } finally {
            this.actionInFlight = false;
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

const approvalsView = new ApprovalsView();
// Expose for onclick handlers
window.approvalsView = approvalsView;
export default approvalsView;
