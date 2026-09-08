import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { User, Session, AuthError } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured as initialIsConfigured } from '../lib/supabase';
import { setupCapacitorAuthListeners } from '../utils/capacitorAuth';
import type { SupportedLanguage } from './MarineContext';

export type UserRole = 'FISHERMAN' | 'ADMIN' | 'RESEARCHER';
export type VesselClass = 'Traditional' | 'Motorized' | 'Mechanized' | 'Deep Sea Trawler';

export interface UserProfile {
  id: string;
  full_name: string | null;
  email: string | null;
  phone_number: string | null;
  preferred_language: SupportedLanguage;
  preferred_harbor: string;
  user_role: UserRole;
  vessel_class?: string | null;
  avatar_url?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface SignUpMetadata {
  full_name?: string;
  phone_number?: string;
  preferred_language?: SupportedLanguage;
  preferred_harbor?: string;
  user_role?: UserRole;
  vessel_class?: string;
}

interface AuthContextValue {
  user: User | null;
  session: Session | null;
  profile: UserProfile | null;
  loading: boolean;
  isGuest: boolean;
  sessionExpired: boolean;
  authError: string | null;
  isConfigured: boolean;
  isPasswordRecovery: boolean;
  clearPasswordRecovery: () => void;
  signIn: (email: string, password: string) => Promise<{ error: AuthError | Error | null }>;
  signUp: (email: string, password: string, metadata?: SignUpMetadata) => Promise<{ error: AuthError | Error | null }>;
  signInWithOtp: (email: string) => Promise<{ error: AuthError | Error | null }>;
  signInWithGoogle: () => Promise<{ error: AuthError | Error | null }>;
  resetPassword: (email: string) => Promise<{ error: AuthError | Error | null }>;
  updatePassword: (newPassword: string) => Promise<{ error: AuthError | Error | null }>;
  signOut: () => Promise<void>;
  updateProfile: (updates: Partial<UserProfile>) => Promise<{ error: any }>;
  refreshProfile: () => Promise<void>;
  clearSessionExpired: () => void;
  continueAsGuest: () => void;
  reloadAuthConfig: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const GUEST_STORAGE_KEY = 'orca_guest_mode';

const DEFAULT_PROFILE: UserProfile = {
  id: 'guest',
  full_name: 'Marine Navigator',
  email: 'navigator@orca.marine',
  phone_number: null,
  preferred_language: 'en',
  preferred_harbor: 'Kasimedu Fishing Harbour, Chennai',
  user_role: 'FISHERMAN',
  vessel_class: 'Motorized',
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isGuest, setIsGuest] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      return window.localStorage.getItem(GUEST_STORAGE_KEY) === 'true';
    }
    return false;
  });
  const [sessionExpired, setSessionExpired] = useState<boolean>(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isConfigured, setIsConfigured] = useState<boolean>(initialIsConfigured);
  const [isPasswordRecovery, setIsPasswordRecovery] = useState<boolean>(false);

  // Fetch or create profile in `profiles` table
  const fetchProfile = async (currentUser: User) => {
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', currentUser.id)
        .single();

      if (data && !error) {
        setProfile(data as UserProfile);
        return data as UserProfile;
      }

      // If profile record doesn't exist yet, construct from user metadata & insert
      const meta = currentUser.user_metadata || {};
      const newProfile: UserProfile = {
        id: currentUser.id,
        full_name: meta.full_name || meta.name || currentUser.email?.split('@')[0] || 'ORCA User',
        email: currentUser.email || null,
        phone_number: meta.phone_number || null,
        preferred_language: (meta.preferred_language as SupportedLanguage) || 'en',
        preferred_harbor: meta.preferred_harbor || 'Kasimedu Fishing Harbour, Chennai',
        user_role: (meta.user_role as UserRole) || 'FISHERMAN',
        vessel_class: meta.vessel_class || 'Motorized',
      };

      const { data: created, error: insertError } = await supabase
        .from('profiles')
        .upsert(newProfile)
        .select()
        .single();

      if (created && !insertError) {
        setProfile(created as UserProfile);
        return created as UserProfile;
      }

      setProfile(newProfile);
      return newProfile;
    } catch (err) {
      console.warn('[ORCA Auth] Failed to load profile from database:', err);
      // Fallback in-memory profile
      const meta = currentUser.user_metadata || {};
      const fallback: UserProfile = {
        id: currentUser.id,
        full_name: meta.full_name || currentUser.email?.split('@')[0] || 'ORCA User',
        email: currentUser.email || null,
        phone_number: meta.phone_number || null,
        preferred_language: (meta.preferred_language as SupportedLanguage) || 'en',
        preferred_harbor: meta.preferred_harbor || 'Kasimedu Fishing Harbour, Chennai',
        user_role: (meta.user_role as UserRole) || 'FISHERMAN',
        vessel_class: meta.vessel_class || 'Motorized',
      };
      setProfile(fallback);
      return fallback;
    }
  };

  const reloadAuthConfig = () => {
    const configured = Boolean(
      window.localStorage.getItem('orca_supabase_url') ||
      (import.meta as any).env?.VITE_SUPABASE_URL
    );
    setIsConfigured(configured);
  };

  useEffect(() => {
    // Check if recovery link was opened via URL hash
    if (typeof window !== 'undefined' && window.location.hash.includes('type=recovery')) {
      setIsPasswordRecovery(true);
    }

    // If Supabase credentials are not configured, offer guest mode by default
    if (!isConfigured) {
      console.info('[ORCA Auth] Supabase credentials not yet configured. Available in guest/demo mode or configurable via UI.');
      if (typeof window !== 'undefined' && window.localStorage.getItem(GUEST_STORAGE_KEY) === 'true') {
        setIsGuest(true);
        setProfile(DEFAULT_PROFILE);
      }
      setLoading(false);
      return;
    }

    let mounted = true;

    // 1. Initial session restoration
    supabase.auth.getSession().then(({ data: { session }, error }) => {
      if (!mounted) return;
      if (error) {
        console.error('[ORCA Auth] Error checking session:', error);
      }
      if (session?.user) {
        setSession(session);
        setUser(session.user);
        setIsGuest(false);
        fetchProfile(session.user);
      } else if (typeof window !== 'undefined' && window.localStorage.getItem(GUEST_STORAGE_KEY) === 'true') {
        setIsGuest(true);
        setProfile(DEFAULT_PROFILE);
      }
      setLoading(false);
    });

    // 2. Auth state change listener (login, logout, token refresh, password recovery)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, currentSession) => {
        if (!mounted) return;

        if (event === 'PASSWORD_RECOVERY') {
          setIsPasswordRecovery(true);
          if (currentSession?.user) {
            setSession(currentSession);
            setUser(currentSession.user);
          }
          return;
        }

        if (event === 'SIGNED_IN' && currentSession?.user) {
          setSession(currentSession);
          setUser(currentSession.user);
          setIsGuest(false);
          setSessionExpired(false);
          setIsPasswordRecovery(false);
          if (typeof window !== 'undefined') {
            window.localStorage.removeItem(GUEST_STORAGE_KEY);
          }
          await fetchProfile(currentSession.user);
        } else if (event === 'SIGNED_OUT') {
          setSession(null);
          setUser(null);
          setProfile(null);
          setIsGuest(false);
          setIsPasswordRecovery(false);
        } else if (event === 'TOKEN_REFRESHED' && currentSession) {
          setSession(currentSession);
        } else if (event === 'USER_UPDATED' && currentSession?.user) {
          setUser(currentSession.user);
          await fetchProfile(currentSession.user);
        }
      }
    );

    // 3. Android Capacitor deep link listener for OAuth and Magic Link callbacks
    const removeCapacitorListener = setupCapacitorAuthListeners(() => {
      supabase.auth.getSession().then(({ data: { session } }) => {
        if (session?.user) {
          setSession(session);
          setUser(session.user);
          fetchProfile(session.user);
        }
      });
    });

    // 4. Session expiration listener dispatched from API client 401s
    const handleSessionExpired = () => {
      console.warn('[ORCA Auth] Session expired. Redirecting to login.');
      setSessionExpired(true);
      setUser(null);
      setSession(null);
      setProfile(null);
    };
    window.addEventListener('orca-auth-session-expired', handleSessionExpired);

    return () => {
      mounted = false;
      subscription.unsubscribe();
      removeCapacitorListener();
      window.removeEventListener('orca-auth-session-expired', handleSessionExpired);
    };
  }, [isConfigured]);

  const signIn = async (email: string, password: string) => {
    setAuthError(null);
    if (!isConfigured) {
      // Demo login
      setIsGuest(true);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(GUEST_STORAGE_KEY, 'true');
      }
      setProfile({
        ...DEFAULT_PROFILE,
        email,
        full_name: email.split('@')[0],
      });
      return { error: null };
    }

    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) {
        setAuthError(error.message);
        return { error };
      }
      if (data.session) {
        setSession(data.session);
        setUser(data.user);
        setIsGuest(false);
        if (typeof window !== 'undefined') {
          window.localStorage.removeItem(GUEST_STORAGE_KEY);
        }
        await fetchProfile(data.user);
      }
      return { error: null };
    } catch (err: any) {
      setAuthError(err.message || 'Login failed');
      return { error: err };
    }
  };

  const signUp = async (email: string, password: string, metadata: SignUpMetadata = {}) => {
    setAuthError(null);
    if (!isConfigured) {
      setIsGuest(true);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(GUEST_STORAGE_KEY, 'true');
      }
      setProfile({
        ...DEFAULT_PROFILE,
        email,
        full_name: metadata.full_name || email.split('@')[0],
        preferred_language: metadata.preferred_language || 'en',
        preferred_harbor: metadata.preferred_harbor || 'Kasimedu Fishing Harbour, Chennai',
        user_role: metadata.user_role || 'FISHERMAN',
        vessel_class: metadata.vessel_class || 'Motorized',
      });
      return { error: null };
    }

    try {
      const isNative = typeof window !== 'undefined' && (window as any).Capacitor?.isNativePlatform();
      const emailRedirectTo = isNative ? 'com.orca.marine://login-callback' : window.location.origin;

      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo,
          data: {
            full_name: metadata.full_name || '',
            phone_number: metadata.phone_number || '',
            preferred_language: metadata.preferred_language || 'en',
            preferred_harbor: metadata.preferred_harbor || 'Kasimedu Fishing Harbour, Chennai',
            user_role: metadata.user_role || 'FISHERMAN',
            vessel_class: metadata.vessel_class || 'Motorized',
          },
        },
      });

      if (error) {
        setAuthError(error.message);
        return { error };
      }

      if (data.user) {
        if (data.session) {
          setSession(data.session);
          setUser(data.user);
          setIsGuest(false);
          if (typeof window !== 'undefined') {
            window.localStorage.removeItem(GUEST_STORAGE_KEY);
          }
          await fetchProfile(data.user);
        }
      }
      return { error: null };
    } catch (err: any) {
      setAuthError(err.message || 'Signup failed');
      return { error: err };
    }
  };

  const signInWithOtp = async (email: string) => {
    setAuthError(null);
    if (!isConfigured) {
      setIsGuest(true);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(GUEST_STORAGE_KEY, 'true');
      }
      setProfile({
        ...DEFAULT_PROFILE,
        email,
        full_name: email.split('@')[0],
      });
      return { error: null };
    }

    try {
      const isNative = typeof window !== 'undefined' && (window as any).Capacitor?.isNativePlatform();
      const emailRedirectTo = isNative ? 'com.orca.marine://login-callback' : window.location.origin;

      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo,
        },
      });

      if (error) {
        setAuthError(error.message);
        return { error };
      }
      return { error: null };
    } catch (err: any) {
      setAuthError(err.message || 'Failed to send magic link');
      return { error: err };
    }
  };

  const signInWithGoogle = async () => {
    setAuthError(null);
    if (!isConfigured) {
      setIsGuest(true);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(GUEST_STORAGE_KEY, 'true');
      }
      setProfile(DEFAULT_PROFILE);
      return { error: null };
    }

    try {
      const isNative = typeof window !== 'undefined' && (window as any).Capacitor?.isNativePlatform();
      const redirectTo = isNative ? 'com.orca.marine://login-callback' : window.location.origin;

      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo,
        },
      });

      if (error) {
        setAuthError(error.message);
        return { error };
      }
      return { error: null };
    } catch (err: any) {
      setAuthError(err.message || 'Google login failed');
      return { error: err };
    }
  };

  const resetPassword = async (email: string) => {
    setAuthError(null);
    if (!isConfigured) {
      return { error: null };
    }
    try {
      const isNative = typeof window !== 'undefined' && (window as any).Capacitor?.isNativePlatform();
      const redirectTo = isNative ? 'com.orca.marine://reset-password' : `${window.location.origin}/#type=recovery`;

      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo,
      });
      if (error) {
        setAuthError(error.message);
        return { error };
      }
      return { error: null };
    } catch (err: any) {
      setAuthError(err.message || 'Password reset request failed');
      return { error: err };
    }
  };

  const updatePassword = async (newPassword: string) => {
    setAuthError(null);
    if (!isConfigured) {
      return { error: null };
    }
    try {
      const { data, error } = await supabase.auth.updateUser({
        password: newPassword,
      });
      if (error) {
        setAuthError(error.message);
        return { error };
      }
      if (data.user) {
        setUser(data.user);
      }
      setIsPasswordRecovery(false);
      return { error: null };
    } catch (err: any) {
      setAuthError(err.message || 'Failed to update password');
      return { error: err };
    }
  };

  const signOut = async () => {
    if (isConfigured) {
      try {
        await supabase.auth.signOut();
      } catch (err) {
        console.warn('[ORCA Auth] Error during signOut:', err);
      }
    }
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(GUEST_STORAGE_KEY);
    }
    setSession(null);
    setUser(null);
    setProfile(null);
    setIsGuest(false);
    setSessionExpired(false);
    setIsPasswordRecovery(false);
  };

  const updateProfile = async (updates: Partial<UserProfile>) => {
    if (!user) {
      if (isGuest && profile) {
        setProfile({ ...profile, ...updates });
      }
      return { error: null };
    }

    try {
      const { data, error } = await supabase
        .from('profiles')
        .update({
          ...updates,
          updated_at: new Date().toISOString(),
        })
        .eq('id', user.id)
        .select()
        .single();

      if (!error && data) {
        setProfile(data as UserProfile);
      }
      return { error };
    } catch (err) {
      return { error: err };
    }
  };

  const refreshProfile = async () => {
    if (user) {
      await fetchProfile(user);
    }
  };

  const continueAsGuest = () => {
    setIsGuest(true);
    setProfile(DEFAULT_PROFILE);
    setSessionExpired(false);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(GUEST_STORAGE_KEY, 'true');
    }
  };

  const clearSessionExpired = () => {
    setSessionExpired(false);
  };

  const clearPasswordRecovery = () => {
    setIsPasswordRecovery(false);
    if (typeof window !== 'undefined' && window.location.hash.includes('type=recovery')) {
      window.history.replaceState(null, '', window.location.pathname);
    }
  };

  const value: AuthContextValue = {
    user,
    session,
    profile,
    loading,
    isGuest,
    sessionExpired,
    authError,
    isConfigured,
    isPasswordRecovery,
    clearPasswordRecovery,
    signIn,
    signUp,
    signInWithOtp,
    signInWithGoogle,
    resetPassword,
    updatePassword,
    signOut,
    updateProfile,
    refreshProfile,
    clearSessionExpired,
    continueAsGuest,
    reloadAuthConfig,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
