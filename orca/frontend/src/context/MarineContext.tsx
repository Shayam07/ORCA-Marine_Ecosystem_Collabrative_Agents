import { createContext, useContext, useMemo, useState, useEffect, type ReactNode } from 'react';
import type { PFZZone } from '../components/ChatPanel';
import { INDIAN_LANDING_CENTRES, type FishLandingCentre } from '../data/landingCentres';
import {
  checkOfflineGeofence,
  saveLastKnownPFZ,
  loadLastKnownPFZ,
  saveVesselProfile,
  loadVesselProfile,
  type VesselProfile,
  DEFAULT_VESSEL_PROFILES,
} from '../utils/offlineStorage';
import { getPFZZones, getApiUrl } from '../api/client';

export type DataMode = 'LIVE' | 'CACHED' | 'DEMO';
export type OperationalMode = 'PFZ' | 'OSF' | 'WINDS' | 'CURRENTS' | 'HIGH_WAVES' | 'SAFETY' | 'ROUTE';
export type SupportedLanguage = 'en' | 'ta' | 'te' | 'ml' | 'hi' | 'bn' | 'gu' | 'kn' | 'mr' | 'or';
export type GeofenceAlertStatus = 'SAFE' | 'WARNING' | 'CRITICAL';

// Full-area colored overlays are radio-exclusive (OSF-app style): only one
// may be visible at a time. Vector/boundary layers toggle additively on top.
export const FIELD_OVERLAY_KEYS = ['sst', 'wind', 'chlorophyll', 'currents', 'waves'];

/** Keep at most one field overlay (first-listed wins), preserving vector layers. */
export function normalizeLayers(next: string[]): string[] {
  const vector = next.filter((k) => !FIELD_OVERLAY_KEYS.includes(k));
  const field = next.filter((k) => FIELD_OVERLAY_KEYS.includes(k));
  if (field.length === 0) return vector;
  return [...vector, field[0]];
}

/** Radio-style toggle: enabling a field overlay disables the others. */
export function toggleLayer(prev: string[], key: string): string[] {
  if (prev.includes(key)) return prev.filter((k) => k !== key);
  if (FIELD_OVERLAY_KEYS.includes(key)) {
    return [...prev.filter((k) => !FIELD_OVERLAY_KEYS.includes(k)), key];
  }
  return [...prev, key];
}



/** Which field overlay should be active by default in a given operational mode. */
export function defaultLayersForMode(mode: OperationalMode): string[] {
  switch (mode) {
    case 'OSF':
    case 'HIGH_WAVES':
      return ['waves', 'geofence', 'sustainability'];
    case 'WINDS':
      return ['wind', 'geofence', 'sustainability'];
    case 'CURRENTS':
      return ['currents', 'geofence', 'sustainability'];
    case 'SAFETY':
      return ['geofence', 'sustainability'];
    case 'ROUTE':
      return ['geofence', 'sustainability'];
    case 'PFZ':
    default:
      return ['pfz', 'geofence', 'sustainability'];
  }
}

export interface MarineLocation {
  name: string;
  lat: number;
  lon: number;
  environment?: string;
}

export interface MarineRouteInfo {
  distance_km: number;
  eta_hours: number;
  estimated_diesel_liters: number;
  saved_diesel_liters: number;
  fuel_saved_percent?: number;
  max_wave_height_m: number;
  safety_score?: number;
  risk_level?: string;
  bearing_deg?: number;
  warnings?: string[];
  waypoints?: Array<{
    step: number;
    lat: number;
    lon: number;
    distance_km: number;
    bearing_deg?: number;
    wave_height_m: number;
    current_knots: number;
    hazard_level: string;
  }>;
  geojson?: any;
  alternative_geojson?: any;
}

interface MarineContextValue {
  // Operational Mode
  operationalMode: OperationalMode;
  setOperationalMode: (mode: OperationalMode) => void;

