import { Capacitor } from '@capacitor/core';
import { App as CapacitorApp } from '@capacitor/app';
import { supabase } from '../lib/supabase';

/**
 * Android / Capacitor Deep Linking & OAuth Lifecycle Handler
 * 
 * Handles URL schemes such as:
 * - com.orca.marine://login-callback#access_token=...
 * - com.orca.marine://reset-password#access_token=...
 */
export function setupCapacitorAuthListeners(onAuthSuccess?: () => void): () => void {
  if (!Capacitor.isNativePlatform()) {
    return () => {};
  }

  const handleUrlOpen = async (data: { url: string }) => {
    console.log('[Capacitor Auth] Deep link opened:', data.url);

    try {
      const url = new URL(data.url);

      // Handle OAuth or magic-link callback hash or query params
      if (url.hash && (url.hash.includes('access_token') || url.hash.includes('refresh_token'))) {
        const hashParams = new URLSearchParams(url.hash.replace('#', ''));
        const accessToken = hashParams.get('access_token');
        const refreshToken = hashParams.get('refresh_token');

        if (accessToken && refreshToken) {
          const { error } = await supabase.auth.setSession({
            access_token: accessToken,
            refresh_token: refreshToken,
          });

          if (!error) {
            console.log('[Capacitor Auth] Session successfully restored from deep link');
            onAuthSuccess?.();
          } else {
            console.error('[Capacitor Auth] Error restoring session from deep link:', error);
          }
        }
      } else if (url.searchParams.has('code')) {
        // PKCE flow callback
        const code = url.searchParams.get('code');
        if (code) {
          const { error } = await supabase.auth.exchangeCodeForSession(code);
          if (!error) {
            console.log('[Capacitor Auth] PKCE session exchanged successfully');
            onAuthSuccess?.();
          } else {
            console.error('[Capacitor Auth] PKCE exchange error:', error);
          }
        }
      }
    } catch (err) {
      console.error('[Capacitor Auth] Failed to parse deep link URL:', err);
    }
  };

  const listenerPromise = CapacitorApp.addListener('appUrlOpen', handleUrlOpen);

  return () => {
    listenerPromise.then((handle) => handle.remove());
  };
}
