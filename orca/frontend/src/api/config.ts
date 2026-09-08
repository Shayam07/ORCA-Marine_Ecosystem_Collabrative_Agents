import { Capacitor } from '@capacitor/core';
import { getAccessToken } from '../lib/supabase';

/**
 * ORCA Centralized API Configuration & Connectivity Diagnostics
 * 
 * Manages the API endpoint resolution across:
 * 1. Web browser (development via Vite proxy: relative '')
 * 2. Web browser (production with custom backend URL: VITE_API_URL)
 * 3. Physical Android device running Capacitor (LAN IP, e.g. http://192.168.1.48:8000)
 * 4. Android Emulator (http://10.0.2.2:8000)
 * 5. Dynamic runtime IP override saved in localStorage
 */

// Default local network development IP for physical devices
export const DEFAULT_LAN_BACKEND_URL = 'http://192.168.1.48:8000';

/**
 * Returns the active base URL for API requests.
 */
export function getApiBaseUrl(): string {
  // 1. Check runtime override stored in localStorage (allows changing server IP in-app)
  const savedUrl = typeof window !== 'undefined' ? localStorage.getItem('orca_api_base_url') : null;
  if (savedUrl && savedUrl.trim()) {
    return savedUrl.trim().replace(/\/+$/, '');
  }

  // 2. Check environment variable from Vite (.env / build-time)
  const envUrl = (import.meta as any).env?.VITE_API_URL || (import.meta as any).env?.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, '');
  }

  // 3. If running natively inside Capacitor (Android/iOS phone)
  if (Capacitor.isNativePlatform()) {
    return DEFAULT_LAN_BACKEND_URL;
  }

  // 4. Web browser fallback: empty string allows relative paths like `/api/v1/...`
  // which are proxied by Vite in dev or handled by nginx/reverse proxy in prod
  return '';
}

/**
 * Constructs a fully qualified API URL from a relative or absolute path.
 */
export function getApiUrl(path: string, baseOverride?: string): string {
  const base = baseOverride !== undefined ? (baseOverride ? baseOverride.trim().replace(/\/+$/, '') : '') : getApiBaseUrl();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return base ? `${base}${cleanPath}` : cleanPath;
}

/**
 * Persists a custom API base URL for mobile testing.
 */
export function setCustomApiBaseUrl(url: string | null): void {
  if (typeof window === 'undefined') return;
  if (!url || !url.trim()) {
    localStorage.removeItem('orca_api_base_url');
  } else {
    localStorage.setItem('orca_api_base_url', url.trim().replace(/\/+$/, ''));
  }
}

export type HealthErrorCategory =
  | 'OFFLINE'
  | 'TIMEOUT'
  | 'SERVER_NOT_RUNNING'
  | 'WRONG_IP_OR_ISOLATION'
  | 'MIXED_CONTENT_BLOCKED'
  | 'HTTP_ERROR'
  | 'UNKNOWN';

export interface HealthCheckResult {
  connected: boolean;
  status: 'ok' | 'error';
  service?: string;
  url: string;
  endpointUrl: string;
  latencyMs?: number;
  errorCategory?: HealthErrorCategory;
  message: string;
  recommendation: string;
}

/**
 * Comprehensive diagnostic check against the backend /health endpoint.
 * Classifies exact failure causes (Down, Wrong IP, Firewall, AP Isolation, Mixed Content, Offline).
 */