  // Selected Landing Centre
  landingCentre: FishLandingCentre;
  setLandingCentre: (centre: FishLandingCentre) => void;

  // Location & Map State
  location: MarineLocation | null;
  setLocation: (value: MarineLocation | null) => void;
  intent: string | null;
  setIntent: (value: string | null) => void;

  // PFZ & Zones
  selectedZone: PFZZone | null;
  setSelectedZone: (value: PFZZone | null) => void;
  zones: PFZZone[];
  setZones: (value: PFZZone[]) => void;
  refreshPFZZones: () => Promise<void>;

  // Layers & Route
  layers: string[];
  setLayers: (value: string[] | ((prev: string[]) => string[])) => void;
  currentRoute: MarineRouteInfo | null;
  setCurrentRoute: (value: MarineRouteInfo | null) => void;
  routeOrigin: MarineLocation;
  setRouteOrigin: (loc: MarineLocation) => void;
  routeDestination: MarineLocation | null;
  setRouteDestination: (loc: MarineLocation | null) => void;
  isPickingDestinationOnMap: boolean;
  setIsPickingDestinationOnMap: (picking: boolean) => void;
  activeRouteType: 'PRIMARY' | 'ALTERNATIVE';
  setActiveRouteType: (type: 'PRIMARY' | 'ALTERNATIVE') => void;

  // Real-Time Geofence & Maritime Border Alerts
  geofenceStatus: GeofenceAlertStatus;
  borderAlertMessage: string | null;
  minBorderDistanceKm: number | null;
  closestBorderName: string | null;
  safeReturnHeadingDeg: number | null;
  dismissBorderAlert: boolean;
  setDismissBorderAlert: (dismiss: boolean) => void;
  checkGeofence: (lat: number, lon: number) => Promise<any>;

  // Offline Safety & Vessel Profile
  isOffline: boolean;
  setIsOffline: (offline: boolean) => void;
  vesselProfile: VesselProfile;
  setVesselProfile: (profile: VesselProfile) => void;

  // OSF Timeline Playback
  forecastHour: number; // 0, 6, 12, 24, 48, 72
  setForecastHour: (hour: number) => void;
  isPlayingForecast: boolean;
  setIsPlayingForecast: (playing: boolean) => void;
  threatFilter: string;
  setThreatFilter: (threat: string) => void;

  // Global & Drawer States
  dataMode: DataMode;
  setDataMode: (value: DataMode) => void;
  language: SupportedLanguage;
  setLanguage: (lang: SupportedLanguage) => void;
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  aiAssistantOpen: boolean;
  setAiAssistantOpen: (open: boolean) => void;
}

const MarineContext = createContext<MarineContextValue | null>(null);

