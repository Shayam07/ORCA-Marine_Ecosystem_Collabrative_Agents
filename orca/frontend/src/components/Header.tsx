import { useState, useEffect } from 'react';
import {
  Menu,
  Languages,
  Radio,
  Settings,
  Crosshair,
  Fish,
  Waves,
  Wind,
  Compass,
  AlertTriangle,
  ShieldCheck,
  Check,
  Route,
  Server,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useMarineContext, type SupportedLanguage } from '../context/MarineContext';
import { useAuth } from '../context/AuthContext';
import SettingsDialog from './SettingsDialog';
import IncoisLogo from './IncoisLogo';
import BackendStatusModal from './BackendStatusModal';
import UserProfileModal from './auth/UserProfileModal';
import { checkBackendHealth, getApiBaseUrl } from '../api/config';
import { LogOut, User as UserIcon, Shield, Anchor } from 'lucide-react';

const LANGUAGE_LABELS: Record<SupportedLanguage, { name: string; native: string }> = {
  en: { name: 'English', native: 'English' },
  ta: { name: 'Tamil', native: 'தமிழ்' },
  te: { name: 'Telugu', native: 'తెలుగు' },
  ml: { name: 'Malayalam', native: 'മലയാളം' },
  hi: { name: 'Hindi', native: 'हिन्दी' },
  bn: { name: 'Bengali', native: 'বাংলা' },
  gu: { name: 'Gujarati', native: 'ગુજરાતી' },
  kn: { name: 'Kannada', native: 'ಕನ್ನಡ' },
  mr: { name: 'Marathi', native: 'मराठी' },
  or: { name: 'Odia', native: 'ଓଡ଼ିଆ' },
};

