import { useEffect, useRef, useState, useMemo } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { PFZZone } from './ChatPanel';
import { useMarineContext, type MarineLocation, FIELD_OVERLAY_KEYS } from '../context/MarineContext';
import { INDIAN_LANDING_CENTRES } from '../data/landingCentres';
import { INCOIS_COASTAL_ALERTS_GEOJSON } from '../data/incoisCoastalAlerts';
import { geocodeLocation, getApiUrl } from '../api/client';
import {
  Layers,
  Wind,
  Waves,
  Thermometer,
  Compass,
  Search,
  Plus,
  Minus,
  MapPin,
  AlertTriangle,
  ShieldAlert,
  ArrowUpRight,
  X,
  Fish,
  Leaf,
  Users,
  ShieldX,
  Crosshair,
  Loader2,
} from 'lucide-react';
import { getDevicePosition } from '../utils/nativeLocation';
import { sendMarineAlert } from '../utils/nativeNotifications';

interface Props {
  bbox: [number, number, number, number];
  activeLayer?: string;
  center?: [number, number];
  pfzZones: PFZZone[];
  onLocationSelect: (location: MarineLocation) => void;
  onZoneSelect: (zone: PFZZone) => void;
}


const LAYER_GROUP_MAP: Record<string, string[]> = {
  sst: ['sst-heat'],
  wind: ['wind-fill'],
  chlorophyll: ['chl-fill'],
  currents: ['currents-fill'],
  waves: ['waves-fill'],
  fishing: ['fishing-crowding'],
  pfz: ['pfz-fill', 'pfz-line'],
  geofence: ['imbl-glow', 'imbl-lines', 'defense-fill', 'defense-line'],
  sustainability: ['mpa-fill', 'mpa-line'],
};

// Exact INCOIS Ocean State Forecast Significant Wave Height Color Palette
const INCOIS_WAVE_STOPS: Array<[number, string]> = [
  [0, '#80cbc4'],
  [0.5, '#4dd0e1'],
  [1.0, '#29b6f6'],
  [1.5, '#3f51b5'],
  [2.0, '#ab47bc'],
  [2.5, '#e91e63'],
  [3.0, '#ad1457'],
  [4.0, '#c2185b'],
  [5.0, '#d32f2f'],
  [7.0, '#8d6e63'],
  [10.0, '#bdbdbd'],
  [12.0, '#616161'],
];

// Exact INCOIS Wind Speed (m/s) Color Palette matching Screenshot 1
const INCOIS_WIND_STOPS: Array<[number, string]> = [
  [0, '#5c6bc0'],
  [6, '#26a69a'],
  [12, '#66bb6a'],
  [16, '#c0ca33'],
  [18, '#8d6e63'],
  [20, '#b71c1c'],
];

const CURRENT_STOPS: Array<[number, string]> = [
  [0, '#1e3a8a'],
  [0.15, '#2563eb'],
  [0.3, '#0891b2'],
  [0.45, '#22c55e'],
  [0.6, '#f59e0b'],
  [0.75, '#dc2626'],
];

// Display metadata used by the data-cell click popups
const OVERLAY_META: Record<string, { label: string; icon: string; unit: string; decimals: number; color: string }> = {
  'wind-fill': { label: 'Wind Speed', icon: '🌀', unit: 'm/s', decimals: 1, color: '#0369a1' },
  'waves-fill': { label: 'Significant Wave Height', icon: '🌊', unit: 'm', decimals: 2, color: '#0e7490' },
  'sst-heat': { label: 'Sea Surface Temperature', icon: '🌡️', unit: '°C', decimals: 1, color: '#b45309' },
  'chl-fill': { label: 'Chlorophyll-a', icon: '🧪', unit: 'mg/m³', decimals: 2, color: '#15803d' },
  'currents-fill': { label: 'Ocean Current Speed', icon: '➤', unit: 'm/s', decimals: 2, color: '#4f46e5' },
};

function degToCompass(deg: number): string {
  const dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  return dirs[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16];
}

// Convert point grid to seamless polygon grid cells
const toGridCells = (fc: any): any => {
  const feats = fc?.features;
  if (!feats?.length) return fc;
  const lons = Array.from(new Set<number>(feats.map((f: any) => f.geometry.coordinates[0] as number))).sort((a, b) => a - b);
  const lats = Array.from(new Set<number>(feats.map((f: any) => f.geometry.coordinates[1] as number))).sort((a, b) => a - b);
  const step = (arr: number[], fallback: number) => {
    let min = Infinity;
    if (arr.length >= 2) {
      for (let i = 1; i < arr.length; i++) {
        const d = arr[i] - arr[i - 1];
        if (d > 1e-6) min = Math.min(min, d);
      }
    }
    return min === Infinity ? fallback : min;
  };
  const dx = Math.min(step(lons, 0.25), 1.0);
  const dy = Math.min(step(lats, 0.25), 1.0);
  const hx = (dx * 0.5) * 1.08;
  const hy = (dy * 0.5) * 1.08;
  return {
    type: 'FeatureCollection',
    features: feats.map((f: any) => {
      const [lon, lat] = f.geometry.coordinates;
      return {
        ...f,
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [lon - hx, lat - hy],
            [lon + hx, lat - hy],
            [lon + hx, lat + hy],
            [lon - hx, lat + hy],
            [lon - hx, lat - hy],
          ]],
        },
      };
    }),
  };
};

