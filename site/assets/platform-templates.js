/**
 * Template generators for parking rows, handicap spaces, crosswalks, and arrows.
 * Pure geometry — no DOM or map dependencies.
 * @module platform-templates
 */

import { uid } from './platform-utils.js';
import { LINE_TYPES } from './platform-state.js';

export function localToGeo(originLat, originLon, x, y) {
  return {
    lat: originLat + y / 110540,
    lon: originLon + x / (111320 * Math.cos(originLat * Math.PI / 180))
  };
}

export function rotatePoint(x, y, angleDeg) {
  var rad = angleDeg * Math.PI / 180;
  return {
    x: x * Math.cos(rad) - y * Math.sin(rad),
    y: x * Math.sin(rad) + y * Math.cos(rad)
  };
}

export function makeTemplateFeature(coords, lineType, color, groupId) {
  return {
    type: 'Feature',
    geometry: { type: 'LineString', coordinates: coords },
    properties: {
      id: uid(), type: lineType, lineType: LINE_TYPES[lineType] ? LINE_TYPES[lineType].label : lineType,
      color: color, width: 4, notes: '', geometryType: 'polyline', groupId: groupId,
      created: new Date().toISOString()
    }
  };
}

export function generateParkingRow(originLat, originLon, angle, count, spacing, length) {
  var groupId = 'row_' + uid();
  var features = [];
  for (var i = 0; i <= count; i++) {
    var localX = i * spacing;
    var bot = rotatePoint(localX, 0, angle);
    var top = rotatePoint(localX, length, angle);
    var p1 = localToGeo(originLat, originLon, bot.x, bot.y);
    var p2 = localToGeo(originLat, originLon, top.x, top.y);
    features.push({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[p1.lon, p1.lat], [p2.lon, p2.lat]] },
      properties: {
        id: uid(), type: 'standard', lineType: 'Standard', color: '#ffffff',
        width: 4, notes: '', geometryType: 'polyline', groupId: groupId,
        created: new Date().toISOString()
      }
    });
  }
  return { features: features, groupId: groupId };
}

export function generateHandicapSpace(originLat, originLon, angle) {
  var groupId = 'hc_' + uid();
  var features = [];
  var width = 3.6, length = 5.5, aisleX = width * 0.6, color = '#58a6ff';

  var b1 = rotatePoint(0, 0, angle), t1 = rotatePoint(0, length, angle);
  var p1 = localToGeo(originLat, originLon, b1.x, b1.y), p2 = localToGeo(originLat, originLon, t1.x, t1.y);
  features.push(makeTemplateFeature([[p1.lon, p1.lat], [p2.lon, p2.lat]], 'handicap', color, groupId));

  var b2 = rotatePoint(width, 0, angle), t2 = rotatePoint(width, length, angle);
  var p3 = localToGeo(originLat, originLon, b2.x, b2.y), p4 = localToGeo(originLat, originLon, t2.x, t2.y);
  features.push(makeTemplateFeature([[p3.lon, p3.lat], [p4.lon, p4.lat]], 'handicap', color, groupId));

  var b3 = rotatePoint(aisleX, 0, angle), t3 = rotatePoint(aisleX, length, angle);
  var p5 = localToGeo(originLat, originLon, b3.x, b3.y), p6 = localToGeo(originLat, originLon, t3.x, t3.y);
  features.push(makeTemplateFeature([[p5.lon, p5.lat], [p6.lon, p6.lat]], 'handicap', color, groupId));

  var hatchSpacing = 0.6;
  for (var y = hatchSpacing; y < length; y += hatchSpacing) {
    var hl = rotatePoint(aisleX, y, angle), hr = rotatePoint(width, y, angle);
    var hp1 = localToGeo(originLat, originLon, hl.x, hl.y), hp2 = localToGeo(originLat, originLon, hr.x, hr.y);
    features.push(makeTemplateFeature([[hp1.lon, hp1.lat], [hp2.lon, hp2.lat]], 'handicap', color, groupId));
  }
  return { features: features, groupId: groupId };
}

export function generateCrosswalk(originLat, originLon, angle, cwWidth, cwLength) {
  var groupId = 'cw_' + uid();
  var features = [];
  var stripeWidth = 0.3, gap = 0.3, x = 0;
  while (x + stripeWidth <= cwWidth + 0.001) {
    var cx = x + stripeWidth / 2;
    var bot = rotatePoint(cx, 0, angle), top = rotatePoint(cx, cwLength, angle);
    var p1 = localToGeo(originLat, originLon, bot.x, bot.y), p2 = localToGeo(originLat, originLon, top.x, top.y);
    features.push(makeTemplateFeature([[p1.lon, p1.lat], [p2.lon, p2.lat]], 'crosswalk', '#ffffff', groupId));
    x += stripeWidth + gap;
  }
  return { features: features, groupId: groupId };
}

export var ARROW_TEMPLATES = {
  straight: [[[0,0],[0,2.0]],[[-0.4,1.4],[0,2.0]],[[0.4,1.4],[0,2.0]]],
  left: [[[0,0],[0,1.2],[-0.8,1.2]],[[-0.4,0.8],[-0.8,1.2]],[[-0.4,1.6],[-0.8,1.2]]],
  right: [[[0,0],[0,1.2],[0.8,1.2]],[[0.4,0.8],[0.8,1.2]],[[0.4,1.6],[0.8,1.2]]],
  u_turn: [[[0,0],[0,1.5]],[[0,1.5],[0.3,1.8],[0.6,1.5]],[[0.6,1.5],[0.6,0.6]],[[0.2,1.0],[0.6,0.6]],[[1.0,1.0],[0.6,0.6]]]
};

export function generateArrow(originLat, originLon, angle, arrowType) {
  var groupId = 'arrow_' + uid();
  var features = [];
  var template = ARROW_TEMPLATES[arrowType] || ARROW_TEMPLATES.straight;
  template.forEach(function(polyline) {
    var coords = polyline.map(function(pt) {
      var rot = rotatePoint(pt[0], pt[1], angle);
      var geo = localToGeo(originLat, originLon, rot.x, rot.y);
      return [geo.lon, geo.lat];
    });
    features.push(makeTemplateFeature(coords, 'standard', '#ffffff', groupId));
  });
  return { features: features, groupId: groupId };
}