export default function Header() {
  const {
    operationalMode,
    landingCentre,
    setDrawerOpen,
    dataMode,
    setDataMode,
    language,
    setLanguage,
    setLocation,
  } = useMarineContext();

  const { user, profile, signOut, isGuest } = useAuth();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [langMenuOpen, setLangMenuOpen] = useState(false);
  const [backendModalOpen, setBackendModalOpen] = useState(false);
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  const [activeUrl, setActiveUrl] = useState<string>('');

  useEffect(() => {
    let isMounted = true;
    const probe = async () => {
      setActiveUrl(getApiBaseUrl() || 'http://localhost:8000 (Proxy)');
      try {
        const res = await checkBackendHealth();
        if (isMounted) setBackendConnected(res.connected);
      } catch {
        if (isMounted) setBackendConnected(false);
      }
    };

    probe();
    const interval = setInterval(probe, 25000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const getModeTitle = () => {
    switch (operationalMode) {
      case 'WINDS':
        return {
          title: 'Winds',
          sub: 'ISRO MOSDAC / ERA5 Telemetry',
        };
      case 'OSF':
        return {
          title: 'Ocean State Forecast Composite Alerts',
          sub: 'INCOIS SAMUDRA Live Alerts',
        };
      case 'HIGH_WAVES':
        return {
          title: 'High Waves & Swell Surge Alert',
          sub: 'INCOIS Kallakkadal Matrix',
        };
      case 'CURRENTS':
        return {
          title: 'Ocean Currents & Drift',
          sub: 'HYCOM Surface Hydrodynamics',
        };
      case 'PFZ':
        return {
          title: 'Potential Fishing Zone (PFZ) Advisory',
          sub: 'Thermal & Chlorophyll Fronts',
        };
      case 'ROUTE':
        return {
          title: 'Space-Time Route Optimization',
          sub: 'A* Maritime Hazard Avoidance',
        };
      case 'SAFETY':
        return {
          title: 'IMBL & Maritime Safety Geofences',
          sub: 'Coast Guard Border Telemetry',
        };
      default:
        return {
          title: 'Ocean State Forecast Composite Alerts',
          sub: 'INCOIS SAMUDRA',
        };
    }
  };

  const modeInfo = getModeTitle();

  const handleCenterOnLandingCentre = () => {
    if (landingCentre) {
      setLocation({
        name: landingCentre.name,
        lat: landingCentre.lat,
        lon: landingCentre.lon,
        environment: 'COASTAL',
      });
    }
  };

  return (
    <>
      <header className="bg-[#1f242d] border-b border-[#2d3748] text-white px-3 sm:px-4 py-2 sm:py-2.5 shadow-md z-30 flex items-center justify-between select-none pt-safe">
        {/* Left: Hamburger Menu & Title (Matching Screenshots 1 & 2) */}
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <button
            onClick={() => setDrawerOpen(true)}
            className="p-1.5 -ml-1 rounded-md text-white hover:text-slate-200 hover:bg-white/10 transition-colors touch-target flex items-center justify-center"
            title="Open Menu"
            aria-label="Open Navigation Menu"
          >
            <Menu className="w-6 h-6 stroke-[2.2]" />
          </button>

          {/* Clean Title */}
          <div className="min-w-0">
            <h1 className="font-semibold text-base sm:text-lg tracking-tight text-white leading-tight truncate">
              {modeInfo.title}
            </h1>
          </div>
        </div>

        {/* Right Controls: Center GPS, Translation [文A], INCOIS Official Logo */}
        <div className="flex items-center gap-2 sm:gap-2.5 flex-shrink-0">
          {/* Live Backend Connection Indicator Button */}
          <button
            onClick={() => setBackendModalOpen(true)}
            className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all ${
              backendConnected === true
                ? 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300 hover:bg-emerald-900/60 shadow-sm'
                : backendConnected === false
                ? 'bg-rose-950/70 border-rose-500/60 text-rose-300 hover:bg-rose-900/70 shadow-sm animate-pulse'
                : 'bg-slate-800/80 border-slate-700 text-slate-300'
            }`}
            title={`ORCA Backend: ${backendConnected ? 'Connected' : 'Offline'} (${activeUrl}). Tap to inspect / change server IP.`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                backendConnected === true
                  ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                  : backendConnected === false
                  ? 'bg-rose-400 shadow-[0_0_8px_rgba(251,113,133,0.8)]'
                  : 'bg-slate-400 animate-ping'
              }`}
            />
            <span className="text-[10px] sm:text-xs tracking-wider uppercase font-mono">
              {backendConnected === true ? 'CONNECTED' : backendConnected === false ? 'OFFLINE' : 'CHECKING'}
            </span>
          </button>

          {/* Quick GPS Locate Centre */}
          <button
            onClick={handleCenterOnLandingCentre}
            className="hidden md:flex items-center gap-1 px-2 py-1 rounded-md bg-white/10 hover:bg-white/15 text-xs font-medium text-slate-200 transition-colors"
            title="Center on Indian Subcontinent"
          >
            <Crosshair className="w-3.5 h-3.5 text-cyan-300" />
            <span>Center Harbour</span>
          </button>

          {/* INCOIS Style Translation [文A] Button */}
          <div className="relative">
            <button
              onClick={() => setLangMenuOpen(!langMenuOpen)}
              className="flex items-center justify-center gap-1 px-2.5 py-1 rounded-lg bg-white text-slate-900 shadow-sm hover:bg-slate-100 transition-all font-sans"
              title="Translate / மொழி"
            >
              <span className="text-[14px] font-bold leading-none tracking-tighter">文A</span>
              <span className="text-[10px] font-bold uppercase text-slate-600 ml-0.5">{language}</span>
            </button>

            {langMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setLangMenuOpen(false)}
                />
                <div className="absolute right-0 mt-2 w-52 rounded-xl bg-slate-900 border border-slate-700 shadow-2xl py-2 z-50 animate-in fade-in zoom-in-95 duration-150">
                  <div className="px-3 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 mb-1">
                    Select Language / மொழி
                  </div>
                  <div className="max-h-60 overflow-y-auto">
                    {Object.entries(LANGUAGE_LABELS).map(([code, label]) => (
                      <button
                        key={code}
                        onClick={() => {
                          setLanguage(code as SupportedLanguage);
                          setLangMenuOpen(false);
                        }}
                        className={`w-full text-left px-3 py-1.5 flex items-center justify-between text-xs hover:bg-slate-800 transition-colors ${
                          language === code ? 'text-cyan-400 font-bold bg-cyan-950/40' : 'text-slate-300'
                        }`}
                      >
                        <div>
                          <span>{label.native}</span>
                          <span className="text-[10px] text-slate-500 ml-1.5">({label.name})</span>
                        </div>
                        {language === code && <Check className="w-3.5 h-3.5 text-cyan-400" />}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Official INCOIS Emblem Logo */}
          <IncoisLogo className="w-8 h-8 sm:w-9 sm:h-9" />

          {/* User Profile Avatar & Dropdown Menu */}
          <div className="relative">
            <button
              onClick={() => setUserDropdownOpen(!userDropdownOpen)}
              className="flex items-center gap-1.5 p-1 rounded-lg hover:bg-white/10 transition-colors border border-transparent hover:border-slate-700 focus:outline-none"
              title="User Profile & Logout"
              aria-label="User Profile"
            >
              <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-gradient-to-tr from-cyan-700 to-blue-600 border border-cyan-400 flex items-center justify-center text-white font-bold text-xs shadow-sm">
                {profile?.full_name ? profile.full_name.charAt(0).toUpperCase() : '🐋'}
              </div>
              <div className="hidden lg:flex flex-col text-left leading-none pr-1">
                <span className="text-[11px] font-semibold text-white max-w-[110px] truncate">
                  {profile?.full_name || (isGuest ? 'Guest' : 'Navigator')}
                </span>
                <span className="text-[9px] text-cyan-300 font-mono mt-0.5">
                  {profile?.user_role || 'FISHERMAN'}
                </span>
              </div>
            </button>

            {/* Profile Dropdown Menu */}
            {userDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setUserDropdownOpen(false)}
                />
                <div className="absolute right-0 mt-2 w-64 rounded-xl bg-slate-900 border border-slate-700 shadow-2xl py-2 z-50 animate-in fade-in zoom-in-95 duration-150 text-xs">
                  {/* User Overview */}
                  <div className="px-3.5 py-2.5 border-b border-slate-800">
                    <div className="font-bold text-white text-sm truncate">
                      {profile?.full_name || 'ORCA Navigator'}
                    </div>
                    <div className="text-[11px] text-slate-400 truncate mt-0.5">
                      {isGuest ? 'Guest Session' : user?.email || profile?.email || 'Authenticated'}
                    </div>
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded-md bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 text-[10px] font-bold font-mono">
                        {profile?.user_role || 'FISHERMAN'}
                      </span>
                      {isGuest && (
                        <span className="px-2 py-0.5 rounded-md bg-amber-950/80 border border-amber-500/40 text-amber-300 text-[10px] font-semibold">
                          Guest
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Harbour & Language Indicators */}
                  <div className="px-3.5 py-2 border-b border-slate-800 text-[11px] space-y-1 text-slate-300">
                    <div className="flex items-center gap-1.5 text-slate-400">
                      <Anchor className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
                      <span className="truncate">{landingCentre?.name || profile?.preferred_harbor || 'Kasimedu Harbour'}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="pt-1">
                    <button
                      onClick={() => {
                        setUserDropdownOpen(false);
                        setProfileModalOpen(true);
                      }}
                      className="w-full text-left px-3.5 py-2 flex items-center gap-2 text-slate-200 hover:bg-slate-800 hover:text-cyan-300 transition-colors"
                    >
                      <UserIcon className="w-4 h-4 text-cyan-400" />
                      <span>Profile & Preferences</span>
                    </button>

                    <button
                      onClick={() => {
                        setUserDropdownOpen(false);
                        setSettingsOpen(true);
                      }}
                      className="w-full text-left px-3.5 py-2 flex items-center gap-2 text-slate-200 hover:bg-slate-800 hover:text-white transition-colors sm:hidden"
                    >
                      <Settings className="w-4 h-4 text-slate-400" />
                      <span>System Settings</span>
                    </button>

                    <button
                      onClick={async () => {
                        setUserDropdownOpen(false);
                        await signOut();
                      }}
                      className="w-full text-left px-3.5 py-2 flex items-center gap-2 text-rose-400 hover:bg-rose-950/40 transition-colors border-t border-slate-800/80 mt-1"
                    >
                      <LogOut className="w-4 h-4 text-rose-400" />
                      <span className="font-semibold">Sign Out</span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Settings button */}
          <button
            onClick={() => setSettingsOpen(true)}
            className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-white/10 transition-colors hidden sm:block"
            title="System Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <UserProfileModal open={profileModalOpen} onClose={() => setProfileModalOpen(false)} />
      <BackendStatusModal
        open={backendModalOpen}
        onClose={() => setBackendModalOpen(false)}
        onStatusChange={(c) => setBackendConnected(c)}
      />
    </>
  );
}