export default function MapView({ center, pfzZones, onLocationSelect, onZoneSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const searchMarker = useRef<maplibregl.Marker | null>(null);
  const vesselMarker = useRef<maplibregl.Marker | null>(null);
  const routeStartMarker = useRef<maplibregl.Marker | null>(null);
  const routeEndMarker = useRef<maplibregl.Marker | null>(null);
  const landingCentreMarkers = useRef<maplibregl.Marker[]>([]);
  const pfzMarkers = useRef<maplibregl.Marker[]>([]);
  const restrictedMarkers = useRef<maplibregl.Marker[]>([]);

  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [showLayerMenu, setShowLayerMenu] = useState(false);
  const mapLoadedRef = useRef(false);

  const onLocationSelectRef = useRef(onLocationSelect);
  onLocationSelectRef.current = onLocationSelect;
  const onZoneSelectRef = useRef(onZoneSelect);
  onZoneSelectRef.current = onZoneSelect;

  const {
    operationalMode,
    setOperationalMode,
    landingCentre,
    setLandingCentre,
    layers,
    setLayers,
    zones,
    currentRoute,
    routeOrigin,
    routeDestination,
    setRouteDestination,
    isPickingDestinationOnMap,
    setIsPickingDestinationOnMap,
    activeRouteType,
    geofenceStatus,
    borderAlertMessage,
    minBorderDistanceKm,
    closestBorderName,
    safeReturnHeadingDeg,
    dismissBorderAlert,
    setDismissBorderAlert,
    checkGeofence,
  } = useMarineContext();

  const [locating, setLocating] = useState(false);

  // Send native local notification when critical border breach is detected
  useEffect(() => {
    if (geofenceStatus === 'CRITICAL' && !dismissBorderAlert) {
      sendMarineAlert({
        title: '⚠️ CRITICAL MARITIME BORDER ALERT',
        body: borderAlertMessage || `Approaching ${closestBorderName || 'Restricted Maritime Boundary'}. Steer safe heading immediately!`,
      });
    }
  }, [geofenceStatus, dismissBorderAlert, borderAlertMessage, closestBorderName]);

  const handleLocateMe = async () => {
    try {
      setLocating(true);
      const coords = await getDevicePosition();
      if (map.current) {
        map.current.flyTo({
          center: [coords.longitude, coords.latitude],
          zoom: 11,
          essential: true,
        });
      }
      onLocationSelectRef.current({
        name: 'Vessel Live Position',
        lat: coords.latitude,
        lon: coords.longitude,
        environment: 'COASTAL',
      });
      checkGeofence(coords.latitude, coords.longitude);
    } catch (err) {
      console.warn('GPS Locate failed:', err);
    } finally {
      setLocating(false);
    }
  };

  // Mirror pick-mode in a ref so the one-time map setup can read the live value
  // without re-running (and destroying) the whole map when the flag toggles.
  const isPickingDestinationRef = useRef(isPickingDestinationOnMap);
  isPickingDestinationRef.current = isPickingDestinationOnMap;

  const layersRef = useRef(layers);
  layersRef.current = layers;

  // Apply layer visibility on state change. Field overlays (wind/waves/SST/chl/currents)
  // are full-area fills — showing more than one stacks colors into an unreadable mix,
  // so only the FIRST selected field overlay is ever visible (radio behaviour).
  const applyLayerVisibility = () => {
    const instance = map.current;
    if (!instance || !instance.isStyleLoaded()) return;
    const FIELD_ORDER = ['wind', 'waves', 'sst', 'chlorophyll', 'currents'];
    const activeField = FIELD_ORDER.find((k) => layersRef.current.includes(k)) ?? null;
    for (const [layerKey, layerIds] of Object.entries(LAYER_GROUP_MAP)) {
      const isField = FIELD_ORDER.includes(layerKey);
      const visible = isField
        ? layerKey === activeField
        : layersRef.current.includes(layerKey);
      for (const layerId of layerIds) {
        try {
          if (instance.getLayer(layerId)) {
            instance.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
          }
        } catch {}
      }
    }

    const showGeofenceMarkers = layersRef.current.includes('geofence') || layersRef.current.includes('sustainability');
    restrictedMarkers.current.forEach((mk) => {
      const el = mk.getElement();
      if (el) {
        el.style.display = showGeofenceMarkers ? 'block' : 'none';
      }
    });
  };


  // Zoom controls
  const handleZoomIn = () => map.current?.zoomIn();
  const handleZoomOut = () => map.current?.zoomOut();

  // Initialize MapLibre GL with Esri World Topography Basemap
  useEffect(() => {
    if (!container.current) return;

    // Initial center centered on India & Indian Ocean as in screenshots
    const initialCenter = center || [78.5, 14.8];

    const instance = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {
          esriTopo: {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
            attribution: 'Tiles © Esri – Source: Esri',
          },
        },
        layers: [
          {
            id: 'esri-topo-layer',
            type: 'raster',
            source: 'esriTopo',
          },
        ],
      },
      center: initialCenter,
      zoom: 5.6,
      attributionControl: false, // Customized attribution displayed in bottom bar
    });

    // Click handler on map
    instance.on('click', (event) => {
      const lat = parseFloat(event.lngLat.lat.toFixed(4));
      const lon = parseFloat(event.lngLat.lng.toFixed(4));

      if (isPickingDestinationRef.current) {
        setRouteDestination({
          name: `Custom Sea Waypoint (${lat}°N, ${lon}°E)`,
          lat,
          lon,
        });
        setIsPickingDestinationOnMap(false);
        setOperationalMode('ROUTE');

        new maplibregl.Popup({ closeButton: true, className: 'orca-popup' })
          .setLngLat(event.lngLat)
          .setHTML(`
            <div style="color:#0f172a;font-family:sans-serif;padding:6px;min-width:180px;">
              <strong style="color:#0284c7;font-size:12px;">🎯 Destination Set</strong><br/>
              <div style="font-size:11px;margin-top:2px;">Lat: <b>${lat}°</b> | Lon: <b>${lon}°</b></div>
              <div style="font-size:10px;color:#16a34a;margin-top:3px;">Ready for Space-Time Route calculation</div>
            </div>
          `)
          .addTo(instance);
        return;
      }

      // A click on a colored data cell or INCOIS alert is handled by that layer's own
      // popup handler (shows the measured value); don't also fire the generic popup.
      const interactiveLayers = [
        'wind-fill',
        'waves-fill',
        'sst-heat',
        'chl-fill',
        'currents-fill',
        'offshore-alert-fill',
        'offshore-alert-line',
        'coastal-ribbon-line',
        'pfz-fill',
        'defense-fill',
        'mpa-fill',
        'imbl-lines',
        'route-primary-line',
        'route-alt-line',
        'route-waypoints',
      ];
      if (instance.queryRenderedFeatures(event.point, { layers: interactiveLayers }).length > 0) {
        return;
      }

      const point: MarineLocation = {
        name: `Lat ${lat}°, Lon ${lon}°`,
        lat,
        lon,
      };

      onLocationSelectRef.current(point);
      checkGeofence(lat, lon);

      new maplibregl.Popup({ closeButton: true, className: 'orca-popup' })
        .setLngLat(event.lngLat)
        .setHTML(`
          <div style="color:#0f172a;font-family:sans-serif;padding:6px;min-width:180px;">
            <strong style="color:#0284c7;font-size:12px;">📍 Maritime Coordinates</strong>
            <div style="font-size:11px;margin-top:2px;">Lat: <b>${lat}°</b> | Lon: <b>${lon}°</b></div>
            <div style="margin-top:4px;font-size:10px;color:#16a34a;font-weight:bold;">INCOIS & Geofence Telemetry Active</div>
          </div>
        `)
        .addTo(instance);
    });

    // Load data layers when style is loaded
    instance.on('load', async () => {
      mapLoadedRef.current = true;
      const m = map.current;
      if (!m) return;

      const colorExpr = (stops: Array<[number, string]>, valueExpr?: any): any =>
        ['interpolate', ['linear'], valueExpr ?? ['get', 'value'], ...stops.flatMap(([v, c]) => [v, c])];

      const addOverlayLayer = async (cfg: {
        source: string;
        layer: string;
        url: string;
        stops: Array<[number, string]>;
        opacity?: number;
        valueExpr?: any;
      }) => {
        if (m.getSource(cfg.source)) return;
        try {
          const res = await fetch(cfg.url);
          if (!res.ok) return;
          const data = await res.json();
          if (!data.features?.length || m.getSource(cfg.source)) return;

          // Convert point observation array to seamless box grid cells (box shape)
          m.addSource(cfg.source, { type: 'geojson', data: toGridCells(data) });

          m.addLayer({
            id: cfg.layer,
            type: 'fill',
            source: cfg.source,
            paint: {
              'fill-color': colorExpr(cfg.stops, cfg.valueExpr),
              'fill-opacity': cfg.opacity ?? 0.78,
              'fill-antialias': false,
            },
          });

          // Clicking a colored data cell shows its value; hovering shows a pointer.
          m.on('click', cfg.layer, (e: any) => showCellPopup(e, cfg.layer));
          m.on('mousemove', cfg.layer, () => {
            m.getCanvas().style.cursor = 'pointer';
          });
          m.on('mouseleave', cfg.layer, () => {
            m.getCanvas().style.cursor = '';
          });

          applyLayerVisibility();
        } catch (e) {
          console.warn(`Overlay ${cfg.layer} failed:`, e);
        }
      };

      const showCellPopup = (e: any, layerId: string) => {
        const props = e.features?.[0]?.properties;
        const meta = OVERLAY_META[layerId];
        if (!props || !meta) return;
        const raw = Number(props.value);
        const shown = Number.isFinite(raw) ? Math.abs(raw).toFixed(meta.decimals) : '—';
        const qualityPct = props.quality != null ? Math.round(Number(props.quality) * 100) : null;
        const ts =
          typeof props.timestamp === 'string' && props.timestamp ? props.timestamp.slice(0, 10) : '';
        const source = props.source ? String(props.source) : '';
        const dirDeg = props.wind_direction_deg ?? props.current_direction_deg;
        const dirRow =
          dirDeg != null
            ? `<div style="margin-top:2px;">🧭 From ${degToCompass(Number(dirDeg))} (${Math.round(Number(dirDeg))}°)</div>`
            : '';
        const demoChip = props.is_demo
          ? `<span style="display:inline-block;margin-left:6px;vertical-align:middle;font-size:9px;font-weight:700;padding:1px 6px;border-radius:4px;background:#fbbf24;color:#78350f;">SIMULATED DATA</span>`
          : '';
        new maplibregl.Popup({ closeButton: true, className: 'orca-popup' })
          .setLngLat(e.lngLat)
          .setHTML(`
            <div style="color:#0f172a;font-family:sans-serif;padding:6px;min-width:210px;max-width:270px;">
              <div style="font-size:12px;font-weight:800;color:#0f172a;display:flex;align-items:center;flex-wrap:wrap;">
                <span style="margin-right:6px;">${meta.icon}</span>${meta.label}${demoChip}
              </div>
              <div style="font-size:20px;font-weight:800;color:${meta.color};margin:4px 0 2px;">
                ${shown} <span style="font-size:11px;font-weight:600;color:#64748b;">${meta.unit}</span>
              </div>
              <div style="font-size:10px;color:#475569;line-height:1.6;">
                ${dirRow}
                <div>📍 ${e.lngLat.lat.toFixed(3)}°N, ${e.lngLat.lng.toFixed(3)}°E</div>
                ${ts ? `<div>🕒 ${ts}</div>` : ''}
                ${qualityPct != null ? `<div>${props.is_demo ? 'Simulation confidence' : 'Data quality'}: ${qualityPct}%</div>` : ''}
                ${source ? `<div>📡 Source: ${source}</div>` : ''}
              </div>
            </div>
          `)
          .addTo(m);
      };

      const b = m.getBounds();
      const vw = b.getWest().toFixed(2);
      const vs = b.getSouth().toFixed(2);
      const ve = b.getEast().toFixed(2);
      const vn = b.getNorth().toFixed(2);
      const base = getApiUrl('/api/v1/map/data');
      const q = `?west=${vw}&south=${vs}&east=${ve}&north=${vn}`;

      await Promise.allSettled([
        addOverlayLayer({
          source: 'wind-source',
          layer: 'wind-fill',
          url: `${base}/wind${q}`,
          stops: INCOIS_WIND_STOPS,
          opacity: 0.82,
        }),
        addOverlayLayer({
          source: 'waves-source',
          layer: 'waves-fill',
          url: `${base}/waves${q}`,
          stops: INCOIS_WAVE_STOPS,
          opacity: 0.82,
        }),
        addOverlayLayer({
          source: 'sst-source',
          layer: 'sst-heat',
          url: `${base}/sst${q}`,
          stops: [
            [22, '#313695'],
            [24, '#4575b4'],
            [26, '#74add1'],
            [28, '#fee090'],
            [29.5, '#fdae61'],
            [31, '#f46d43'],
            [33, '#d73027'],
          ],
          opacity: 0.78,
        }),
        addOverlayLayer({
          source: 'chl-source',
          layer: 'chl-fill',
          url: `${base}/chlorophyll${q}`,
          stops: [
            [0.1, '#f0f9e8'],
            [0.4, '#ccebc5'],
            [0.8, '#a8ddb5'],
            [1.5, '#4eb3d3'],
            [3, '#2b8cbe'],
            [6, '#0868ac'],
          ],
          opacity: 0.78,
        }),
        addOverlayLayer({
          source: 'currents-source',
          layer: 'currents-fill',
          url: `${base}/currents${q}`,
          stops: CURRENT_STOPS as any,
          valueExpr: ['abs', ['get', 'value']],
          opacity: 0.65,
        }),
      ]);

      // 2. INCOIS Coastal Threat Warning Ribbons & Alert Polygons (Matching Screenshot 2)
      if (!m.getSource('incois-coastal-alerts')) {
        m.addSource('incois-coastal-alerts', {
          type: 'geojson',
          data: INCOIS_COASTAL_ALERTS_GEOJSON,
        });

        // Offshore Alert Polygons Fill
        m.addLayer({
          id: 'offshore-alert-fill',
          type: 'fill',
          source: 'incois-coastal-alerts',
          filter: ['==', '$type', 'Polygon'],
          paint: {
            'fill-color': [
              'match',
              ['get', 'threatLevel'],
              'WARNING', '#e53935',
              'ALERT', '#fb8c00',
              'WATCH', '#fdd835',
              'NO_THREAT', '#43a047',
              '#fb8c00',
            ],
            'fill-opacity': 0.72,
          },
        });

        // Offshore Alert Polygons Outline
        m.addLayer({
          id: 'offshore-alert-line',
          type: 'line',
          source: 'incois-coastal-alerts',
          filter: ['==', '$type', 'Polygon'],
          paint: {
            'line-color': '#fef08a',
            'line-width': 2,
            'line-dasharray': [2, 1.5],
          },
        });

        // Coastal Ribbon Outer Glow
        m.addLayer({
          id: 'coastal-ribbon-glow',
          type: 'line',
          source: 'incois-coastal-alerts',
          filter: ['==', '$type', 'LineString'],
          paint: {
            'line-color': [
              'match',
              ['get', 'threatLevel'],
              'WARNING', '#e53935',
              'ALERT', '#fb8c00',
              'WATCH', '#fdd835',
              'NO_THREAT', '#43a047',
              '#fb8c00',
            ],
            'line-width': 7.5,
            'line-opacity': 0.4,
          },
        });

        // Coastal Ribbon Core Line
        m.addLayer({
          id: 'coastal-ribbon-line',
          type: 'line',
          source: 'incois-coastal-alerts',
          filter: ['==', '$type', 'LineString'],
          paint: {
            'line-color': [
              'match',
              ['get', 'threatLevel'],
              'WARNING', '#e53935',
              'ALERT', '#fb8c00',
              'WATCH', '#fdd835',
              'NO_THREAT', '#43a047',
              '#fb8c00',
            ],
            'line-width': 4.0,
          },
        });

        // Interactive Click on Coastal Ribbons & Offshore Polygons
        const handleAlertClick = (e: any) => {
          const props = e.features?.[0]?.properties;
          if (!props) return;
          const threatColor =
            props.threatLevel === 'WARNING'
              ? '#e53935'
              : props.threatLevel === 'ALERT'
              ? '#fb8c00'
              : props.threatLevel === 'WATCH'
              ? '#fdd835'
              : '#43a047';

          new maplibregl.Popup({ closeButton: true, className: 'orca-popup' })
            .setLngLat(e.lngLat)
            .setHTML(`
              <div style="color:#0f172a;font-family:sans-serif;padding:6px;max-width:260px;">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
                  <strong style="color:#0f172a;font-size:12px;">${props.name}</strong>
                  <span style="font-size:10px;font-weight:bold;padding:2px 6px;border-radius:4px;background:${threatColor};color:white;">
                    ${props.threatLevel}
                  </span>
                </div>
                <div style="font-size:11px;margin-top:4px;color:#334155;">
                  • <b>Wave Height:</b> ${props.waveHeightRange}<br/>
                  • <b>Swell Height:</b> ${props.swellHeightRange}<br/>
                  • <b>Wind Speed:</b> ${props.windSpeedRange}
                </div>
                <div style="font-size:10px;color:#475569;margin-top:4px;border-top:1px solid #e2e8f0;padding-top:4px;">
                  ${props.advisory}
                </div>
              </div>
            `)
            .addTo(m);
        };

        m.on('click', 'coastal-ribbon-line', handleAlertClick);
        m.on('click', 'offshore-alert-fill', handleAlertClick);
      }

      // 3. Load Geofence / IMBL Boundaries & Restricted Zones
      try {
        const res = await fetch(getApiUrl('/api/v1/map/geofence'));
        if (res.ok) {
          const data = await res.json();
          if (!m.getSource('geofence')) {
            m.addSource('geofence', { type: 'geojson', data });

            // 1. IMBL Outer Glow & Core Line
            m.addLayer({
              id: 'imbl-glow',
              type: 'line',
              source: 'geofence',
              filter: ['==', ['get', 'category'], 'IMBL'],
              paint: {
                'line-color': '#ef4444',
                'line-width': 10,
                'line-opacity': 0.35,
              },
            });

            m.addLayer({
              id: 'imbl-lines',
              type: 'line',
              source: 'geofence',
              filter: ['==', ['get', 'category'], 'IMBL'],
              paint: {
                'line-color': '#ef4444',
                'line-width': 3.5,
                'line-dasharray': [2, 1.5],
              },
            });

            // 2. Defense, Rocket Testing & High-Risk Security Zones
            m.addLayer({
              id: 'defense-fill',
              type: 'fill',
              source: 'geofence',
              filter: ['==', ['get', 'category'], 'DEFENSE_RESTRICTED'],
              paint: {
                'fill-color': '#dc2626',
                'fill-opacity': 0.35,
              },
            });

            m.addLayer({
              id: 'defense-line',
              type: 'line',
              source: 'geofence',
              filter: ['==', ['get', 'category'], 'DEFENSE_RESTRICTED'],
              paint: {
                'line-color': '#b91c1c',
                'line-width': 2.5,
                'line-dasharray': [3, 2],
              },
            });

            // 3. Marine Protected Areas (MPAs) & Spawning Sanctuaries
            m.addLayer({
              id: 'mpa-fill',
              type: 'fill',
              source: 'geofence',
              filter: ['==', ['get', 'category'], 'MPA'],
              paint: {
                'fill-color': '#059669',
                'fill-opacity': 0.28,
              },
            });

            m.addLayer({
              id: 'mpa-line',
              type: 'line',
              source: 'geofence',
              filter: ['==', ['get', 'category'], 'MPA'],
              paint: {
                'line-color': '#047857',
                'line-width': 2.0,
                'line-dasharray': [2, 2],
              },
            });

            // Interactive Click handler for restricted zones
            const handleRestrictedZoneClick = (e: any) => {
              const props = e.features?.[0]?.properties;
              if (!props) return;
              const isDefense = props.category === 'DEFENSE_RESTRICTED';
              const isImbl = props.category === 'IMBL' || props.zone_type === 'BORDER';
              const badgeColor = isDefense ? '#dc2626' : isImbl ? '#ef4444' : '#059669';
              const icon = props.icon || (isDefense ? '⛔' : isImbl ? '🚨' : '🛡️');
              const categoryLabel = isDefense
                ? 'DEFENSE / SECURITY EXCLUSION'
                : isImbl
                ? 'SOVEREIGN MARITIME BORDER'
                : 'MARINE PROTECTED AREA';

              new maplibregl.Popup({ closeButton: true, className: 'orca-popup' })
                .setLngLat(e.lngLat)
                .setHTML(`
                  <div style="color:#0f172a;font-family:sans-serif;padding:6px;max-width:280px;">
                    <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
                      <div style="font-size:10px;font-weight:bold;padding:2px 6px;border-radius:4px;background:${badgeColor};color:white;">
                        ${icon} ${categoryLabel}
                      </div>
                      ${props.radius_km ? `<span style="font-size:10px;font-weight:600;color:#64748b;">${props.radius_km} km radius</span>` : ''}
                    </div>
                    <div style="font-size:13px;font-weight:800;color:#0f172a;margin-top:6px;">
                      ${props.name}
                    </div>
                    <div style="font-size:11px;color:#334155;margin-top:4px;line-height:1.4;">
                      ${props.description || ''}
                    </div>
                    ${props.legal_warning ? `
                      <div style="font-size:10px;color:#b91c1c;background:#fee2e2;border:1px solid #fca5a5;padding:4px 6px;border-radius:6px;margin-top:6px;font-weight:600;">
                        ⚠️ ${props.legal_warning}
                      </div>
                    ` : ''}
                    <div style="font-size:10px;color:#64748b;margin-top:6px;border-top:1px solid #e2e8f0;padding-top:4px;">
                      📍 Center: ${props.center_lat ? `${Number(props.center_lat).toFixed(2)}°N, ${Number(props.center_lon).toFixed(2)}°E` : `${e.lngLat.lat.toFixed(2)}°N, ${e.lngLat.lng.toFixed(2)}°E`}
                    </div>
                  </div>
                `)
                .addTo(m);
            };

            m.on('click', 'defense-fill', handleRestrictedZoneClick);
            m.on('click', 'mpa-fill', handleRestrictedZoneClick);
            m.on('click', 'imbl-lines', handleRestrictedZoneClick);

            m.on('mousemove', 'defense-fill', () => { m.getCanvas().style.cursor = 'pointer'; });
            m.on('mouseleave', 'defense-fill', () => { m.getCanvas().style.cursor = ''; });
            m.on('mousemove', 'mpa-fill', () => { m.getCanvas().style.cursor = 'pointer'; });
            m.on('mouseleave', 'mpa-fill', () => { m.getCanvas().style.cursor = ''; });
            m.on('mousemove', 'imbl-lines', () => { m.getCanvas().style.cursor = 'pointer'; });
            m.on('mouseleave', 'imbl-lines', () => { m.getCanvas().style.cursor = ''; });

            // Create center badge pins for restricted zones
            restrictedMarkers.current.forEach((mk) => mk.remove());
            restrictedMarkers.current = [];

            (data.features || []).forEach((feat: any) => {
              const p = feat.properties;
              if (p && p.center_lat && p.center_lon) {
                const isDef = p.category === 'DEFENSE_RESTRICTED';
                const isIm = p.category === 'IMBL' || p.zone_type === 'BORDER';
                const borderColor = isDef ? '#dc2626' : isIm ? '#ef4444' : '#10b981';
                const icon = p.icon || (isDef ? '⛔' : isIm ? '🚨' : '🛡️');
                const title = p.short_name || p.name;

                const el = document.createElement('div');
                el.className = 'restricted-zone-badge cursor-pointer select-none';
                el.innerHTML = `
                  <div style="background:rgba(15,23,42,0.92);border:2px solid ${borderColor};color:white;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:700;display:flex;align-items:center;gap:4px;box-shadow:0 3px 10px rgba(0,0,0,0.5);transform:translate(-50%,-50%);white-space:nowrap;backdrop-filter:blur(4px);">
                    <span>${icon}</span>
                    <span>${title}</span>
                  </div>
                `;

                el.addEventListener('click', (ev) => {
                  ev.stopPropagation();
                  m.flyTo({ center: [p.center_lon, p.center_lat], zoom: 8.5 });
                  new maplibregl.Popup({ closeButton: true, className: 'orca-popup' })
                    .setLngLat([p.center_lon, p.center_lat])
                    .setHTML(`
                      <div style="color:#0f172a;font-family:sans-serif;padding:6px;max-width:280px;">
                        <div style="font-size:10px;font-weight:bold;padding:2px 6px;border-radius:4px;background:${borderColor};color:white;display:inline-block;">
                          ${icon} ${isDef ? 'DEFENSE RESTRICTED ZONE' : isIm ? 'INTERNATIONAL BORDER' : 'MARINE PROTECTED AREA'}
                        </div>
                        <div style="font-size:13px;font-weight:800;color:#0f172a;margin-top:6px;">
                          ${p.name}
                        </div>
                        <div style="font-size:11px;color:#334155;margin-top:4px;line-height:1.4;">
                          ${p.description || ''}
                        </div>
                        ${p.legal_warning ? `
                          <div style="font-size:10px;color:#b91c1c;background:#fee2e2;border:1px solid #fca5a5;padding:4px 6px;border-radius:6px;margin-top:6px;font-weight:600;">
                            ⚠️ ${p.legal_warning}
                          </div>
                        ` : ''}
                      </div>
                    `)
                    .addTo(m);
                });

                const marker = new maplibregl.Marker({ element: el })
                  .setLngLat([p.center_lon, p.center_lat])
                  .addTo(m);

                restrictedMarkers.current.push(marker);
              }
            });
          }
        }
      } catch (err) {
        console.warn('Geofence load error:', err);
      }

      applyLayerVisibility();
    });

    map.current = instance;
    (window as any).__orcaMap = instance;
    return () => instance.remove();
    // The map is created exactly once. Destination picking is read via
    // isPickingDestinationRef, so toggling it must not recreate the map (which
    // would wipe every overlay source and refetch all layers).
  }, []);

  // Update center when prop changes
  useEffect(() => {
    if (!map.current || !center) return;
    map.current.flyTo({ center, zoom: 7.5, essential: true });

    searchMarker.current?.remove();
    searchMarker.current = new maplibregl.Marker({ color: '#06b6d4' })
      .setLngLat(center)
      .addTo(map.current);
  }, [center]);

  // Layer visibility synchronization
  useEffect(() => {
    applyLayerVisibility();
  }, [layers, operationalMode]);

  // Fish Landing Centre Markers
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    landingCentreMarkers.current.forEach((m) => m.remove());
    landingCentreMarkers.current = [];

    INDIAN_LANDING_CENTRES.forEach((centre) => {
      const isSelected = landingCentre.id === centre.id;
      const el = document.createElement('div');
      el.className = 'flc-marker cursor-pointer';
      el.innerHTML = `
        <div style="position:relative;display:flex;align-items:center;justify-content:center;">
          <div style="width:${isSelected ? '22px' : '14px'};height:${isSelected ? '22px' : '14px'};border-radius:50%;background:${isSelected ? '#0284c7' : '#0369a1'};border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;color:white;font-size:9px;">
            ⚓
          </div>
        </div>
      `;

      el.addEventListener('click', () => {
        setLandingCentre(centre);
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([centre.lon, centre.lat])
        .addTo(instance);

      landingCentreMarkers.current.push(marker);
    });
  }, [landingCentre]);

  // ── PFZ Candidate Zones Layer & Interactive Markers ──
  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const activeZoneList = zones && zones.length > 0 ? zones : pfzZones || [];

    const updatePFZ = () => {
      if (!m.isStyleLoaded()) return;

      const features: any[] = [];
      activeZoneList.forEach((z, idx) => {
        if (z.geometry) {
          features.push({
            type: 'Feature',
            geometry: z.geometry,
            properties: {
              ...z,
              option_label: z.option_label || String.fromCharCode(65 + idx),
              option_title: z.option_title || `Sector ${idx + 1}`,
              crowding_level: z.crowding_level || 'LOW',
            },
          });
        }
      });

      const pfzGeoJSON: GeoJSON.FeatureCollection = {
        type: 'FeatureCollection',
        features,
      };

      if (!m.getSource('pfz-source')) {
        m.addSource('pfz-source', { type: 'geojson', data: pfzGeoJSON });
      } else {
        (m.getSource('pfz-source') as maplibregl.GeoJSONSource).setData(pfzGeoJSON);
      }

      if (!m.getLayer('pfz-fill')) {
        m.addLayer({
          id: 'pfz-fill',
          type: 'fill',
          source: 'pfz-source',
          paint: {
            'fill-color': [
              'match',
              ['get', 'option_label'],
              'A', '#10b981',
              'B', '#06b6d4',
              'C', '#f59e0b',
              '#10b981',
            ],
            'fill-opacity': 0.38,
            'fill-antialias': true,
          },
        });

        m.on('click', 'pfz-fill', (e: any) => {
          const props = e.features?.[0]?.properties;
          if (!props) return;
          const zoneId = props.zone_id;
          const label = props.option_label ? `Option ${props.option_label}` : zoneId;
          const title = props.option_title || zoneId;
          const crowd = props.crowding_level || 'LOW';
          const crowdColor = crowd === 'LOW' ? '#10b981' : crowd === 'MODERATE' ? '#f59e0b' : '#ef4444';
          const scorePct = Math.round((Number(props.score) || 0.8) * 100);

          const matchedZone = activeZoneList.find((z) => z.zone_id === zoneId);
          if (matchedZone) {
            onZoneSelectRef.current(matchedZone);
          }

          const popupContent = document.createElement('div');
          popupContent.className = 'orca-popup-content text-slate-900 font-sans p-1 min-w-[240px]';
          popupContent.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;border-bottom:1px solid #e2e8f0;padding-bottom:6px;margin-bottom:6px;">
              <div style="font-weight:800;font-size:13px;color:#0f172a;display:flex;align-items:center;gap:4px;">
                <span>🐟</span> <span>${label}</span>
              </div>
              <span style="font-size:10px;font-weight:700;padding:2px 6px;border-radius:9999px;background:${crowdColor}20;color:${crowdColor};border:1px solid ${crowdColor}40;">
                ${crowd} CROWDING
              </span>
            </div>
            <div style="font-size:11px;font-weight:600;color:#334155;margin-bottom:6px;">
              ${title}
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:10px;background:#f8fafc;padding:6px;border-radius:8px;margin-bottom:8px;">
              <div><b>Confidence:</b> ${scorePct}%</div>
              <div><b>Class:</b> ${props.classification || 'HIGH'}</div>
              <div><b>SST:</b> ${props.avg_sst ?? '28.2'}°C</div>
              <div><b>Chlorophyll:</b> ${props.avg_chlorophyll ?? '1.4'} mg/m³</div>
              <div><b>Fleet Density:</b> ${props.vessel_density ?? '0.4'}/km²</div>
              <div><b>Distance:</b> ~${props.distance_km ?? '16'} km</div>
            </div>
            <button id="pfz-route-btn-${zoneId}" style="width:100%;padding:6px 8px;border-radius:8px;background:#0284c7;color:white;font-weight:700;font-size:11px;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;">
              <span>🧭</span> <span>Plot Safe Route to this Zone</span>
            </button>
          `;

          const popup = new maplibregl.Popup({ closeButton: true, className: 'orca-popup' })
            .setLngLat(e.lngLat)
            .setDOMContent(popupContent)
            .addTo(m);

          const btn = popupContent.querySelector(`#pfz-route-btn-${zoneId}`);
          if (btn) {
            btn.addEventListener('click', () => {
              const lat = Number(props.center_lat) || e.lngLat.lat;
              const lon = Number(props.center_lon) || e.lngLat.lng;
              setRouteDestination({
                name: `PFZ ${label}`,
                lat,
                lon,
              });
              setOperationalMode('ROUTE');
              popup.remove();
            });
          }
        });

        m.on('mousemove', 'pfz-fill', () => {
          m.getCanvas().style.cursor = 'pointer';
        });
        m.on('mouseleave', 'pfz-fill', () => {
          m.getCanvas().style.cursor = '';
        });
      }

      if (!m.getLayer('pfz-line')) {
        m.addLayer({
          id: 'pfz-line',
          type: 'line',
          source: 'pfz-source',
          paint: {
            'line-color': [
              'match',
              ['get', 'option_label'],
              'A', '#059669',
              'B', '#0891b2',
              'C', '#d97706',
              '#059669',
            ],
            'line-width': 2.5,
            'line-dasharray': [2, 1.5],
          },
        });
      }

      // Sync badges at the center of each PFZ zone
      pfzMarkers.current.forEach((mk) => mk.remove());
      pfzMarkers.current = [];

      activeZoneList.forEach((z, idx) => {
        const label = z.option_label || String.fromCharCode(65 + idx);
        const crowdDot = z.crowding_level === 'LOW' ? '🟢' : z.crowding_level === 'MODERATE' ? '🟡' : '🔴';
        const isRecommended = idx === 0;

        const el = document.createElement('div');
        el.className = 'pfz-zone-badge cursor-pointer';
        el.innerHTML = `
          <div style="background:rgba(15,23,42,0.92);border:${isRecommended ? '2px solid #10b981' : '2px solid #06b6d4'};color:white;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:800;display:flex;align-items:center;gap:4px;box-shadow:0 3px 10px rgba(0,0,0,0.5);transform:translate(-50%,-50%);white-space:nowrap;">
            <span>🐟</span>
            <span>Option ${label}</span>
            <span>${crowdDot}</span>
          </div>
        `;

        el.addEventListener('click', (e) => {
          e.stopPropagation();
          onZoneSelectRef.current(z);
          m.flyTo({ center: [z.center_lon, z.center_lat], zoom: 8.5 });
        });

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([z.center_lon, z.center_lat])
          .addTo(m);

        pfzMarkers.current.push(marker);
      });

      applyLayerVisibility();
    };

    if (m.isStyleLoaded()) {
      updatePFZ();
    } else {
      m.once('load', updatePFZ);
    }
  }, [zones, pfzZones]);

  // ── Space-Time Optimal Route Synchronization ──
  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const updateRoute = () => {
      if (!m.isStyleLoaded()) return;

      const primaryGeoJSON = currentRoute?.geojson || { type: 'FeatureCollection', features: [] };
      const altGeoJSON = currentRoute?.alternative_geojson || { type: 'FeatureCollection', features: [] };

      const waypointFeatures: GeoJSON.Feature[] = (currentRoute?.waypoints || []).map((wp) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'Point' as const,
          coordinates: [wp.lon, wp.lat],
        },
        properties: {
          ...wp,
        },
      }));

      const waypointsGeoJSON: GeoJSON.FeatureCollection = {
        type: 'FeatureCollection',
        features: waypointFeatures,
      };

      // Sources
      if (!m.getSource('route-primary-source')) {
        m.addSource('route-primary-source', { type: 'geojson', data: primaryGeoJSON });
      } else {
        (m.getSource('route-primary-source') as maplibregl.GeoJSONSource).setData(primaryGeoJSON);
      }

      if (!m.getSource('route-alt-source')) {
        m.addSource('route-alt-source', { type: 'geojson', data: altGeoJSON });
      } else {
        (m.getSource('route-alt-source') as maplibregl.GeoJSONSource).setData(altGeoJSON);
      }

      if (!m.getSource('route-waypoints-source')) {
        m.addSource('route-waypoints-source', { type: 'geojson', data: waypointsGeoJSON });
      } else {
        (m.getSource('route-waypoints-source') as maplibregl.GeoJSONSource).setData(waypointsGeoJSON);
      }

      // Layers
      if (!m.getLayer('route-primary-glow')) {
        m.addLayer({
          id: 'route-primary-glow',
          type: 'line',
          source: 'route-primary-source',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#06b6d4',
            'line-width': 12,
            'line-opacity': 0.35,
          },
        });
      }

      if (!m.getLayer('route-primary-line')) {
        m.addLayer({
          id: 'route-primary-line',
          type: 'line',
          source: 'route-primary-source',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#0284c7',
            'line-width': 5.5,
            'line-opacity': 0.95,
          },
        });
      }

      if (!m.getLayer('route-alt-line')) {
        m.addLayer({
          id: 'route-alt-line',
          type: 'line',
          source: 'route-alt-source',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#f59e0b',
            'line-width': 3.5,
            'line-dasharray': [3, 2],
            'line-opacity': 0.8,
          },
        });
      }

      if (!m.getLayer('route-waypoints')) {
        m.addLayer({
          id: 'route-waypoints',
          type: 'circle',
          source: 'route-waypoints-source',
          paint: {
            'circle-radius': 5.5,
            'circle-color': [
              'match',
              ['get', 'hazard_level'],
              'SAFE', '#22c55e',
              'CAUTION', '#f59e0b',
              'HAZARD', '#ef4444',
              '#38bdf8',
            ],
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff',
          },
        });

        m.on('click', 'route-waypoints', (e: any) => {
          const props = e.features?.[0]?.properties;
          if (!props) return;
          new maplibregl.Popup({ closeButton: true, className: 'orca-popup' })
            .setLngLat(e.lngLat)
            .setHTML(`
              <div style="font-family:sans-serif;color:#0f172a;padding:5px;min-width:190px;">
                <div style="font-weight:800;font-size:12px;color:#0284c7;display:flex;align-items:center;gap:4px;">
                  <span>📍</span> <span>Waypoint #${props.step ?? 1}</span>
                </div>
                <div style="font-size:10px;color:#475569;margin-top:4px;line-height:1.6;">
                  <div><b>Distance:</b> ${props.distance_km ?? '—'} km</div>
                  <div><b>Wave Height:</b> ${props.wave_height_m ?? '—'} m</div>
                  <div><b>Current Velocity:</b> ${props.current_knots ?? '—'} kts</div>
                  <div><b>Hazard Level:</b> <span style="font-weight:700;color:${props.hazard_level === 'SAFE' ? '#16a34a' : props.hazard_level === 'CAUTION' ? '#d97706' : '#dc2626'};">${props.hazard_level ?? 'SAFE'}</span></div>
                </div>
              </div>
            `)
            .addTo(m);
        });

        m.on('mousemove', 'route-waypoints', () => {
          m.getCanvas().style.cursor = 'pointer';
        });
        m.on('mouseleave', 'route-waypoints', () => {
          m.getCanvas().style.cursor = '';
        });
      }

      // Highlight active route type
      if (m.getLayer('route-primary-line') && m.getLayer('route-alt-line')) {
        const isAlt = activeRouteType === 'ALTERNATIVE';
        m.setPaintProperty('route-primary-line', 'line-opacity', isAlt ? 0.35 : 0.95);
        m.setPaintProperty('route-primary-line', 'line-width', isAlt ? 3.5 : 5.5);
        m.setPaintProperty('route-alt-line', 'line-opacity', isAlt ? 0.95 : 0.45);
        m.setPaintProperty('route-alt-line', 'line-width', isAlt ? 5.5 : 3.5);
      }

      // Clear existing markers
      routeStartMarker.current?.remove();
      routeStartMarker.current = null;
      routeEndMarker.current?.remove();
      routeEndMarker.current = null;

      if (currentRoute) {
        // Departure Start Marker
        const sCoords = currentRoute.geojson?.geometry?.coordinates?.[0] || [routeOrigin.lon, routeOrigin.lat];
        const sEl = document.createElement('div');
        sEl.className = 'route-start-pin cursor-pointer';
        sEl.innerHTML = `
          <div style="background:#0284c7;color:white;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 3px 10px rgba(2,132,199,0.5);border:2.5px solid white;">
            ⚓
          </div>
        `;
        routeStartMarker.current = new maplibregl.Marker({ element: sEl })
          .setLngLat([sCoords[0], sCoords[1]])
          .addTo(m);

        // Target Destination Marker
        const eCoords = currentRoute.geojson?.geometry?.coordinates?.slice(-1)[0] || (routeDestination ? [routeDestination.lon, routeDestination.lat] : null);
        if (eCoords) {
          const eEl = document.createElement('div');
          eEl.className = 'route-end-pin cursor-pointer';
          eEl.innerHTML = `
            <div style="background:#ef4444;color:white;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 3px 10px rgba(239,68,68,0.5);border:2.5px solid white;">
              🎯
            </div>
          `;
          routeEndMarker.current = new maplibregl.Marker({ element: eEl })
            .setLngLat([eCoords[0], eCoords[1]])
            .addTo(m);
        }

        // Fit map bounds to encompass the entire route
        const coords = currentRoute.geojson?.geometry?.coordinates || [];
        if (coords.length > 1) {
          let minLon = coords[0][0];
          let maxLon = coords[0][0];
          let minLat = coords[0][1];
          let maxLat = coords[0][1];
          for (const c of coords) {
            minLon = Math.min(minLon, c[0]);
            maxLon = Math.max(maxLon, c[0]);
            minLat = Math.min(minLat, c[1]);
            maxLat = Math.max(maxLat, c[1]);
          }
          m.fitBounds(
            [
              [minLon, minLat],
              [maxLon, maxLat],
            ],
            {
              padding: { top: 90, bottom: 210, left: 100, right: 100 },
              maxZoom: 10.5,
              duration: 1100,
            }
          );
        }
      }
    };

    if (m.isStyleLoaded()) {
      updateRoute();
    } else {
      m.once('load', updateRoute);
    }
  }, [currentRoute, activeRouteType]);


  // Geocoding search handler
  const handleSearch = async () => {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    try {
      const results = await geocodeLocation(q);
      if (results && results.length > 0) {
        const best = results[0];
        onLocationSelect({
          name: best.name,
          lat: best.latitude,
          lon: best.longitude,
        });
        checkGeofence(best.latitude, best.longitude);
        setQuery('');
      }
    } catch (err) {
      console.warn('Geocoding error:', err);
    } finally {
      setSearching(false);
    }
  };

  const toggleLayer = (layerName: string) => {
    setLayers((prev) => {
      if (prev.includes(layerName)) {
        return prev.filter((l) => l !== layerName);
      }
      if (FIELD_OVERLAY_KEYS.includes(layerName)) {
        return [...prev.filter((l) => !FIELD_OVERLAY_KEYS.includes(l)), layerName];
      }
      return [...prev, layerName];
    });
  };

  return (
    <div
      className={`relative h-full w-full bg-[#f8f9fa] overflow-hidden ${
        isPickingDestinationOnMap ? 'cursor-crosshair' : ''
      }`}
    >
      {/* MapLibre WebGL Canvas Container */}
      <div ref={container} className="h-full w-full" />


      {/* INCOIS Style Zoom Controls (Top-Left +, - buttons matching screenshots) */}
      <div className="absolute top-3 left-3 z-20 flex flex-col bg-white rounded-md border border-slate-300 shadow-md overflow-hidden font-sans select-none">
        <button
          onClick={handleZoomIn}
          className="w-8 h-8 flex items-center justify-center text-slate-800 hover:bg-slate-100 hover:text-black transition-colors font-bold text-lg border-b border-slate-200"
          title="Zoom In"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
        </button>
        <button
          onClick={handleZoomOut}
          className="w-8 h-8 flex items-center justify-center text-slate-800 hover:bg-slate-100 hover:text-black transition-colors font-bold text-lg"
          title="Zoom Out"
        >
          <Minus className="w-4 h-4 stroke-[2.5]" />
        </button>
      </div>

      {/* Interactive Destination Picking Mode Guidance Banner */}
      {isPickingDestinationOnMap && (
        <div className="absolute top-14 left-1/2 -translate-x-1/2 z-30 flex items-center gap-3 px-4 py-2 rounded-xl bg-cyan-950/95 border-2 border-cyan-400 text-white shadow-2xl backdrop-blur-md animate-bounce select-none">
          <span className="text-base">🎯</span>
          <span className="text-xs font-extrabold text-cyan-200">
            Click anywhere in the ocean to set route destination
          </span>
          <button
            onClick={() => setIsPickingDestinationOnMap(false)}
            className="px-2 py-0.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-[10px] font-bold text-slate-300 border border-slate-700"
          >
            Cancel
          </button>
        </div>
      )}

      {/* REAL-TIME MARITIME BORDER & GEOFENCE ALERT BANNER */}
      {geofenceStatus !== 'SAFE' && !dismissBorderAlert && (
        <div
          className={`absolute top-14 left-1/2 -translate-x-1/2 z-30 max-w-lg w-[92%] sm:w-auto px-4 py-2.5 rounded-2xl shadow-2xl backdrop-blur-xl border flex items-center gap-3 transition-all duration-300 ${
            geofenceStatus === 'CRITICAL'
              ? 'bg-red-950/95 border-red-500 text-red-100 animate-pulse'
              : 'bg-amber-950/95 border-amber-500 text-amber-100'
          }`}
        >
          {geofenceStatus === 'CRITICAL' ? (
            <ShieldAlert className="w-5 h-5 text-red-400 flex-shrink-0 animate-bounce" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
          )}

          <div className="flex-1 min-w-0">
            <div className="text-xs font-extrabold tracking-wide uppercase flex items-center gap-2">
              <span>{geofenceStatus === 'CRITICAL' ? 'Critical Border Alert' : 'Border Proximity Warning'}</span>
              {minBorderDistanceKm !== null && (
                <span className="px-1.5 py-0.2 rounded bg-black/40 text-[10px] font-mono">
                  {minBorderDistanceKm} km to boundary
                </span>
              )}
            </div>
            <div className="text-[11px] text-slate-200 mt-0.5 leading-tight line-clamp-2">
              {borderAlertMessage || `Approaching ${closestBorderName || 'Restricted Boundary'}.`}
            </div>
            {safeReturnHeadingDeg !== null && (
              <div className="text-[10px] font-bold text-cyan-300 mt-1 flex items-center gap-1">
                <ArrowUpRight
                  className="w-3.5 h-3.5"
                  style={{ transform: `rotate(${safeReturnHeadingDeg}deg)` }}
                />
                <span>Recommended Safe Course: Steer Heading {safeReturnHeadingDeg}° (Westward)</span>
              </div>
            )}
          </div>

          <button
            onClick={() => setDismissBorderAlert(true)}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-black/30 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Active Destination Picking Banner */}
      {isPickingDestinationOnMap && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 bg-amber-500 text-slate-950 px-4 py-1.5 rounded-full font-bold text-xs shadow-2xl flex items-center gap-2 animate-bounce">
          <MapPin className="w-4 h-4" />
          <span>Click any point on the ocean to set route destination</span>
          <button
            onClick={() => setIsPickingDestinationOnMap(false)}
            className="ml-2 text-xs bg-slate-900 text-white rounded-full px-2 py-0.5"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Floating Map Controls (GPS Locate & Zoom) */}
      <div className="absolute top-20 right-3 sm:right-4 z-20 flex flex-col gap-1.5">
        <button
          onClick={handleLocateMe}
          disabled={locating}
          className="h-10 w-10 sm:h-9 sm:w-9 rounded-xl bg-slate-900/90 text-cyan-300 border border-slate-700/80 shadow-xl backdrop-blur-md flex items-center justify-center hover:bg-slate-800 transition-all touch-target"
          title="Locate My Vessel (Native GPS)"
          aria-label="Locate Vessel"
        >
          {locating ? <Loader2 className="w-4 h-4 animate-spin text-cyan-400" /> : <Crosshair className="w-4 h-4" />}
        </button>

        <button
          onClick={() => map.current?.zoomIn()}
          className="h-10 w-10 sm:h-9 sm:w-9 rounded-xl bg-slate-900/90 text-slate-200 border border-slate-700/80 shadow-xl backdrop-blur-md flex items-center justify-center hover:bg-slate-800 transition-all touch-target"
          title="Zoom In"
          aria-label="Zoom In"
        >
          <Plus className="w-4 h-4" />
        </button>

        <button
          onClick={() => map.current?.zoomOut()}
          className="h-10 w-10 sm:h-9 sm:w-9 rounded-xl bg-slate-900/90 text-slate-200 border border-slate-700/80 shadow-xl backdrop-blur-md flex items-center justify-center hover:bg-slate-800 transition-all touch-target"
          title="Zoom Out"
          aria-label="Zoom Out"
        >
          <Minus className="w-4 h-4" />
        </button>
      </div>

      {/* Top Floating Search & Layer Toggle (Subtle & Clean) */}
      <div className="absolute top-3 left-3 sm:left-14 z-20 flex items-center gap-1.5 max-w-[calc(100vw-13rem)] sm:max-w-sm">
        <div className="relative flex-1 flex items-center min-w-0">
          <input
            type="text"
            placeholder="Search port..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="w-full pl-7 pr-6 py-1.5 rounded-lg bg-white/95 border border-slate-300 text-slate-800 placeholder:text-slate-500 text-xs shadow-md focus:outline-none focus:border-blue-500 transition-all font-sans truncate"
          />
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2" />
          {searching && (
            <div className="absolute right-2 h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          )}
        </div>

        <button
          onClick={() => {
            const hasFieldLayer = layers.some((l) => ['wind', 'waves', 'currents', 'sst', 'chlorophyll'].includes(l));
            if (hasFieldLayer) {
              setLayers(layers.filter((l) => !['wind', 'waves', 'currents', 'sst', 'chlorophyll'].includes(l)));
            } else {
              setLayers([...layers, 'wind']);
            }
          }}
          className={`px-2.5 py-1.5 rounded-md text-xs font-bold border shadow-md transition-all flex items-center gap-1.5 ${
            layers.some((l) => ['wind', 'waves', 'currents', 'sst', 'chlorophyll'].includes(l))
              ? 'bg-blue-600 text-white border-blue-500 hover:bg-blue-700'
              : 'bg-white/95 text-slate-700 border-slate-300 hover:bg-slate-100'
          }`}
          title="Turn Grid Boxes On / Off"
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Grid: {layers.some((l) => ['wind', 'waves', 'currents', 'sst', 'chlorophyll'].includes(l)) ? 'ON' : 'OFF'}</span>
        </button>

        <button
          onClick={() => setShowLayerMenu(!showLayerMenu)}
          className="p-1.5 rounded-md bg-white/95 border border-slate-300 text-slate-700 hover:text-black shadow-md transition-all"
          title="Toggle Layers Menu"
        >
          <Layers className="w-4 h-4" />
        </button>

        {showLayerMenu && (
          <div className="absolute top-10 left-0 w-48 rounded-md bg-white border border-slate-300 shadow-xl p-2 z-30 font-sans text-xs animate-in fade-in zoom-in-95 duration-100">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-2 py-1 border-b border-slate-100 mb-1">
              Field Overlays
            </div>

            {[
              { key: 'wind', label: 'Wind Field', icon: Wind, color: 'text-blue-600' },
              { key: 'waves', label: 'Wave Height (SWH)', icon: Waves, color: 'text-cyan-600' },
              { key: 'currents', label: 'Ocean Currents', icon: Compass, color: 'text-indigo-600' },
              { key: 'sst', label: 'SST Heatmap', icon: Thermometer, color: 'text-orange-600' },
              { key: 'pfz', label: 'PFZ Advisory', icon: Fish, color: 'text-emerald-600' },
            ].map((item) => {
              const Icon = item.icon;
              const active = layers.includes(item.key);
              return (
                <button
                  key={item.key}
                  onClick={() => toggleLayer(item.key)}
                  className={`w-full text-left px-2 py-1.5 rounded flex items-center justify-between text-xs transition-colors ${
                    active ? 'bg-blue-50 text-blue-700 font-semibold' : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Icon className={`w-3.5 h-3.5 ${item.color}`} />
                    <span>{item.label}</span>
                  </span>
                  <span className={`h-2 w-2 rounded-full ${active ? 'bg-blue-600' : 'bg-slate-300'}`} />
                </button>
              );
            })}
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-2 py-1 border-b border-slate-100 mt-2 mb-1">
              Safety & Restrictions
            </div>

            {[
              { key: 'geofence', label: 'Restricted Defense & IMBL', icon: ShieldAlert, color: 'text-red-600', activeBg: 'bg-red-50 text-red-700', dotBg: 'bg-red-600' },
              { key: 'sustainability', label: 'Marine Protected Areas', icon: Leaf, color: 'text-emerald-600', activeBg: 'bg-emerald-50 text-emerald-700', dotBg: 'bg-emerald-600' },
            ].map((item) => {
              const Icon = item.icon;
              const active = layers.includes(item.key);
              return (
                <button
                  key={item.key}
                  onClick={() => toggleLayer(item.key)}
                  className={`w-full text-left px-2 py-1.5 rounded flex items-center justify-between text-xs transition-colors ${
                    active ? `${item.activeBg} font-semibold` : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Icon className={`w-3.5 h-3.5 ${item.color}`} />
                    <span>{item.label}</span>
                  </span>
                  <span className={`h-2 w-2 rounded-full ${active ? item.dotBg : 'bg-slate-300'}`} />
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* RESTRICTED ZONES & GEOFENCE MAP LEGEND */}
      <div className="absolute bottom-6 left-3 sm:left-4 z-20 bg-slate-900/95 text-white border border-slate-700/80 rounded-xl px-3 py-2.5 shadow-2xl backdrop-blur-md select-none text-[11px] max-w-[260px]">
        <div className="flex items-center justify-between gap-2 border-b border-slate-700/60 pb-1 mb-1.5">
          <span className="font-extrabold text-slate-200 flex items-center gap-1.5 text-xs">
            <ShieldAlert className="w-3.5 h-3.5 text-red-400" />
            Restricted Marine Zones
          </span>
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40">
            {layers.includes('geofence') ? 'ACTIVE' : 'OFF'}
          </span>
        </div>
        <div className="space-y-1.5 text-[10px] text-slate-300">
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3.5 rounded-sm bg-red-600/50 border-2 border-red-500 inline-flex items-center justify-center text-[8px] flex-shrink-0">
              ⛔
            </span>
            <span>Defense Exclusion (Missile/Naval)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3.5 rounded-sm bg-red-500/20 border-2 border-dashed border-red-500 inline-flex items-center justify-center text-[8px] flex-shrink-0">
              🚨
            </span>
            <span>International Border (IMBL)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3.5 rounded-sm bg-emerald-600/40 border-2 border-emerald-500 inline-flex items-center justify-center text-[8px] flex-shrink-0">
              🛡️
            </span>
            <span>Marine Protected Area (MPA)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
