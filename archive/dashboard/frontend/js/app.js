/**
 * Striper Robot Dashboard — Main Application
 *
 * Manages view routing, WebSocket connection, global state, and notifications.
 */

const App = (() => {
    // ------------------------------------------------------------------ State
    const state = {
        currentView: 'map',
        wsConnected: false,
        robotStatus: null,
    };

    let ws = null;
    let wsReconnectTimer = null;
    const WS_RECONNECT_MS = 3000;

    // API base — same origin when served by FastAPI
    const API = window.location.origin;

    // ------------------------------------------------------------------ Init
    function init() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => navigateTo(item.dataset.view));
        });

        // Template select toggle in create-job modal
        const tplSelect = document.getElementById('input-job-template');
        if (tplSelect) {
            tplSelect.addEventListener('change', () => {
                const params = document.getElementById('template-params');
                const fileGroup = document.getElementById('file-upload-group');
                if (tplSelect.value) {
                    params.style.display = 'block';
                    fileGroup.style.display = 'none';
                } else {
                    params.style.display = 'none';
                    fileGroup.style.display = 'block';
                }
            });
        }

        connectWebSocket();

        // Initialize sub-modules once DOM is ready
        setTimeout(() => {
            if (typeof MapEditor !== 'undefined') MapEditor.init();
            if (typeof RobotMonitor !== 'undefined') RobotMonitor.init();
            if (typeof JobManager !== 'undefined') JobManager.init();
        }, 100);
    }

    // ------------------------------------------------------------------ Views
    function navigateTo(view) {
        state.currentView = view;
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

        const viewEl = document.getElementById('view-' + view);
        const navEl = document.querySelector(`.nav-item[data-view="${view}"]`);
        if (viewEl) viewEl.classList.add('active');
        if (navEl) navEl.classList.add('active');

        // Leaflet needs a resize nudge when shown
        if (view === 'map' && typeof MapEditor !== 'undefined') {
            setTimeout(() => MapEditor.invalidateSize(), 50);
        }
    }

    // ------------------------------------------------------------------ WebSocket
    function connectWebSocket() {
        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const url = `${proto}://${window.location.host}/ws`;
        setConnectionStatus('connecting');

        try {
            ws = new WebSocket(url);
        } catch (_) {
            scheduleReconnect();
            return;
        }

        ws.onopen = () => {
            state.wsConnected = true;
            setConnectionStatus('connected');
            if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleWsMessage(msg);
            } catch (_) { /* ignore non-JSON */ }
        };

        ws.onclose = () => {
            state.wsConnected = false;
            setConnectionStatus('disconnected');
            scheduleReconnect();
        };

        ws.onerror = () => {
            state.wsConnected = false;
            setConnectionStatus('disconnected');
        };
    }

    function scheduleReconnect() {
        if (wsReconnectTimer) return;
        wsReconnectTimer = setTimeout(() => {
            wsReconnectTimer = null;
            connectWebSocket();
        }, WS_RECONNECT_MS);
    }

    function setConnectionStatus(status) {
        const dot = document.getElementById('ws-dot');
        const label = document.getElementById('ws-label');
        dot.className = 'dot';
        if (status === 'connected') {
            dot.classList.add('connected');
            label.textContent = 'Connected';
        } else if (status === 'connecting') {
            dot.classList.add('connecting');
            label.textContent = 'Connecting...';
        } else {
            label.textContent = 'Disconnected';
        }
    }

    function handleWsMessage(msg) {
        if (msg.event === 'status' && msg.data) {
            state.robotStatus = msg.data;
            if (typeof RobotMonitor !== 'undefined') RobotMonitor.onStatus(msg.data);
            if (typeof MapEditor !== 'undefined') MapEditor.onRobotStatus(msg.data);
        } else if (msg.event === 'job_completed') {
            toast('Job completed', 'success');
            if (typeof JobManager !== 'undefined') JobManager.refresh();
        } else if (msg.event === 'job_started') {
            toast('Job started', 'info');
        } else if (msg.event === 'estop_activated') {
            toast('E-STOP ACTIVATED', 'error');
        } else if (msg.event === 'estop_released') {
            toast('E-Stop released', 'warning');
        }
    }

    // ------------------------------------------------------------------ API helper
    async function apiFetch(path, options = {}) {
        const url = API + path;
        const defaults = { headers: { 'Content-Type': 'application/json' } };
        const opts = { ...defaults, ...options };
        if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
            opts.body = JSON.stringify(opts.body);
        }
        if (opts.body instanceof FormData) {
            delete opts.headers['Content-Type'];  // let browser set multipart boundary
        }
        const resp = await fetch(url, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || resp.statusText);
        }
        return resp.json();
    }

    // ------------------------------------------------------------------ Toasts
    function toast(message, type = 'info', durationMs = 4000) {
        const container = document.getElementById('toast-container');
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = message;
        container.appendChild(el);
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.3s';
            setTimeout(() => el.remove(), 300);
        }, durationMs);
    }

    // ------------------------------------------------------------------ Expose
    document.addEventListener('DOMContentLoaded', init);

    return {
        state,
        navigateTo,
        apiFetch,
        toast,
    };
})();
