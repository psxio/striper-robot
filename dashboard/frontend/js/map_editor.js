/**
 * Striper Robot Dashboard — Map Editor (Leaflet.js)
 *
 * Satellite/OSM tile layer, drawing tools, parking templates,
 * paint-path display, real-time robot marker and trail.
 */

const MapEditor = (() => {
    let map = null;
    let robotMarker = null;
    let robotTrail = null;
    let trailCoords = [];
    let pathsLayer = null;
    let drawControl = null;
    let drawnItems = null;
    let placementMode = false;

    const DEFAULT_CENTER = [30.2672, -97.7431]; // Austin, TX
    const DEFAULT_ZOOM = 18;
    const MAX_TRAIL = 2000;

    // ------------------------------------------------------------------ Init
    function init() {
        if (map) return;

        map = L.map('map', {
            center: DEFAULT_CENTER,
            zoom: DEFAULT_ZOOM,
            zoomControl: true,
        });

        // Tile layers
        const osmTile = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 22,
            attribution: '&copy; OpenStreetMap contributors',
        });

        const satelliteTile = L.tileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 22,
            attribution: 'Tiles &copy; Esri',
        });

        // Default to satellite, allow toggle
        satelliteTile.addTo(map);
        L.control.layers({ 'Satellite': satelliteTile, 'Street': osmTile }, null, { position: 'bottomright' }).addTo(map);

        // Drawing layer
        drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        drawControl = new L.Control.Draw({
            position: 'topleft',
            draw: {
                polygon: { shapeOptions: { color: '#4a9eff', weight: 2 } },
                polyline: { shapeOptions: { color: '#00d68f', weight: 2 } },
                rectangle: { shapeOptions: { color: '#4a9eff', weight: 2 } },
                circle: false,
                circlemarker: false,
                marker: false,
            },
            edit: { featureGroup: drawnItems },
        });
        map.addControl(drawControl);

        map.on(L.Draw.Event.CREATED, (e) => {
            drawnItems.addLayer(e.layer);
        });

        // Paths overlay
        pathsLayer = L.featureGroup().addTo(map);

        // Robot marker
        const robotIcon = L.divIcon({
            className: 'robot-icon',
            html: `<div style="
                width:20px; height:20px;
                background: #4a9eff;
                border: 2px solid #fff;
                border-radius: 50% 50% 50% 0;
                transform: rotate(-45deg);
                box-shadow: 0 2px 6px rgba(0,0,0,0.5);
            "></div>`,
            iconSize: [20, 20],
            iconAnchor: [10, 10],
        });

        robotMarker = L.marker(DEFAULT_CENTER, { icon: robotIcon, rotationAngle: 0 }).addTo(map);
        robotTrail = L.polyline([], { color: '#4a9eff', weight: 2, opacity: 0.6 }).addTo(map);

        // Click handler for template placement
        map.on('click', onMapClick);
    }

    // ------------------------------------------------------------------ Robot
    function onRobotStatus(status) {
        if (!map || !status.position) return;
        const latlng = [status.position.lat, status.position.lng];
        robotMarker.setLatLng(latlng);

        // Heading rotation — Leaflet.RotatedMarker is optional, so we just
        // recreate the icon with a CSS rotation.
        if (status.heading !== undefined) {
            const angle = status.heading - 45; // offset for teardrop shape
            robotMarker.setIcon(L.divIcon({
                className: 'robot-icon',
                html: `<div style="
                    width:20px; height:20px;
                    background: #4a9eff;
                    border: 2px solid #fff;
                    border-radius: 50% 50% 50% 0;
                    transform: rotate(${angle}deg);
                    box-shadow: 0 2px 6px rgba(0,0,0,0.5);
                "></div>`,
                iconSize: [20, 20],
                iconAnchor: [10, 10],
            }));
        }

        // Trail
        if (status.state === 'running') {
            trailCoords.push(latlng);
            if (trailCoords.length > MAX_TRAIL) trailCoords.shift();
            robotTrail.setLatLngs(trailCoords);
        }
    }

    function centerOnRobot() {
        if (!map || !robotMarker) return;
        map.setView(robotMarker.getLatLng(), map.getZoom());
    }

    // ------------------------------------------------------------------ Paths
    function displayGeoJSON(geojson) {
        pathsLayer.clearLayers();
        if (!geojson || !geojson.features) return;

        L.geoJSON(geojson, {
            style: (feature) => ({
                color: (feature.properties && feature.properties.color) || '#FFFFFF',
                weight: 2,
                opacity: 0.85,
            }),
        }).addTo(pathsLayer);

        if (pathsLayer.getLayers().length > 0) {
            map.fitBounds(pathsLayer.getBounds().pad(0.2));
        }
    }

    function clearPaths() {
        pathsLayer.clearLayers();
        trailCoords = [];
        robotTrail.setLatLngs([]);
        App.toast('Paths cleared', 'info');
    }

    // ------------------------------------------------------------------ Templates
    function placeTemplate() {
        document.getElementById('modal-place-template').classList.add('active');
    }

    function cancelPlacement() {
        document.getElementById('modal-place-template').classList.remove('active');
        placementMode = false;
    }

    function startPlacement() {
        document.getElementById('modal-place-template').classList.remove('active');
        placementMode = true;
        App.toast('Click on the map to place the template', 'info');
    }

    function onTplTypeChange() {
        const type = document.getElementById('tpl-type').value;
        const isParking = ['standard','angled_60','angled_45','handicap','compact'].includes(type);
        const isArrow = type === 'arrow';
        const isCrosswalk = type === 'crosswalk';

        document.querySelectorAll('.tpl-parking-param').forEach(el => el.style.display = isParking ? '' : 'none');
        document.querySelectorAll('.tpl-arrow-param').forEach(el => el.style.display = isArrow ? '' : 'none');
        document.querySelectorAll('.tpl-crosswalk-param').forEach(el => el.style.display = isCrosswalk ? '' : 'none');
    }

    async function onMapClick(e) {
        if (!placementMode) return;
        placementMode = false;

        const templateType = document.getElementById('tpl-type').value;
        const count = parseInt(document.getElementById('tpl-count').value, 10) || 10;
        const angle = parseFloat(document.getElementById('tpl-angle').value) || 0;

        const body = {
            template_type: templateType,
            origin: { lat: e.latlng.lat, lng: e.latlng.lng },
            angle: angle,
            count: count,
        };

        // Add type-specific params
        if (templateType === 'arrow') {
            body.arrow_type = document.getElementById('tpl-arrow-type').value;
        } else if (templateType === 'crosswalk') {
            body.crosswalk_width_ft = parseFloat(document.getElementById('tpl-crosswalk-width').value) || 10;
            body.crosswalk_length_ft = parseFloat(document.getElementById('tpl-crosswalk-length').value) || 20;
        }

        try {
            const data = await App.apiFetch('/api/paths/template', {
                method: 'POST',
                body: body,
            });
            displayGeoJSON(data.geojson);
            App.toast(`Placed ${data.line_count} lines`, 'success');
        } catch (err) {
            App.toast('Failed to generate template: ' + err.message, 'error');
        }
    }

    // ------------------------------------------------------------------ Misc
    function invalidateSize() {
        if (map) map.invalidateSize();
    }

    // ------------------------------------------------------------------ Expose
    return {
        init,
        onRobotStatus,
        centerOnRobot,
        displayGeoJSON,
        clearPaths,
        placeTemplate,
        cancelPlacement,
        startPlacement,
        onTplTypeChange,
        invalidateSize,
    };
})();
