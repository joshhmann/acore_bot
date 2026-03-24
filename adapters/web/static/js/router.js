/**
 * Simple Hash Router
 * 
 * Provides client-side navigation using URL hash fragments.
 * Each view has mount() and unmount() lifecycle methods.
 */

class Router {
    constructor() {
        this.routes = new Map();
        this.currentView = null;
        this.beforeHooks = [];
        this.afterHooks = [];
        
        // Listen for hash changes
        window.addEventListener('hashchange', () => this._handleRoute());
        
        // Handle initial route on DOM ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this._handleRoute());
        } else {
            this._handleRoute();
        }
    }

    /**
     * Register a route
     * @param {string} path - Route path (e.g., '/chat', '/sessions')
     * @param {Object} view - View object with mount(), unmount() methods
     */
    register(path, view) {
        this.routes.set(path, view);
        return this;
    }

    /**
     * Register multiple routes
     * @param {Object} routes - Map of path -> view
     */
    registerAll(routes) {
        Object.entries(routes).forEach(([path, view]) => {
            this.register(path, view);
        });
        return this;
    }

    /**
     * Add navigation guard (runs before route change)
     * @param {Function} hook - Async function receiving (to, from)
     */
    beforeEach(hook) {
        this.beforeHooks.push(hook);
        return this;
    }

    /**
     * Add post-navigation hook
     * @param {Function} hook - Function receiving (to, from)
     */
    afterEach(hook) {
        this.afterHooks.push(hook);
        return this;
    }

    /**
     * Navigate to a route
     * @param {string} path - Route path
     */
    navigate(path) {
        window.location.hash = path;
    }

    /**
     * Get current route path
     */
    get currentPath() {
        const hash = window.location.hash.slice(1) || '/';
        return hash.split('?')[0];
    }

    /**
     * Get current query params
     */
    get queryParams() {
        const hash = window.location.hash.slice(1) || '/';
        const queryIndex = hash.indexOf('?');
        
        if (queryIndex === -1) return {};
        
        const queryString = hash.slice(queryIndex + 1);
        const params = {};
        
        queryString.split('&').forEach(pair => {
            const [key, value] = pair.split('=').map(decodeURIComponent);
            params[key] = value;
        });
        
        return params;
    }

    /**
     * Handle route change
     */
    async _handleRoute() {
        const path = this.currentPath;
        const view = this.routes.get(path) || this.routes.get('*') || this.routes.get('/');
        
        if (!view) {
            console.error(`No route found for: ${path}`);
            return;
        }

        const from = this.currentView;
        const to = { path, view };

        // Run before hooks
        for (const hook of this.beforeHooks) {
            const result = await hook(to, from);
            if (result === false) return; // Cancel navigation
        }

        // Unmount current view
        if (this.currentView && this.currentView.view.unmount) {
            try {
                await this.currentView.view.unmount();
            } catch (error) {
                console.error('Error unmounting view:', error);
            }
        }

        // Mount new view
        this.currentView = to;
        
        if (view.mount) {
            try {
                await view.mount();
            } catch (error) {
                console.error('Error mounting view:', error);
                this._showError(error);
            }
        }

        // Update active nav state
        this._updateNavState(path);

        // Run after hooks
        for (const hook of this.afterHooks) {
            try {
                hook(to, from);
            } catch (error) {
                console.error('Error in after hook:', error);
            }
        }
    }

    /**
     * Update active state in navigation
     */
    _updateNavState(path) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.getAttribute('href') === `#${path}`) {
                item.classList.add('active');
            }
        });
    }

    /**
     * Show error in content area
     */
    _showError(error) {
        const content = document.getElementById('content');
        if (content) {
            content.innerHTML = `
                <div class="error-message">
                    <strong>Error loading view:</strong> ${error.message}
                </div>
            `;
        }
    }
}

// Export singleton
const router = new Router();
export default router;
