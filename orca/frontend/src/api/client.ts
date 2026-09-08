/* ORCA API Client */

import type { AnalysisRequest, AnalysisResult, MapLayer, ProviderHealth } from '../types';
import { apiFetch, getApiUrl, getApiBaseUrl, setCustomApiBaseUrl, ApiError } from './config';

export { getApiUrl, getApiBaseUrl, setCustomApiBaseUrl, ApiError, apiFetch };

async function fetchJSON<T>(endpoint: string, options?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const url = endpoint.startsWith('/api/') ? endpoint : `/api/v1${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  return apiFetch<T>(url, options);
}

export async function runQuery(request: AnalysisRequest): Promise<AnalysisResult> {
  return fetchJSON<AnalysisResult>('/query', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getAnalysis(analysisId: string): Promise<AnalysisResult> {
  return fetchJSON<AnalysisResult>(`/analysis/${analysisId}`);
}

export async function getMapLayers(): Promise<{ layers: MapLayer[] }> {
  return fetchJSON<{ layers: MapLayer[] }>('/map/layers');
}

export async function getMapData(
  layerId: string,
  bbox: [number, number, number, number],
  startDate: string,
  endDate: string
): Promise<any> {
  const [west, south, east, north] = bbox;
  return fetchJSON(
    `/map/data/${layerId}?west=${west}&south=${south}&east=${east}&north=${north}&start_date=${startDate}&end_date=${endDate}`
  );
}

export async function getPFZZones(
  lat: number,
  lon: number,
  landingCentreId?: string,
  vesselClass?: string
): Promise<{ zones: any[]; geojson: any }> {
  const params = new URLSearchParams({
    center_lat: lat.toString(),
    center_lon: lon.toString(),
    ...(landingCentreId ? { landing_centre_id: landingCentreId } : {}),
    ...(vesselClass ? { vessel_class: vesselClass } : {}),
  });
  return fetchJSON<{ zones: any[]; geojson: any }>(`/map/pfz?${params.toString()}`);
}

export async function getSourceStatus(): Promise<{ providers: ProviderHealth[] }> {
  return fetchJSON<{ providers: ProviderHealth[] }>('/sources/status');
}

export async function getHealth(): Promise<any> {
  return fetchJSON('/health');
}

export async function checkGeofencePoint(lat: number, lon: number): Promise<any> {
  return fetchJSON(`/map/geofence/check?lat=${lat}&lon=${lon}`);
}

export async function getGeofencePolygons(): Promise<any> {
  return fetchJSON('/map/geofence');
}

export async function optimizeRoute(payload: any): Promise<any> {
  return fetchJSON('/map/route/optimize', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export interface GeocodedLocation {
  name: string;
  display_name: string;
  latitude: number;
  longitude: number;
  state?: string;
  district?: string;
  environment: string;
  nearest_coast_km?: number;
  confidence: number;
  bbox?: [number, number, number, number];
}

export async function geocodeLocation(query: string): Promise<GeocodedLocation[]> {
  const res = await fetchJSON<{ results: GeocodedLocation[] }>(
    '/chat/geocode',
    {
      method: 'POST',
      body: JSON.stringify({ query, country: 'India' }),
    }
  );
  return res.results;
}

export async function reverseGeocodeLocation(
  latitude: number,
  longitude: number
): Promise<GeocodedLocation | null> {
  try {
    const res = await fetchJSON<GeocodedLocation>(
      '/chat/reverse-geocode',
      {
        method: 'POST',
        body: JSON.stringify({ latitude, longitude }),
      }
    );
    return res;
  } catch {
    return null;
  }
}

export interface ChatRequestPayload {
  message: string;
  conversation_id?: string | null;
  data_mode?: string;
  location?: { name: string; lat: number; lon: number } | null;
  landing_centre?: any;
  selected_zone?: any;
  language?: string;
}

export async function sendMessage(payload: ChatRequestPayload): Promise<any> {
  return fetchJSON<any>('/chat/message', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: 30000,
  });
}

export async function processVoiceAudio(payload: { audio_base64: string; language: string; format?: string }): Promise<any> {
  return fetchJSON<any>('/chat/voice/process', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: 25000,
  });
}
