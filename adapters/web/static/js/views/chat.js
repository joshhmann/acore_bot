/**
 * Chat View
 * 
 * Main chat interface with persona selection.
 * Preserves all existing chat functionality.
 */

import api from '../api.js';

class ChatView {
    constructor() {
        this.isProcessing = false;
        this.personas = [];
        this.currentPersona = 'default';
        this.userId = 'web_user';
    }

    async mount() {
        const content = document.getElementById('content');
        content.innerHTML = this._render();

        // Cache DOM elements
        this.messagesEl = document.getElementById('chat-messages');
        this.inputEl = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('send-btn');
        this.personaSelect = document.getElementById('persona-select');
        this.userIdInput = document.getElementById('user-id');
        this.typingEl = document.getElementById('typing-indicator');

        // Bind events
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.inputEl.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });

        // Load personas
        await this.loadPersonas();

        // Focus input
        this.inputEl.focus();
    }

    unmount() {
        // Cleanup if needed
    }

    _render() {
        return `
            <div class="chat-container">
                <div class="chat-header">
                    <label>Persona:</label>
                    <select id="persona-select">
                        <option value="default">Loading...</option>
                    </select>
                    <label>User:</label>
                    <input type="text" id="user-id" value="web_user" placeholder="User ID">
                </div>
                
                <div class="chat-messages" id="chat-messages">
                    <div class="message bot">
                        <div class="author">System</div>
                        Welcome to Gestalt Framework! Select a persona and start chatting.
                    </div>
                </div>
                
                <div class="chat-input-area">
                    <input type="text" id="chat-input" placeholder="Type your message..." maxlength="1000">
                    <button id="send-btn" class="btn btn-primary">Send</button>
                </div>
                
                <div class="typing" id="typing-indicator">
                    <span class="spinner" style="width: 16px; height: 16px; margin-right: 8px;"></span>
                    Persona is typing...
                </div>
            </div>
        `;
    }

    async loadPersonas() {
        try {
            const data = await api.listPersonas();
            this.personas = data.personas || [];
            
            if (this.personas.length > 0) {
                this.personaSelect.innerHTML = this.personas.map(p => 
                    `<option value="${p.id}">${p.display_name}</option>`
                ).join('');
                this.currentPersona = this.personas[0].id;
            }
        } catch (error) {
            console.error('Failed to load personas:', error);
        }
    }

    addMessage(text, isUser, author = '') {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${isUser ? 'user' : 'bot'}`;
        
        if (author) {
            msgDiv.innerHTML = `<div class="author">${this.escapeHtml(author)}</div>${this.escapeHtml(text)}`;
        } else {
            msgDiv.textContent = text;
        }
        
        this.messagesEl.appendChild(msgDiv);
        this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async sendMessage() {
        const text = this.inputEl.value.trim();
        if (!text || this.isProcessing) return;

        this.isProcessing = true;
        this.sendBtn.disabled = true;
        this.inputEl.value = '';

        const personaId = this.personaSelect.value;
        const userId = this.userIdInput.value || 'web_user';

        this.addMessage(text, true, userId);
        this.typingEl.style.display = 'flex';

        try {
            const response = await api.chat(text, {
                personaId,
                userId
            });

            this.addMessage(response.response, false, response.persona_name);
        } catch (error) {
            console.error('Chat error:', error);
            this.addMessage(`Error: ${error.message}`, false, 'System');
        } finally {
            this.isProcessing = false;
            this.sendBtn.disabled = false;
            this.typingEl.style.display = 'none';
            this.inputEl.focus();
        }
    }
}

const chatView = new ChatView();
export default chatView;
