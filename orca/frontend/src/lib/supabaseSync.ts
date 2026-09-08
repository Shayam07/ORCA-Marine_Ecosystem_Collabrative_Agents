/**
 * ORCA Supabase Data Synchronization Engine
 * 
 * Provides high-reliability sync between local browser storage and Supabase cloud tables:
 * - `chat_history`: Conversation logs and advisory Q&A
 * - `saved_pfz`: Fishermen's saved Potential Fishing Zones
 * - `saved_routes`: Planned or recorded navigation routes
 * - `alert_preferences`: Cyclone, wave, wind & IMBL threshold notification configs
 * 
 * Includes automatic fallback to localStorage when in Guest mode or disconnected.
 */

import { supabase, isSupabaseConfigured } from './supabase';

export interface SavedPFZItem {
  id?: string;
  zone_id: string;
  zone_name: string;
  latitude: number;
  longitude: number;
  depth_m?: number;
  species?: string[];
  metadata?: Record<string, any>;
  created_at?: string;
}

export interface SavedRouteItem {
  id?: string;
  route_name: string;
  origin: { lat: number; lon: number; name?: string };
  destination: { lat: number; lon: number; name?: string };
  waypoints?: Array<{ lat: number; lon: number; name?: string }>;
  distance_nm?: number;
  fuel_estimate_l?: number;
  weather_summary?: Record<string, any>;
  created_at?: string;
}

export interface AlertPreferencesItem {
  id?: string;
  min_severity?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  sms_enabled?: boolean;
  voice_call_enabled?: boolean;
  whatsapp_enabled?: boolean;
  push_enabled?: boolean;
  imbl_warning_distance_km?: number;
  max_wave_height_m?: number;
  max_wind_speed_kmh?: number;
}

export interface ChatHistoryMessage {
  id?: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  intent?: string | null;
  location?: { lat: number; lon: number } | null;
  sources?: any[];
  metadata?: Record<string, any>;
  created_at?: string;
}

const LOCAL_STORAGE_FALLBACKS = {
  PFZ: 'orca_local_saved_pfz',
  ROUTES: 'orca_local_saved_routes',
  ALERT_PREFS: 'orca_local_alert_prefs',
  CHAT: 'orca_local_chat_history',
};

async function getCurrentUserId(): Promise<string | null> {
  if (!isSupabaseConfigured) return null;
  try {
    const { data } = await supabase.auth.getSession();
    return data.session?.user?.id || null;
  } catch {
    return null;
  }
}

// ==============================================================================
// 1. SAVED PFZ ZONES
// ==============================================================================

export async function savePFZZone(zone: SavedPFZItem): Promise<{ success: boolean; error?: string }> {
  const userId = await getCurrentUserId();

  if (userId) {
    try {
      const { error } = await supabase.from('saved_pfz').upsert({
        user_id: userId,
        zone_id: zone.zone_id,
        zone_name: zone.zone_name,
        latitude: zone.latitude,
        longitude: zone.longitude,
        depth_m: zone.depth_m || null,
        species: zone.species || [],
        metadata: zone.metadata || {},
      });
      if (error) throw error;
      return { success: true };
    } catch (err: any) {
      console.warn('[ORCA Sync] Error saving PFZ to Supabase, saving locally:', err);
    }
  }

  // Local storage fallback
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_FALLBACKS.PFZ);
    const list: SavedPFZItem[] = raw ? JSON.parse(raw) : [];
    const filtered = list.filter((item) => item.zone_id !== zone.zone_id);
    filtered.unshift({ ...zone, created_at: new Date().toISOString() });
    localStorage.setItem(LOCAL_STORAGE_FALLBACKS.PFZ, JSON.stringify(filtered));
    return { success: true };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function getSavedPFZZones(): Promise<SavedPFZItem[]> {
  const userId = await getCurrentUserId();

  if (userId) {
    try {
      const { data, error } = await supabase
        .from('saved_pfz')
        .select('*')
        .eq('user_id', userId)
        .order('created_at', { ascending: false });
      if (!error && data) {
        return data as SavedPFZItem[];
      }
    } catch (err) {
      console.warn('[ORCA Sync] Error fetching PFZ from Supabase:', err);
    }
  }

  // Local fallback
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_FALLBACKS.PFZ);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export async function deleteSavedPFZZone(zoneId: string): Promise<boolean> {
  const userId = await getCurrentUserId();

  if (userId) {
    try {
      await supabase.from('saved_pfz').delete().eq('user_id', userId).eq('zone_id', zoneId);
    } catch (err) {
      console.warn('[ORCA Sync] Error deleting PFZ from Supabase:', err);
    }
  }

  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_FALLBACKS.PFZ);
    if (raw) {
      const list: SavedPFZItem[] = JSON.parse(raw);
      const updated = list.filter((item) => item.zone_id !== zoneId);
      localStorage.setItem(LOCAL_STORAGE_FALLBACKS.PFZ, JSON.stringify(updated));
    }
    return true;
  } catch {
    return false;
  }
}

