/**
 * Runtime API Client
 * 
 * Provides typed interface to the Gestalt Runtime API.
 * All data flows from runtime - no local state reconstruction.
 */

class RuntimeAPI {
    constructor() {
        this.baseUrl = '';
        this.defaultSessionId = 'web:main';
        this.defaultRoomId = 'web_chat';
        this.defaultPlatform = 'web';
    }

    /**
     * Build runtime context payload for requests
     */
    _payload(options = {}) {
        return {
            session_id: options.sessionId || this.defaultSessionId,
            persona_id: options.personaId || 'default',
            room_id: options.roomId || this.defaultRoomId,
            platform: options.platform || this.defaultPlatform,
            mode: options.mode || '',
            flags: options.flags || {},
            user_id: options.userId || 'web_user'
        };
    }

    /**
     * Make API request with error handling
     */
    async _request(method, endpoint, body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, options);
            
            if (!response.ok) {
                const error = await response.text();
                throw new Error(`HTTP ${response.status}: ${error}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    // Health & Status
    
    async getHealth() {
        return this._request('GET', '/health');
    }

    async getCommands() {
        return this._request('GET', '/api/runtime/commands');
    }

    async getStatus(options = {}) {
        return this._request('POST', '/api/runtime/status', this._payload(options));
    }

    // Sessions

    async getSession(options = {}) {
        return this._request('POST', '/api/runtime/session', this._payload(options));
    }

    async listSessions(limit = 10, options = {}) {
        const payload = {
            ...this._payload(options),
            limit,
            user_scope: options.userScope || ''
        };
        return this._request('POST', '/api/runtime/sessions', payload);
    }

    // Runtime Introspection

    async getTrace(limit = 50, options = {}) {
        const payload = {
            ...this._payload(options),
            limit
        };
        return this._request('POST', '/api/runtime/trace', payload);
    }

    async getContext(options = {}) {
        return this._request('POST', '/api/runtime/context', this._payload(options));
    }

    async resetContext(options = {}) {
        return this._request('POST', '/api/runtime/context/reset', this._payload(options));
    }

    async getTools(options = {}) {
        return this._request('POST', '/api/runtime/tools', this._payload(options));
    }

    async getProviders(options = {}) {
        return this._request('POST', '/api/runtime/providers', this._payload(options));
    }

    async getPresence(options = {}) {
        return this._request('POST', '/api/runtime/presence', this._payload(options));
    }

    async getSocial(options = {}) {
        return this._request('POST', '/api/runtime/social', this._payload(options));
    }

    // Approvals

    async getApprovals(options = {}) {
        return this._request('POST', '/api/runtime/approvals', this._payload(options));
    }

    async applyApproval(approvalId, options = {}) {
        const payload = {
            ...this._payload(options),
            approval_id: approvalId
        };
        return this._request('POST', '/api/runtime/approvals/apply', payload);
    }

    async rejectApproval(approvalId, options = {}) {
        const payload = {
            ...this._payload(options),
            approval_id: approvalId
        };
        return this._request('POST', '/api/runtime/approvals/reject', payload);
    }

    // Chat

    async chat(message, options = {}) {
        const payload = {
            message,
            persona_id: options.personaId || 'default',
            user_id: options.userId || 'web_user',
            channel_id: options.channelId || 'web_chat'
        };
        return this._request('POST', '/chat', payload);
    }

    async sendEvent(text, kind = 'chat', options = {}) {
        const payload = {
            ...this._payload(options),
            text,
            kind,
            message_id: options.messageId || ''
        };
        return this._request('POST', '/api/runtime/event', payload);
    }

    // Personas

    async listPersonas() {
        return this._request('GET', '/personas');
    }

    async getPersona(personaId) {
        return this._request('GET', `/personas/${personaId}`);
    }

    // Social

    async setSocialMode(mode, options = {}) {
        const payload = {
            ...this._payload(options),
            social_mode: mode
        };
        return this._request('POST', '/api/runtime/social/mode', payload);
    }

    async resetSocial(options = {}) {
        return this._request('POST', '/api/runtime/social/reset', this._payload(options));
    }
}

// Export singleton
const api = new RuntimeAPI();
export default api;