export async function checkBackendHealth(urlOverride?: string): Promise<HealthCheckResult> {
  const baseUrl = urlOverride !== undefined 
    ? (urlOverride ? urlOverride.trim().replace(/\/+$/, '') : '') 
    : getApiBaseUrl();
  
  const endpointUrl = baseUrl ? `${baseUrl}/health` : '/health';
  const displayUrl = baseUrl || 'http://localhost:8000 (Vite Proxy)';

  // 1. Check client offline state
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return {
      connected: false,
      status: 'error',
      url: displayUrl,
      endpointUrl,
      errorCategory: 'OFFLINE',
      message: 'Device has no active internet or local network connection.',
      recommendation: 'Check that Wi-Fi or Mobile Data is turned ON on your phone/device.',
    };
  }

  // 2. Check for potential Mixed Content blocking in browser / WebView
  if (typeof window !== 'undefined' && window.location.protocol === 'https:' && endpointUrl.startsWith('http://')) {
    return {
      connected: false,
      status: 'error',
      url: displayUrl,
      endpointUrl,
      errorCategory: 'MIXED_CONTENT_BLOCKED',
      message: 'Insecure HTTP request blocked by HTTPS security policy (Mixed Content).',
      recommendation: 'In Capacitor, set androidScheme: "http" in capacitor.config.ts or use an HTTPS backend URL.',
    };
  }

  const startTime = Date.now();
  const controller = new AbortController();
  const timeoutMs = 5000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(endpointUrl, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const latencyMs = Date.now() - startTime;

    if (response.ok) {
      let data: any = {};
      try {
        data = await response.json();
      } catch {
        // Not JSON
      }

      return {
        connected: true,
        status: 'ok',
        service: data.service || 'orca-backend',
        url: displayUrl,
        endpointUrl,
        latencyMs,
        message: `Connected successfully (${latencyMs}ms)`,
        recommendation: 'Backend is active and responding to health probes.',
      };
    }

    return {
      connected: false,
      status: 'error',
      url: displayUrl,
      endpointUrl,
      latencyMs,
      errorCategory: 'HTTP_ERROR',
      message: `Server returned HTTP ${response.status} (${response.statusText}).`,
      recommendation: 'Verify backend routes and logs for 500 or 404 responses.',
    };
  } catch (err: any) {
    clearTimeout(timeoutId);
    const latencyMs = Date.now() - startTime;

    // Timeout
    if (err.name === 'AbortError') {
      return {
        connected: false,
        status: 'error',
        url: displayUrl,
        endpointUrl,
        latencyMs,
        errorCategory: 'TIMEOUT',
        message: `Connection timed out after ${timeoutMs / 1000}s.`,
        recommendation: 'The server IP may be unreachable. Check that: 1) The PC and Phone are on the same Wi-Fi, 2) Windows Firewall allows inbound port 8000, 3) The router is not blocking traffic between devices (AP Isolation). Try a mobile hotspot or run "adb reverse tcp:8000 tcp:8000".',
      };
    }

    // Network / TypeError (Connection refused or host unreachable)
    const isNative = Capacitor.isNativePlatform();
    const isLoopback = endpointUrl.includes('localhost') || endpointUrl.includes('127.0.0.1');

    let recommendation = 'Make sure the FastAPI backend is running on 0.0.0.0:8000 (not only 127.0.0.1).';

    if (isNative && isLoopback) {
      recommendation = 'On an Android device, 127.0.0.1 refers to the phone itself, NOT your computer! Use your computer Wi-Fi IPv4 address (e.g., http://192.168.1.48:8000) or run "adb reverse tcp:8000 tcp:8000" over USB.';
    } else {
      recommendation = '1) Ensure the backend is running (`uvicorn main:app --host 0.0.0.0 --port 8000`). 2) Verify PC IPv4 (`ipconfig`). 3) Check Windows Firewall port 8000. 4) If on Public/College Wi-Fi, AP Isolation may block device-to-device traffic; test via mobile hotspot or USB adb reverse.';
    }

    return {
      connected: false,
      status: 'error',
      url: displayUrl,
      endpointUrl,
      latencyMs,
      errorCategory: isLoopback && isNative ? 'WRONG_IP_OR_ISOLATION' : 'SERVER_NOT_RUNNING',
      message: `Unable to connect to ORCA backend server at ${displayUrl}.`,
      recommendation,
    };
  }
}

export interface ApiFetchOptions extends RequestInit {
  timeoutMs?: number;
}

export class ApiError extends Error {
  status?: number;
  isOffline?: boolean;
  isTimeout?: boolean;
  isNetworkError?: boolean;
  serverDetail?: any;

  constructor(
    message: string,
    options?: {
      status?: number;
      isOffline?: boolean;
      isTimeout?: boolean;
      isNetworkError?: boolean;
      serverDetail?: any;
    }
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = options?.status;
    this.isOffline = options?.isOffline;
    this.isTimeout = options?.isTimeout;
    this.isNetworkError = options?.isNetworkError;
    this.serverDetail = options?.serverDetail;
  }
}

/**
 * Robust fetch wrapper with timeout, offline detection, and descriptive error handling.
 */
export async function apiFetch<T = any>(endpoint: string, options: ApiFetchOptions = {}): Promise<T> {
  // Check browser offline status
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    throw new ApiError('Your device appears to be offline. Please check your Wi-Fi or mobile data.', {
      isOffline: true,
    });
  }

  const { timeoutMs = 20000, ...fetchOptions } = options;
  const fullUrl = getApiUrl(endpoint);

  // Retrieve Supabase JWT access token if user is signed in
  const token = await getAccessToken();
  const authHeaders: Record<string, string> = {};
  if (token) {
    authHeaders['Authorization'] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(fullUrl, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
        ...(fetchOptions.headers || {}),
      },
    });

    clearTimeout(timeoutId);

    if (res.status === 401) {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('orca-auth-session-expired'));
      }
    }

    if (!res.ok) {
      let errorDetail: any = null;
      let errorMessage = `Server responded with HTTP ${res.status} (${res.statusText})`;
      try {
        errorDetail = await res.json();
        if (errorDetail?.detail) {
          errorMessage = typeof errorDetail.detail === 'string' 
            ? errorDetail.detail 
            : JSON.stringify(errorDetail.detail);
        }
      } catch {
        // Response was not JSON
      }

      throw new ApiError(errorMessage, {
        status: res.status,
        serverDetail: errorDetail,
      });
    }

    return (await res.json()) as T;
  } catch (err: any) {
    clearTimeout(timeoutId);

    if (err instanceof ApiError) {
      throw err;
    }

    if (err.name === 'AbortError') {
      throw new ApiError(
        `Request timed out after ${Math.round(timeoutMs / 1000)}s waiting for the server.`,
        { isTimeout: true }
      );
    }

    const base = getApiBaseUrl();
    const targetDesc = base ? `at ${base}` : '';
    throw new ApiError(
      `Unable to connect to ORCA backend server ${targetDesc}. Please check that the server is running on 0.0.0.0:8000 and your device is on the same network.`,
      { isNetworkError: true }
    );
  }
}
