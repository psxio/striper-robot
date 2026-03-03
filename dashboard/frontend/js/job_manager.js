/**
 * Striper Robot Dashboard — Job Manager
 *
 * CRUD operations, job list rendering, and job execution controls.
 */

const JobManager = (() => {
    let jobs = [];

    function init() {
        refresh();
    }

    // ------------------------------------------------------------------ CRUD
    async function refresh() {
        try {
            jobs = await App.apiFetch('/api/jobs');
            renderList();
        } catch (_) {
            // Server not running — show empty
            jobs = [];
            renderList();
        }
    }

    function renderList() {
        const container = document.getElementById('job-list');
        if (!container) return;

        if (jobs.length === 0) {
            container.innerHTML = `
                <div class="card" style="text-align:center; color: var(--text-secondary);">
                    No jobs yet. Click <strong>+ New Job</strong> to get started.
                </div>`;
            return;
        }

        container.innerHTML = jobs.map(job => `
            <div class="card" data-job-id="${job.id}">
                <div class="card-header">
                    <h3>${escapeHtml(job.name)}</h3>
                    <span class="badge badge-${job.status}">${job.status}</span>
                </div>
                <div class="card-meta">
                    Created ${formatDate(job.created_at)} &middot; Updated ${formatDate(job.updated_at)}
                </div>
                <div class="card-actions">
                    ${actionButtons(job)}
                </div>
            </div>
        `).join('');
    }

    function actionButtons(job) {
        const btns = [];
        const s = job.status;
        if (s === 'pending' || s === 'ready' || s === 'paused') {
            btns.push(`<button class="btn btn-success btn-sm" onclick="JobManager.startJob(${job.id})">Start</button>`);
        }
        if (s === 'running') {
            btns.push(`<button class="btn btn-warning btn-sm" onclick="JobManager.pauseJob(${job.id})">Pause</button>`);
            btns.push(`<button class="btn btn-danger btn-sm" onclick="JobManager.stopJob(${job.id})">Stop</button>`);
        }
        if (s === 'pending' || s === 'ready') {
            btns.push(`<button class="btn btn-sm" onclick="JobManager.previewPaths(${job.id})">Preview</button>`);
        }
        btns.push(`<button class="btn btn-danger btn-sm" onclick="JobManager.deleteJob(${job.id})">Delete</button>`);
        return btns.join('');
    }

    async function startJob(id) {
        try {
            await App.apiFetch(`/api/jobs/${id}/start`, { method: 'POST' });
            App.toast('Job started', 'success');
            refresh();
        } catch (err) { App.toast(err.message, 'error'); }
    }

    async function pauseJob(id) {
        try {
            await App.apiFetch(`/api/jobs/${id}/pause`, { method: 'POST' });
            App.toast('Job paused', 'warning');
            refresh();
        } catch (err) { App.toast(err.message, 'error'); }
    }

    async function stopJob(id) {
        try {
            await App.apiFetch(`/api/jobs/${id}/stop`, { method: 'POST' });
            App.toast('Job stopped', 'info');
            refresh();
        } catch (err) { App.toast(err.message, 'error'); }
    }

    async function deleteJob(id) {
        if (!confirm('Delete this job?')) return;
        try {
            await App.apiFetch(`/api/jobs/${id}`, { method: 'DELETE' });
            App.toast('Job deleted', 'info');
            refresh();
        } catch (err) { App.toast(err.message, 'error'); }
    }

    async function previewPaths(id) {
        try {
            const geojson = await App.apiFetch(`/api/paths/preview/${id}`);
            if (typeof MapEditor !== 'undefined') {
                MapEditor.displayGeoJSON(geojson);
                App.navigateTo('map');
            }
        } catch (err) { App.toast(err.message, 'error'); }
    }

    // ------------------------------------------------------------------ Create modal
    function showCreateModal() {
        document.getElementById('modal-create-job').classList.add('active');
        document.getElementById('input-job-name').value = '';
        document.getElementById('input-job-template').value = '';
        document.getElementById('template-params').style.display = 'none';
        document.getElementById('file-upload-group').style.display = 'block';
    }

    function closeModal() {
        document.getElementById('modal-create-job').classList.remove('active');
    }

    async function createJob() {
        const name = document.getElementById('input-job-name').value.trim();
        if (!name) {
            App.toast('Job name is required', 'warning');
            return;
        }

        const templateType = document.getElementById('input-job-template').value;
        let pathData = null;

        // If a template is selected, generate it server-side with a default origin
        if (templateType) {
            const count = parseInt(document.getElementById('input-stall-count').value, 10) || 10;
            try {
                const tpl = await App.apiFetch('/api/paths/template', {
                    method: 'POST',
                    body: {
                        template_type: templateType,
                        origin: { lat: 30.2672, lng: -97.7431 },
                        count: count,
                    },
                });
                pathData = tpl.geojson;
            } catch (err) {
                App.toast('Template generation failed: ' + err.message, 'error');
                return;
            }
        } else {
            // Check for file upload
            const fileInput = document.getElementById('input-path-file');
            if (fileInput.files.length > 0) {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                try {
                    const uploadResp = await App.apiFetch('/api/paths/upload', {
                        method: 'POST',
                        body: formData,
                    });
                    pathData = uploadResp.geojson;
                } catch (err) {
                    App.toast('File upload failed: ' + err.message, 'error');
                    return;
                }
            }
        }

        try {
            await App.apiFetch('/api/jobs', {
                method: 'POST',
                body: { name, path_data: pathData },
            });
            App.toast('Job created', 'success');
            closeModal();
            refresh();
        } catch (err) {
            App.toast('Failed to create job: ' + err.message, 'error');
        }
    }

    // ------------------------------------------------------------------ Helpers
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatDate(iso) {
        if (!iso) return '--';
        const d = new Date(iso);
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // ------------------------------------------------------------------ Expose
    return {
        init,
        refresh,
        startJob,
        pauseJob,
        stopJob,
        deleteJob,
        previewPaths,
        showCreateModal,
        closeModal,
        createJob,
    };
})();