// ==============================================================================
// 2. SAVED ROUTES
// ==============================================================================

export async function saveNavigationRoute(route: SavedRouteItem): Promise<{ success: boolean; error?: string }> {
  const userId = await getCurrentUserId();

  if (userId) {
    try {
      const { error } = await supabase.from('saved_routes').insert({
        user_id: userId,
        route_name: route.route_name,
        origin: route.origin,
        destination: route.destination,
        waypoints: route.waypoints || [],
        distance_nm: route.distance_nm || 0,
        fuel_estimate_l: route.fuel_estimate_l || null,
        weather_summary: route.weather_summary || {},
      });
      if (error) throw error;
      return { success: true };
    } catch (err: any) {
      console.warn('[ORCA Sync] Error saving route to Supabase:', err);
    }
  }

  // Local fallback
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_FALLBACKS.ROUTES);
    const list: SavedRouteItem[] = raw ? JSON.parse(raw) : [];
    list.unshift({ ...route, created_at: new Date().toISOString() });
    localStorage.setItem(LOCAL_STORAGE_FALLBACKS.ROUTES, JSON.stringify(list));
    return { success: true };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}

export async function getSavedNavigationRoutes(): Promise<SavedRouteItem[]> {
  const userId = await getCurrentUserId();

  if (userId) {
    try {
      const { data, error } = await supabase
        .from('saved_routes')
        .select('*')
        .eq('user_id', userId)
        .order('created_at', { ascending: false });
      if (!error && data) {
        return data as SavedRouteItem[];
      }
    } catch (err) {
      console.warn('[ORCA Sync] Error fetching routes from Supabase:', err);
    }
  }

  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_FALLBACKS.ROUTES);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

// ==============================================================================
// 3. CHAT HISTORY
// ==============================================================================

export async function logChatMessage(msg: ChatHistoryMessage): Promise<void> {
  const userId = await getCurrentUserId();

  if (userId) {
    try {
      await supabase.from('chat_history').insert({
        user_id: userId,
        conversation_id: msg.conversation_id,
        role: msg.role,
        content: msg.content,
        intent: msg.intent || null,
        location: msg.location || null,
        sources: msg.sources || [],
        metadata: msg.metadata || {},
      });
      return;
    } catch (err) {
      console.warn('[ORCA Sync] Error recording chat to Supabase:', err);
    }
  }

  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_FALLBACKS.CHAT);
    const list: ChatHistoryMessage[] = raw ? JSON.parse(raw) : [];
    list.push({ ...msg, created_at: new Date().toISOString() });
    // Keep max 100 offline messages
    if (list.length > 100) list.shift();
    localStorage.setItem(LOCAL_STORAGE_FALLBACKS.CHAT, JSON.stringify(list));
  } catch (err) {
    console.warn('[ORCA Sync] Error saving chat locally:', err);
  }
}

export async function getRecentChatHistory(conversationId?: string): Promise<ChatHistoryMessage[]> {
  const userId = await getCurrentUserId();

  if (userId) {
    try {
      let query = supabase
        .from('chat_history')
        .select('*')
        .eq('user_id', userId)
        .order('created_at', { ascending: true })
        .limit(50);

      if (conversationId) {
        query = query.eq('conversation_id', conversationId);
      }

      const { data, error } = await query;
      if (!error && data) {
        return data as ChatHistoryMessage[];
      }
    } catch (err) {
      console.warn('[ORCA Sync] Error fetching chat history from Supabase:', err);
    }
  }

  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_FALLBACKS.CHAT);
    const list: ChatHistoryMessage[] = raw ? JSON.parse(raw) : [];
    if (conversationId) {
      return list.filter((m) => m.conversation_id === conversationId);
    }
    return list;
  } catch {
    return [];
  }
}

// ==============================================================================
// 4. ALERT PREFERENCES
// ==============================================================================

export async function getAlertPreferences(): Promise<AlertPreferencesItem | null> {
  const userId = await getCurrentUserId();

  if (userId) {
    try {
      const { data, error } = await supabase
        .from('alert_preferences')
        .select('*')
        .eq('user_id', userId)
        .single();
      if (!error && data) {
        return data as AlertPreferencesItem;
      }
    } catch (err) {
      console.warn('[ORCA Sync] Error getting alert preferences:', err);
    }
  }

  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_FALLBACKS.ALERT_PREFS);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export async function saveAlertPreferences(
  prefs: Partial<AlertPreferencesItem>
): Promise<{ success: boolean; error?: string }> {
  const userId = await getCurrentUserId();

  if (userId) {
    try {
      const { error } = await supabase.from('alert_preferences').upsert({
        user_id: userId,
        ...prefs,
        updated_at: new Date().toISOString(),
      });
      if (error) throw error;
      return { success: true };
    } catch (err: any) {
      console.warn('[ORCA Sync] Error saving alert prefs to Supabase:', err);
    }
  }

  try {
    localStorage.setItem(LOCAL_STORAGE_FALLBACKS.ALERT_PREFS, JSON.stringify(prefs));
    return { success: true };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
}
