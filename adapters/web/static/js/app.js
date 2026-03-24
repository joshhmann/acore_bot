/**
 * Gestalt Operator Dashboard App
 * 
 * Main application entry point.
 * Initializes router, registers views, and starts the app.
 */

import router from './router.js';
import dashboardView from './views/dashboard.js';
import chatView from './views/chat.js';
import sessionsView from './views/sessions.js';
import tracesView from './views/traces.js';
import contextView from './views/context.js';
import toolsView from './views/tools.js';
import approvalsView from './views/approvals.js';

// Icon definitions for sidebar
const ICONS = {
    dashboard: '📊',
    chat: '💬',
    sessions: '📋',
    traces: '🔍',
    context: '💾',
    tools: '🔧',
    approvals: '⏳'
};

/**
 * Initialize the application
 */
function init() {
    renderLayout();
    registerRoutes();
    setupNavigation();
}

/**
 * Render the main layout structure
 */
function renderLayout() {
    document.body.innerHTML = `
        <div class="app-container">
            <aside class="sidebar">
                <div class="sidebar-header">
                    <h1>🎭 Gestalt</h1>
                    <p>Operator Dashboard</p>
                </div>
                
                <nav class="sidebar-nav">
                    <div class="nav-section">
                        <div class="nav-section-title">Overview</div>
                        <a href="#/" class="nav-item" data-route="/">
                            <span class="icon">${ICONS.dashboard}</span>
                            <span>Dashboard</span>
                        </a>
                        <a href="#/chat" class="nav-item" data-route="/chat">
                            <span class="icon">${ICONS.chat}</span>
                            <span>Chat</span>
                        </a>
                    </div>
                    
                    <div class="nav-section">
                        <div class="nav-section-title">Runtime</div>
                        <a href="#/sessions" class="nav-item" data-route="/sessions">
                            <span class="icon">${ICONS.sessions}</span>
                            <span>Sessions</span>
                        </a>
                        <a href="#/traces" class="nav-item" data-route="/traces">
                            <span class="icon">${ICONS.traces}</span>
                            <span>Traces</span>
                        </a>
                        <a href="#/context" class="nav-item" data-route="/context">
                            <span class="icon">${ICONS.context}</span>
                            <span>Context Cache</span>
                        </a>
                        <a href="#/tools" class="nav-item" data-route="/tools">
                            <span class="icon">${ICONS.tools}</span>
                            <span>Tools</span>
                        </a>
                    </div>
                    
                    <div class="nav-section">
                        <div class="nav-section-title">Operations</div>
                        <a href="#/approvals" class="nav-item" data-route="/approvals">
                            <span class="icon">${ICONS.approvals}</span>
                            <span>Approvals</span>
                        </a>
                    </div>
                </nav>
                
                <div class="sidebar-footer">
                    <div>Runtime-first UI</div>
                    <div style="font-size: 11px; opacity: 0.7;">v1.0.0</div>
                </div>
            </aside>
            
            <main class="main-content">
                <header class="header">
                    <div class="header-left">
                        <h1 class="header-title" id="page-title">Dashboard</h1>
                    </div>
                    <div class="header-right">
                        <span class="runtime-badge">Runtime Active</span>
                    </div>
                </header>
                
                <div class="content" id="content">
                    <div class="loading">
                        <div class="spinner"></div>
                        Loading...
                    </div>
                </div>
            </main>
        </div>
    `;
}

/**
 * Register all routes with the router
 */
function registerRoutes() {
    router.registerAll({
        '/': dashboardView,
        '/chat': chatView,
        '/sessions': sessionsView,
        '/traces': tracesView,
        '/context': contextView,
        '/tools': toolsView,
        '/approvals': approvalsView
    });

    // Update page title on route change
    router.afterEach((to) => {
        updatePageTitle(to.path);
    });
}

/**
 * Update the page title based on current route
 */
function updatePageTitle(path) {
    const titles = {
        '/': 'Dashboard',
        '/chat': 'Chat',
        '/sessions': 'Sessions',
        '/traces': 'Traces',
        '/context': 'Context Cache',
        '/tools': 'Tools',
        '/approvals': 'Approvals'
    };

    const title = titles[path] || 'Gestalt';
    document.getElementById('page-title').textContent = title;
    document.title = `${title} - Gestalt Operator`;
}

/**
 * Setup navigation event handlers
 */
function setupNavigation() {
    // Handle nav item clicks
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            // Update active state immediately for responsiveness
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
        });
    });

    // Mobile menu toggle (if needed in future)
    // For now, sidebar is always visible on desktop
}

// Start the app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
