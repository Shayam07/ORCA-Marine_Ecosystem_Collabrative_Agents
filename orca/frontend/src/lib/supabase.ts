import { createClient, SupabaseClient } from '@supabase/supabase-js';

/**
 * Supabase Client Configuration for ORCA Marine Intelligence
 * 
 * Supports:
 * 1. Web browser development & production (via .env or local storage configuration)
 * 2. Capacitor Android / iOS native apps (persistent session, auto token refresh, deep link OAuth)
 * 3. In-app dynamic configuration so users or developers can connect their Supabase project directly
 * 4. Graceful offline & placeholder fallback when credentials are not configured
 */

const STORAGE_KEYS = {
  URL: 'orca_supabase_url',
  ANON_KEY: 'orca_supabase_anon_key',
  AUTH_TOKEN: 'orca_auth_token_v1',
};

function readStoredCredentials(): { url: string; anonKey: string; source: 'env' | 'localStorage' | 'none' } {
  const envUrl = ((import.meta as any).env?.VITE_SUPABASE_URL || '').trim();
  const envKey = ((import.meta as any).env?.VITE_SUPABASE_ANON_KEY || '').trim();

  let localUrl = '';
  let localKey = '';
  if (typeof window !== 'undefined' && window.localStorage) {
    localUrl = (window.localStorage.getItem(STORAGE_KEYS.URL) || '').trim();
    localKey = (window.localStorage.getItem(STORAGE_KEYS.ANON_KEY) || '').trim();
  }

  if (localUrl && localKey && isValidCredential(localUrl, localKey)) {
    return { url: localUrl, anonKey: localKey, source: 'localStorage' };
  }

  if (envUrl && envKey && isValidCredential(envUrl, envKey)) {
    return { url: envUrl, anonKey: envKey, source: 'env' };
  }

  return {
    url: localUrl || envUrl || '',
    anonKey: localKey || envKey || '',
    source: 'none',
  };
}

function isValidCredential(url: string, anonKey: string): boolean {
  if (!url || !anonKey) return false;
  if (url.includes('placeholder') || anonKey.includes('placeholder')) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:';
  } catch {
    return false;
  }
}

const initialConfig = readStoredCredentials();

export let isSupabaseConfigured = isValidCredential(initialConfig.url, initialConfig.anonKey);

function buildClient(url: string, anonKey: string): SupabaseClient {
  const activeUrl = isValidCredential(url, anonKey) ? url : 'https://orca-placeholder.supabase.co';
  const activeKey = isValidCredential(url, anonKey) ? anonKey : 'placeholder-anon-key';

  return createClient(activeUrl, activeKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storage: typeof window !== 'undefined' ? window.localStorage : undefined,
      storageKey: STORAGE_KEYS.AUTH_TOKEN,
    },
  });
}

export let supabase: SupabaseClient = buildClient(initialConfig.url, initialConfig.anonKey);

/**
 * Retrieve current configuration status and source
 */
export function getSupabaseConfig(): {
  url: string;
  anonKey: string;
  isConfigured: boolean;
  source: 'env' | 'localStorage' | 'none';
} {
  const current = readStoredCredentials();
  return {
    url: current.url,
    anonKey: current.anonKey ? `${current.anonKey.slice(0, 10)}...${current.anonKey.slice(-6)}` : '',
    isConfigured: isValidCredential(current.url, current.anonKey),
    source: current.source,
  };
}

/**
 * Configure or update Supabase credentials dynamically in-app.
 * Persists to localStorage and re-initializes client.
 */
export function configureSupabase(url: string, anonKey: string): { success: boolean; error?: string } {
  const trimmedUrl = url.trim();
  const trimmedKey = anonKey.trim();

  if (!isValidCredential(trimmedUrl, trimmedKey)) {
    return { success: false, error: 'Invalid URL or Anon Key. URL must start with https://' };
  }

  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(STORAGE_KEYS.URL, trimmedUrl);
      window.localStorage.setItem(STORAGE_KEYS.ANON_KEY, trimmedKey);
    }
    supabase = buildClient(trimmedUrl, trimmedKey);
    isSupabaseConfigured = true;
    return { success: true };
  } catch (err: any) {
    return { success: false, error: err.message || 'Failed to initialize Supabase client' };
  }
}

/**
 * Clear custom Supabase credentials from localStorage and reset to environment values.
 */
export function clearSupabaseConfig(): void {
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.removeItem(STORAGE_KEYS.URL);
    window.localStorage.removeItem(STORAGE_KEYS.ANON_KEY);
  }
  const restored = readStoredCredentials();
  isSupabaseConfigured = isValidCredential(restored.url, restored.anonKey);
  supabase = buildClient(restored.url, restored.anonKey);
}

/**
 * Test connectivity against a Supabase instance (e.g. before saving settings).
 */
export async function testSupabaseConnection(
  url?: string,
  anonKey?: string
): Promise<{ ok: boolean; message: string }> {
  try {
    const testUrl = url ? url.trim() : readStoredCredentials().url;
    const testKey = anonKey ? anonKey.trim() : readStoredCredentials().anonKey;

    if (!isValidCredential(testUrl, testKey)) {
      return { ok: false, message: 'Invalid URL or Anon Key format.' };
    }

    const testClient = createClient(testUrl, testKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });

    // Fast check: inspect auth settings/session status endpoint
    const { error } = await testClient.auth.getSession();
    if (error) {
      return { ok: false, message: error.message };
    }

    return { ok: true, message: 'Successfully connected to Supabase project!' };
  } catch (err: any) {
    return { ok: false, message: err?.message || 'Connection test failed' };
  }
}

/**
 * Helper to get current active auth access token (for backend Bearer headers)
 */
export async function getAccessToken(): Promise<string | null> {
  if (!isSupabaseConfigured) return null;
  try {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token || null;
  } catch (err) {
    console.warn('[ORCA Auth] Failed to get session access token:', err);
    return null;
  }
}
