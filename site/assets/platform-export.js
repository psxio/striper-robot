/**
 * Export functions for lots: GeoJSON, waypoints, KML.
 * Mostly pure — depends on state for lot lookup and utils for download.
 * @module platform-export
 */

import { EARTH_RADIUS, WAYPOINT_SPACING_M } from './platform-state.js';
import { sanitizeFilename, downloadFile, showToast } from './platform-utils.js';

export function extractCoords(feature) {
  if (!feature || !feature.geometry) return null;
  var geom = feature.geometry;
  switch (geom.type) {
    case 'Point':
      return [[geom.coordinates[0], geom.coordinates[1]]];
    case 'LineString':
      return geom.coordinates.map(function(c) { return [c[0], c[1]]; });
    case 'Polygon':
      var ring = geom.coordinates[0];
      return ring.map(function(c) { return [c[0], c[1]]; });
    case 'MultiLineString':
      var all = [];
      geom.coordinates.forEach(function(line) {
        line.forEach(function(c) { all.push([c[0], c[1]]); });
      });
      return all;
    default:
      return null;
  }
}

export function distanceM(lat1, lon1, lat2, lon2) {
  var dLat = (lat2 - lat1) * Math.PI / 180;
  var dLon = (lon2 - lon1) * Math.PI / 180;
  var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
          Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
          Math.sin(dLon/2) * Math.sin(dLon/2);
  return EARTH_RADIUS * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

export function calcPolylineDistanceM(coords) {
  var dist = 0;
  for (var i = 1; i < coords.length; i++) {
    dist += distanceM(coords[i-1][1], coords[i-1][0], coords[i][1], coords[i][0]);
  }
  return dist;
}

export function interpolatePoints(coords, spacingM) {
  var result = [coords[0]];
  for (var i = 1; i < coords.length; i++) {
    var startLng = coords[i-1][0], startLat = coords[i-1][1];
    var endLng = coords[i][0], endLat = coords[i][1];
    var segDist = distanceM(startLat, startLng, endLat, endLng);
    if (segDist < spacingM) { result.push(coords[i]); continue; }
    var steps = Math.floor(segDist / spacingM);
    for (var s = 1; s <= steps; s++) {
      var frac = s / Math.ceil(segDist / spacingM);
      result.push([startLng + (endLng - startLng) * frac, startLat + (endLat - startLat) * frac]);
    }
    var lastPt = result[result.length - 1];
    if (distanceM(lastPt[1], lastPt[0], endLat, endLng) > 0.05) result.push(coords[i]);
  }
  return result;
}

function waypointLine(seq, frame, cmd, p1, p2, p3, p4, lat, lng, alt) {
  return seq + '\t0\t' + frame + '\t' + cmd + '\t' + p1 + '\t' + p2 + '\t' + p3 + '\t' + p4 + '\t' +
    lat.toFixed(8) + '\t' + lng.toFixed(8) + '\t' + alt.toFixed(6) + '\t1';
}

/**
 * Find a lot for export. Caller must pass lots array and activeLotId.
 * @param {Array} lots
 * @param {string|null} activeLotId
 * @param {string} [lotId]
 */
export function getLotForExport(lots, activeLotId, lotId) {
  var lot = lots.find(function(l) { return l.id === (lotId || activeLotId); });
  if (!lot) { showToast('No lot selected', 'error'); return null; }
  if (!lot.features || !lot.features.length) { showToast('Lot has no features', 'error'); return null; }
  return lot;
}

export function exportGeojsonForLot(lots, activeLotId, lotId, filenameSuffix) {
  var lot = getLotForExport(lots, activeLotId, lotId);
  if (!lot) return;
  var geojson = {
    type: 'FeatureCollection',
    features: lot.features,
    properties: { name: lot.name, center: lot.center, zoom: lot.zoom, exported: new Date().toISOString() }
  };
  var filename = sanitizeFilename(lot.name) + (filenameSuffix || '') + '.geojson';
  downloadFile(filename, JSON.stringify(geojson, null, 2), 'application/geo+json');
  showToast('GeoJSON exported');
}

export function exportWaypointsForLot(lots, activeLotId, lotId, filenameSuffix) {
  var lot = getLotForExport(lots, activeLotId, lotId);
  if (!lot) return;
  var lines = ['QGC WPL 110'];
  var seq = 0;

  var firstCoords = null;
  for (var fi = 0; fi < lot.features.length; fi++) {
    firstCoords = extractCoords(lot.features[fi]);
    if (firstCoords && firstCoords.length >= 1) break;
  }
  if (!firstCoords) { showToast('No valid features to export', 'error'); return; }

  lines.push(waypointLine(seq++, 0, 16, 0, 0, 0, 0, firstCoords[0][1], firstCoords[0][0], 0));

  lot.features.forEach(function(feature) {
    var coords = extractCoords(feature);
    if (!coords || coords.length < 2) return;
    var interpolated = interpolatePoints(coords, WAYPOINT_SPACING_M);

    // Sprayer on
    if (interpolated.length > 0) {
      lines.push(waypointLine(seq++, 3, 183, 1, 0, 0, 0, interpolated[0][1], interpolated[0][0], 0));
    }
    interpolated.forEach(function(pt) {
      lines.push(waypointLine(seq++, 3, 16, 0, 0, 0, 0, pt[1], pt[0], 0));
    });
    // Sprayer off
    if (interpolated.length > 0) {
      var last = interpolated[interpolated.length - 1];
      lines.push(waypointLine(seq++, 3, 183, 0, 0, 0, 0, last[1], last[0], 0));
    }
  });

  var content = lines.join('\n') + '\n';
  var filename = sanitizeFilename(lot.name) + (filenameSuffix || '') + '.waypoints';
  downloadFile(filename, content, 'text/plain');
  showToast('Waypoints exported (' + seq + ' points)');
}

export async function exportKmlForLot(lots, activeLotId, lotId, filenameSuffix) {
  var lot = getLotForExport(lots, activeLotId, lotId);
  if (!lot) return;
  var placemarks = lot.features.map(function(feature) {
    var coords = extractCoords(feature);
    if (!coords || coords.length < 2) return '';
    var coordStr = coords.map(function(c) { return c[0] + ',' + c[1] + ',0'; }).join(' ');
    var props = feature.properties || {};
    return '<Placemark><name>' + (props.lineType || 'Line') + '</name><LineString><coordinates>' + coordStr + '</coordinates></LineString></Placemark>';
  }).join('\n    ');

  var kml = '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n  <name>' +
    lot.name + '</name>\n    ' + placemarks + '\n</Document>\n</kml>';
  var filename = sanitizeFilename(lot.name) + (filenameSuffix || '') + '.kml';
  downloadFile(filename, kml, 'application/vnd.google-earth.kml+xml');
  showToast('KML exported');
}

export function closeExportDropdown() {
  var dropdown = document.getElementById('exportDropdown');
  if (dropdown) dropdown.classList.remove('visible');
}