export function MarineProvider({ children }: { children: ReactNode }) {
  const [operationalMode, setOperationalMode] = useState<OperationalMode>('PFZ');
  const [landingCentre, setLandingCentre] = useState<FishLandingCentre>(INDIAN_LANDING_CENTRES[0]);
  const [location, setLocation] = useState<MarineLocation | null>(null);
  const [intent, setIntent] = useState<string | null>(null);
  const [selectedZone, setSelectedZone] = useState<PFZZone | null>(null);
  const [zones, setZonesState] = useState<PFZZone[]>(() => loadLastKnownPFZ());
  const [layers, setLayersState] = useState<string[]>(['wind', 'geofence', 'sustainability', 'pfz']);
  // Enforce the radio-exclusive field overlay invariant on every set
  const setLayers = (value: string[] | ((prev: string[]) => string[])) => {
    setLayersState((prev) => normalizeLayers(typeof value === 'function' ? value(prev) : value));
  };
  const [currentRoute, setCurrentRoute] = useState<MarineRouteInfo | null>(null);
  const [activeRouteType, setActiveRouteType] = useState<'PRIMARY' | 'ALTERNATIVE'>('PRIMARY');

  // Offline & Vessel Profile State
  const [isOffline, setIsOffline] = useState<boolean>(!navigator.onLine);
  const [vesselProfile, setVesselProfileState] = useState<VesselProfile>(() => loadVesselProfile());

  const setZones = (newZones: PFZZone[]) => {
    setZonesState(newZones);
    saveLastKnownPFZ(newZones);
  };

  const setVesselProfile = (profile: VesselProfile) => {
    setVesselProfileState(profile);
    saveVesselProfile(profile);
  };

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Geofence & Border Alert state
  const [geofenceStatus, setGeofenceStatus] = useState<GeofenceAlertStatus>('SAFE');
  const [borderAlertMessage, setBorderAlertMessage] = useState<string | null>(null);
  const [minBorderDistanceKm, setMinBorderDistanceKm] = useState<number | null>(null);
  const [closestBorderName, setClosestBorderName] = useState<string | null>(null);
  const [safeReturnHeadingDeg, setSafeReturnHeadingDeg] = useState<number | null>(null);
  const [dismissBorderAlert, setDismissBorderAlert] = useState(false);

  // Route Planning Coordinates
  const [routeOrigin, setRouteOrigin] = useState<MarineLocation>({
    name: INDIAN_LANDING_CENTRES[0].name,
    lat: INDIAN_LANDING_CENTRES[0].lat,
    lon: INDIAN_LANDING_CENTRES[0].lon,
  });

  const [routeDestination, setRouteDestination] = useState<MarineLocation | null>(null);
  const [isPickingDestinationOnMap, setIsPickingDestinationOnMap] = useState<boolean>(false);

  // OSF Timeline
  const [forecastHour, setForecastHour] = useState<number>(0);
  const [isPlayingForecast, setIsPlayingForecast] = useState<boolean>(false);
  const [threatFilter, setThreatFilter] = useState<string>('all');

  // App chrome states
  const [dataMode, setDataMode] = useState<DataMode>('LIVE');
  const [language, setLanguage] = useState<SupportedLanguage>('en');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [aiAssistantOpen, setAiAssistantOpen] = useState(false);

  // Real-time geofence check function
  const checkGeofence = async (lat: number, lon: number) => {
    try {
      if (isOffline || !navigator.onLine) {
        const off = checkOfflineGeofence(lat, lon);
        setGeofenceStatus(off.status);
        setBorderAlertMessage(off.alertMessage);
        setMinBorderDistanceKm(off.minBorderDistanceKm);
        setClosestBorderName(off.closestBorderName);
        if (off.status !== 'SAFE') setDismissBorderAlert(false);
        return off;
      }

      const res = await fetch(getApiUrl(`/api/v1/map/geofence/check?lat=${lat}&lon=${lon}`));
      if (!res.ok) {
        const off = checkOfflineGeofence(lat, lon);
        setGeofenceStatus(off.status);
        setBorderAlertMessage(off.alertMessage);
        setMinBorderDistanceKm(off.minBorderDistanceKm);
        setClosestBorderName(off.closestBorderName);
        return off;
      }
      const data = await res.json();
      setGeofenceStatus(data.status || 'SAFE');
      setBorderAlertMessage(data.alert_message || null);
      setMinBorderDistanceKm(data.min_border_distance_km || null);
      setClosestBorderName(data.closest_border_name || null);
      setSafeReturnHeadingDeg(data.safe_return_heading_deg || null);
      if (data.status !== 'SAFE') {
        setDismissBorderAlert(false);
      }
      return data;
    } catch (err) {
      console.warn('Geofence check falling back to offline engine:', err);
      const off = checkOfflineGeofence(lat, lon);
      setGeofenceStatus(off.status);
      setBorderAlertMessage(off.alertMessage);
      setMinBorderDistanceKm(off.minBorderDistanceKm);
      setClosestBorderName(off.closestBorderName);
      return off;
    }
  };

  // Fetch candidate PFZ zones for active landing centre
  const fetchPFZZones = async (centre: FishLandingCentre, vesselType?: string) => {
    try {
      const res = await getPFZZones(centre.lat, centre.lon, centre.id, vesselType || vesselProfile.boat_type);
      if (res && res.zones && res.zones.length > 0) {
        setZones(res.zones);
        if (!selectedZone) {
          setSelectedZone(res.zones[0]);
        }
      }
    } catch (err) {
      console.warn('Could not fetch candidate PFZ zones:', err);
    }
  };

  const refreshPFZZones = async () => {
    if (landingCentre) {
      await fetchPFZZones(landingCentre, vesselProfile.boat_type);
    }
  };

  // Synchronize origin & fetch PFZ zones with landing centre changes
  useEffect(() => {
    if (landingCentre) {
      setRouteOrigin({
        name: landingCentre.name,
        lat: landingCentre.lat,
        lon: landingCentre.lon,
      });
      checkGeofence(landingCentre.lat, landingCentre.lon);
      fetchPFZZones(landingCentre, vesselProfile.boat_type);
    }
  }, [landingCentre]);

  // Evaluate geofence on active location update
  useEffect(() => {
    if (location) {
      checkGeofence(location.lat, location.lon);
    }
  }, [location]);

  // Forecast playback timer
  useEffect(() => {
    if (!isPlayingForecast) return;
    const hours = [0, 6, 12, 24, 48, 72];
    const timer = setInterval(() => {
      setForecastHour((prev) => {
        const idx = hours.indexOf(prev);
        const nextIdx = (idx + 1) % hours.length;
        return hours[nextIdx];
      });
    }, 2200);

    return () => clearInterval(timer);
  }, [isPlayingForecast]);

  // Mode switch: show the matching OSF field overlay by default
  useEffect(() => {
    setLayers(defaultLayersForMode(operationalMode));
  }, [operationalMode]);

  const value = useMemo(
    () => ({
      operationalMode,
      setOperationalMode,
      landingCentre,
      setLandingCentre,
      location,
      setLocation,
      intent,
      setIntent,
      selectedZone,
      setSelectedZone,
      layers,
      setLayers,
      zones,
      setZones,
      refreshPFZZones,
      currentRoute,
      setCurrentRoute,
      routeOrigin,
      setRouteOrigin,
      routeDestination,
      setRouteDestination,
      isPickingDestinationOnMap,
      setIsPickingDestinationOnMap,
      activeRouteType,
      setActiveRouteType,
      geofenceStatus,
      borderAlertMessage,
      minBorderDistanceKm,
      closestBorderName,
      safeReturnHeadingDeg,
      dismissBorderAlert,
      setDismissBorderAlert,
      checkGeofence,
      isOffline,
      setIsOffline,
      vesselProfile,
      setVesselProfile,
      forecastHour,
      setForecastHour,
      isPlayingForecast,
      setIsPlayingForecast,
      threatFilter,
      setThreatFilter,
      dataMode,
      setDataMode,
      language,
      setLanguage,
      drawerOpen,
      setDrawerOpen,
      aiAssistantOpen,
      setAiAssistantOpen,
    }),
    [
      operationalMode,
      landingCentre,
      location,
      intent,
      selectedZone,
      layers,
      zones,
      currentRoute,
      routeOrigin,
      routeDestination,
      isPickingDestinationOnMap,
      activeRouteType,
      geofenceStatus,
      borderAlertMessage,
      minBorderDistanceKm,
      closestBorderName,
      safeReturnHeadingDeg,
      dismissBorderAlert,
      isOffline,
      vesselProfile,
      forecastHour,
      isPlayingForecast,
      threatFilter,
      dataMode,
      language,
      drawerOpen,
      aiAssistantOpen,
    ]
  );

  return <MarineContext.Provider value={value}>{children}</MarineContext.Provider>;
}

export function useMarineContext() {
  const value = useContext(MarineContext);
  if (!value) throw new Error('Marine context missing');
  return value;
}
