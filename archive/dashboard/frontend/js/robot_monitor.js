/**
 * Striper Robot Dashboard — Robot Monitor
 *
 * Live status display, progress bars, and E-Stop control.
 */

const RobotMonitor = (() => {
    let estopped = false;

    function init() {
        // Fetch initial status
        App.apiFetch('/api/robot/status')
            .then(data => onStatus(data))
            .catch(() => { /* server may not be running yet */ });
    }

    function onStatus(s) {
        if (!s) return;

        // State
        const stateEl = document.getElementById('stat-state');
        if (stateEl) {
            stateEl.textContent = (s.state || '--').toUpperCase();
            stateEl.style.color = stateColor(s.state);
        }

        // Speed
        setText('stat-speed', s.speed != null ? s.speed.toFixed(1) : '0.0');

        // Heading
        setText('stat-heading', s.heading != null ? Math.round(s.heading) : '0');

        // GPS accuracy
        setText('stat-gps', s.gps_accuracy != null ? s.gps_accuracy.toFixed(3) : '--');

        // Battery
        const bat = s.battery != null ? s.battery : 0;
        document.getElementById('stat-battery').innerHTML = `${Math.round(bat)}<span class="unit">%</span>`;
        setBar('bar-battery', bat);

        // Paint
        const paint = s.paint_level != null ? s.paint_level : 0;
        document.getElementById('stat-paint').innerHTML = `${Math.round(paint)}<span class="unit">%</span>`;
        setBar('bar-paint', paint);

        // Job progress
        const prog = s.job_progress != null ? s.job_progress : 0;
        setText('stat-progress', Math.round(prog) + '%');
        const barProg = document.getElementById('bar-progress');
        if (barProg) barProg.style.width = prog + '%';

        // E-stop button state
        estopped = s.state === 'estopped';
        const btn = document.getElementById('estop-btn');
        if (btn) {
            btn.classList.toggle('estopped', estopped);
            btn.textContent = estopped ? 'RELEASE' : 'E-STOP';
        }
    }

    async function toggleEstop() {
        try {
            if (estopped) {
                await App.apiFetch('/api/robot/release-estop', { method: 'POST' });
            } else {
                await App.apiFetch('/api/robot/estop', { method: 'POST' });
            }
        } catch (err) {
            App.toast('E-Stop command failed: ' + err.message, 'error');
        }
    }

    // ---- Helpers ----
    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function setBar(id, pct) {
        const bar = document.getElementById(id);
        if (!bar) return;
        bar.style.width = pct + '%';
        bar.className = 'fill';
        if (pct < 20) bar.classList.add('low');
        else if (pct < 50) bar.classList.add('medium');
    }

    function stateColor(state) {
        const colors = {
            idle: '#8892a4',
            running: '#00d68f',
            paused: '#f0b429',
            estopped: '#ff3d71',
            error: '#ff3d71',
            disconnected: '#5a6478',
        };
        return colors[state] || '#e0e0e0';
    }

    return { init, onStatus, toggleEstop };
})();
