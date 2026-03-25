/**
 * Shared mutable state for the Strype platform.
 * All modules import this and read/write directly.
 * @module platform-state
 */

export const LINE_TYPES = {
  standard:  { label: 'Standard',  color: '#ffffff', dash: null },
  handicap:  { label: 'Handicap',  color: '#58a6ff', dash: null },
  fire_lane: { label: 'Fire Lane', color: '#f85149', dash: null },
  no_parking:{ label: 'No Parking', color: '#d29922', dash: null },
  crosswalk: { label: 'Crosswalk', color: '#ffffff', dash: '10, 8' }
};

export const STORAGE_KEYS = {
  lots: 'strype_lots',
  jobs: 'strype_jobs',
  activeLot: 'strype_active_lot',
  mapState: 'strype_map_state'
};

export const WAYPOINT_SPACING_M = 0.5;
export const SPRAY_SPEED = 0.5;
export const TRANSIT_SPEED = 1.0;
export const EARTH_RADIUS = 6378137;

/** @type {{ lots: Array, jobs: Array, currentUser: object|null, organizations: Array, activeOrganizationId: string, organizationSites: Array, organizationQuotes: Array, organizationWorkOrders: Array, organizationScans: Array, organizationSimulations: Array, activeLotId: string|null, activeTool: string, selectedFeatureId: string|null, map: object|null, drawnItems: object|null, currentDrawHandler: object|null, streetLayer: object|null, satelliteLayer: object|null, currentMapStyle: string, robotStatusRefreshTimer: number|null, undoStack: Array, redoStack: Array, placementMode: object|null, measurePoints: Array, measureLayers: Array, measureLabels: Array, _refreshTimerId: number|null, _telemetryPollerId: number|null, _currentRobotId: string|null }} */
export const S = {
  lots: [],
  jobs: [],
  currentUser: null,
  organizations: [],
  activeOrganizationId: '',
  organizationSites: [],
  organizationQuotes: [],
  organizationWorkOrders: [],
  organizationScans: [],
  organizationSimulations: [],
  activeLotId: null,
  activeTool: 'pan',
  selectedFeatureId: null,
  map: null,
  drawnItems: null,
  currentDrawHandler: null,
  streetLayer: null,
  satelliteLayer: null,
  currentMapStyle: 'street',
  robotStatusRefreshTimer: null,
  undoStack: [],
  redoStack: [],
  UNDO_MAX: 50,
  placementMode: null,
  measurePoints: [],
  measureLayers: [],
  measureLabels: [],
  _refreshTimerId: null,
  _telemetryPollerId: null,
  _currentRobotId: null,
};
