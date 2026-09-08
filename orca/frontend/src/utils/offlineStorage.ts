/**
 * ORCA Offline Safety Storage & Local Geofence Engine.
 * 
 * Provides local caching and client-side border/geofence distance calculations
 * when offshore with zero internet connectivity.
 */

import { INDIAN_LANDING_CENTRES, type FishLandingCentre } from '../data/landingCentres';
import type { PFZZone } from '../components/ChatPanel';

const OFFLINE_STORAGE_KEYS = {
  GEOFENCE: 'orca_offline_geofence',
  LAST_PFZ: 'orca_offline_last_pfz',
  VESSEL_PROFILE: 'orca_vessel_profile',
};

// Essential offline IMBL coordinates
export const OFFLINE_IMBL_COORDINATES = [
  { name: 'Palk Strait IMBL (India - Sri Lanka)', lat: 9.30, lon: 79.40 },
  { name: 'Palk Bay IMBL (North)', lat: 9.75, lon: 79.70 },
  { name: 'Gulf of Mannar IMBL (South)', lat: 8.80, lon: 79.15 },
  { name: 'Sir Creek IMBL (India - Pakistan)', lat: 23.65, lon: 68.10 },
];

export interface VesselProfile {
  boat_type: 'Artisanal' | 'Motorized' | 'Mechanized Trawler';
  boat_size_m: number;
  fuel_capacity_l: number;
  maximum_range_km: number;
  maximum_safe_wave_m: number;
  maximum_safe_wind_ms: number;
  cruising_speed_knots: number;
}

export const DEFAULT_VESSEL_PROFILES: Record<string, VesselProfile> = {
  Artisanal: {
    boat_type: 'Artisanal',
    boat_size_m: 6.5,
    fuel_capacity_l: 40.0,
    maximum_range_km: 40.0,
    maximum_safe_wave_m: 2.0,
    maximum_safe_wind_ms: 10.0,
    cruising_speed_knots: 7.0,
  },
  Motorized: {
    boat_type: 'Motorized',
    boat_size_m: 9.5,
    fuel_capacity_l: 120.0,
    maximum_range_km: 90.0,
    maximum_safe_wave_m: 2.8,
    maximum_safe_wind_ms: 14.0,
    cruising_speed_knots: 10.0,
  },
  'Mechanized Trawler': {
    boat_type: 'Mechanized Trawler',
    boat_size_m: 18.0,
    fuel_capacity_l: 450.0,
    maximum_range_km: 250.0,
    maximum_safe_wave_m: 4.0,
    maximum_safe_wind_ms: 20.0,
    cruising_speed_knots: 12.0,
  },
};

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export function checkOfflineGeofence(lat: number, lon: number): {
  status: 'SAFE' | 'WARNING' | 'CRITICAL';
  bufferHierarchyLevel: 'SAFE_AREA' | 'WARNING_BUFFER' | 'CRITICAL_BUFFER' | 'RESTRICTED_AREA';
  minBorderDistanceKm: number;
  closestBorderName: string;
  alertMessage: string;
  isOffline: boolean;
} {
  let minDist = Infinity;
  let closestName = 'None';

  for (const border of OFFLINE_IMBL_COORDINATES) {
    const dist = haversineKm(lat, lon, border.lat, border.lon);
    if (dist < minDist) {
      minDist = dist;
      closestName = border.name;
    }
  }

  let status: 'SAFE' | 'WARNING' | 'CRITICAL' = 'SAFE';
  let bufferHierarchyLevel: 'SAFE_AREA' | 'WARNING_BUFFER' | 'CRITICAL_BUFFER' | 'RESTRICTED_AREA' = 'SAFE_AREA';
  let alertMessage = '✅ Safe Waters: Operating within permitted Indian maritime zone (Offline Check).';

  if (minDist < 1.5) {
    status = 'CRITICAL';
    bufferHierarchyLevel = 'RESTRICTED_AREA';
    alertMessage = `🚨 RESTRICTED AREA VIOLATION: Vessel is only ${minDist.toFixed(1)} km from ${closestName}! Turn back immediately.`;
  } else if (minDist < 5.0) {
    status = 'CRITICAL';
    bufferHierarchyLevel = 'CRITICAL_BUFFER';
    alertMessage = `🚨 CRITICAL BUFFER ALERT: Vessel is ${minDist.toFixed(1)} km from ${closestName}! Steer westward immediately.`;
  } else if (minDist < 12.0) {
    status = 'WARNING';
    bufferHierarchyLevel = 'WARNING_BUFFER';
    alertMessage = `⚠️ WARNING BUFFER: Approaching ${closestName} (${minDist.toFixed(1)} km away).`;
  }

  return {
    status,
    bufferHierarchyLevel,
    minBorderDistanceKm: Math.round(minDist * 10) / 10,
    closestBorderName: closestName,
    alertMessage,
    isOffline: true,
  };
}

export function saveLastKnownPFZ(zones: PFZZone[]): void {
  try {
    localStorage.setItem(OFFLINE_STORAGE_KEYS.LAST_PFZ, JSON.stringify(zones));
  } catch {}
}

export function loadLastKnownPFZ(): PFZZone[] {
  try {
    const data = localStorage.getItem(OFFLINE_STORAGE_KEYS.LAST_PFZ);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function saveVesselProfile(profile: VesselProfile): void {
  try {
    localStorage.setItem(OFFLINE_STORAGE_KEYS.VESSEL_PROFILE, JSON.stringify(profile));
  } catch {}
}

export function loadVesselProfile(): VesselProfile {
  try {
    const data = localStorage.getItem(OFFLINE_STORAGE_KEYS.VESSEL_PROFILE);
    return data ? JSON.parse(data) : DEFAULT_VESSEL_PROFILES.Motorized;
  } catch {
    return DEFAULT_VESSEL_PROFILES.Motorized;
  }
}
