-- ==============================================================================
-- ORCA Marine AI — Supabase Database Architecture & Security Schema
-- ==============================================================================
-- Includes:
-- 1. Custom types & role definitions (FISHERMAN, RESEARCHER, ADMIN)
-- 2. Profiles table linked to auth.users with auto-creation trigger
-- 3. User-specific marine data tables (chat_history, saved_pfz, saved_routes, alert_preferences)
-- 4. Row Level Security (RLS) enabled on all tables
-- 5. Granular per-user access policies ensuring zero cross-tenant access
-- ==============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------------------------
-- 1. USER ROLES ENUM
-- ------------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('FISHERMAN', 'RESEARCHER', 'ADMIN');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ------------------------------------------------------------------------------
-- 2. PROFILES TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone_number TEXT,
    preferred_language TEXT DEFAULT 'en',
    preferred_harbor TEXT DEFAULT 'Chennai Fishing Harbour',
    user_role user_role DEFAULT 'FISHERMAN' NOT NULL,
    vessel_class TEXT DEFAULT 'Motorized',
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()) NOT NULL
);

-- Index for email & lookup performance
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(user_role);

-- ------------------------------------------------------------------------------
-- 3. CHAT HISTORY TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    intent TEXT,
    location JSONB,
    sources JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON public.chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_conversation ON public.chat_history(conversation_id);

-- ------------------------------------------------------------------------------
-- 4. SAVED PFZ ZONES TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.saved_pfz (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    zone_id TEXT NOT NULL,
    zone_title TEXT NOT NULL,
    center_lat FLOAT NOT NULL,
    center_lon FLOAT NOT NULL,
    suitability_score FLOAT,
    classification TEXT DEFAULT 'HIGH',
    crowding_level TEXT DEFAULT 'LOW',
    distance_km FLOAT,
    harbor_name TEXT,
    sst FLOAT,
    chlorophyll FLOAT,
    geometry JSONB,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_saved_pfz_user_id ON public.saved_pfz(user_id);

-- ------------------------------------------------------------------------------
-- 5. SAVED ROUTES TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.saved_routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    origin_name TEXT,
    origin_lat FLOAT NOT NULL,
    origin_lon FLOAT NOT NULL,
    destination_name TEXT,
    destination_lat FLOAT NOT NULL,
    destination_lon FLOAT NOT NULL,
    distance_km FLOAT,
    eta_hours FLOAT,
    diesel_liters FLOAT,
    saved_diesel_liters FLOAT,
    fuel_saved_percent FLOAT,
    safety_score FLOAT,
    geojson JSONB,
    waypoints JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_saved_routes_user_id ON public.saved_routes(user_id);

-- ------------------------------------------------------------------------------
-- 6. ALERT PREFERENCES TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.alert_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    imbl_border_alert BOOLEAN DEFAULT true NOT NULL,
    defense_exclusion_alert BOOLEAN DEFAULT true NOT NULL,
    mpa_sanctuary_alert BOOLEAN DEFAULT true NOT NULL,
    high_wave_alert BOOLEAN DEFAULT true NOT NULL,
    squall_wind_alert BOOLEAN DEFAULT true NOT NULL,
    cyclone_alert BOOLEAN DEFAULT true NOT NULL,
    sound_alerts_enabled BOOLEAN DEFAULT true NOT NULL,
    warning_distance_km FLOAT DEFAULT 10.0 NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()) NOT NULL
);

-- ------------------------------------------------------------------------------
-- 7. AUTOMATIC TIMESTAMP TRIGGER
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc', now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS on_profile_updated ON public.profiles;
CREATE TRIGGER on_profile_updated
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS on_alert_prefs_updated ON public.alert_preferences;
CREATE TRIGGER on_alert_prefs_updated
    BEFORE UPDATE ON public.alert_preferences
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- 8. AUTOMATIC PROFILE CREATION ON AUTH.USERS SIGNUP
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    default_name TEXT;
    default_lang TEXT;
    default_harbor TEXT;
    default_role public.user_role;
    default_vessel TEXT;
BEGIN
    default_name := COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1));
    default_lang := COALESCE(NEW.raw_user_meta_data->>'preferred_language', 'en');
    default_harbor := COALESCE(NEW.raw_user_meta_data->>'preferred_harbor', 'Chennai Fishing Harbour');
    default_vessel := COALESCE(NEW.raw_user_meta_data->>'vessel_class', 'Motorized');
    
    -- Safe role parsing
    BEGIN
        default_role := (NEW.raw_user_meta_data->>'user_role')::public.user_role;
    EXCEPTION WHEN OTHERS THEN
        default_role := 'FISHERMAN'::public.user_role;
    END;

    -- Insert profile
    INSERT INTO public.profiles (
        id,
        full_name,
        email,
        phone_number,
        preferred_language,
        preferred_harbor,
        user_role,
        vessel_class,
        created_at,
        updated_at
    )
    VALUES (
        NEW.id,
        default_name,
        NEW.email,
        NEW.raw_user_meta_data->>'phone_number',
        default_lang,
        default_harbor,
        COALESCE(default_role, 'FISHERMAN'),
        default_vessel,
        timezone('utc', now()),
        timezone('utc', now())
    )
    ON CONFLICT (id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        updated_at = timezone('utc', now());

    -- Insert default alert preferences
    INSERT INTO public.alert_preferences (user_id)
    VALUES (NEW.id)
    ON CONFLICT (user_id) DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger firing on every new auth.users signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ------------------------------------------------------------------------------
-- 9. ROW LEVEL SECURITY (RLS) POLICIES
-- ------------------------------------------------------------------------------
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_pfz ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alert_preferences ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can view and edit only their own profile
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
    ON public.profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

-- Chat History: Users can view and manage their own messages
CREATE POLICY "Users can view own chat history"
    ON public.chat_history FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own chat history"
    ON public.chat_history FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own chat history"
    ON public.chat_history FOR DELETE
    USING (auth.uid() = user_id);

-- Saved PFZ: Users can manage their own saved fishing zones
CREATE POLICY "Users can view own saved PFZ"
    ON public.saved_pfz FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own saved PFZ"
    ON public.saved_pfz FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own saved PFZ"
    ON public.saved_pfz FOR DELETE
    USING (auth.uid() = user_id);

-- Saved Routes: Users can manage their own saved marine routes
CREATE POLICY "Users can view own saved routes"
    ON public.saved_routes FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own saved routes"
    ON public.saved_routes FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own saved routes"
    ON public.saved_routes FOR DELETE
    USING (auth.uid() = user_id);

-- Alert Preferences: Users can manage their own alert preferences
CREATE POLICY "Users can view own alert preferences"
    ON public.alert_preferences FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update own alert preferences"
    ON public.alert_preferences FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can insert own alert preferences"
    ON public.alert_preferences FOR INSERT
    WITH CHECK (auth.uid() = user_id);
