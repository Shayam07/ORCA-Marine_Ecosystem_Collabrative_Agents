import { useState, useEffect } from 'react';
import Header from './components/Header';
import NavigationDrawer from './components/NavigationDrawer';
import MapView from './components/MapView';
import IncoisAlertsSelector from './components/IncoisAlertsSelector';
import IncoisThreatLegend from './components/IncoisThreatLegend';
import IncoisTimelineBar from './components/IncoisTimelineBar';
import PFZBottomPanel from './components/PFZBottomPanel';
import RoutePlanningPanel from './components/RoutePlanningPanel';
import BottomModeDock from './components/BottomModeDock';
import FloatingAIAssistant from './components/FloatingAIAssistant';
import OfflineBanner from './components/OfflineBanner';
import { MarineProvider, useMarineContext } from './context/MarineContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import AuthScreen from './components/auth/AuthScreen';
import { INDIAN_LANDING_CENTRES } from './data/landingCentres';
import { AlertTriangle, X } from 'lucide-react';
import './index.css';

function OperationalWorkspace() {
  const {
    location,
    zones,
    setLocation,
    setSelectedZone,
    operationalMode,
    setOperationalMode,
    isOffline,
    layers,
    setLayers,
  } = useMarineContext();

  const [activeIncoisMode, setActiveIncoisMode] = useState<string>('WINDS');
  const [showOrcaTools, setShowOrcaTools] = useState<boolean>(false);

  const bbox: [number, number, number, number] = location
    ? [location.lon - 1.5, location.lat - 1.5, location.lon + 1.5, location.lat + 1.5]
    : [78, 11, 82, 15];

  const mapCenter: [number, number] = location
    ? [location.lon, location.lat]
    : [78.5, 14.8];

  const handleAlertModeChange = (modeId: string) => {
    // If clicking the active layer or 'NONE', turn OFF the grid box overlay
    if (modeId === activeIncoisMode || modeId === 'NONE') {
      setActiveIncoisMode('NONE');
      setLayers((prev) => prev.filter((l) => !['wind', 'waves', 'currents', 'sst', 'chlorophyll'].includes(l)));
      return;
    }

    setActiveIncoisMode(modeId);
    const targetField =
      modeId === 'WINDS'
        ? 'wind'
        : modeId === 'CURRENTS'
        ? 'currents'
        : 'waves';

    if (modeId === 'WINDS') {
      setOperationalMode('WINDS');
    } else if (modeId === 'CURRENTS') {
      setOperationalMode('CURRENTS');
    } else if (modeId === 'HIGH_WAVES') {
      setOperationalMode('HIGH_WAVES');
    } else {
      setOperationalMode('OSF');
    }
    setLayers((prev) => [...prev.filter((l) => !['wind', 'waves', 'currents', 'sst', 'chlorophyll'].includes(l)), targetField]);
  };

  const isAlertMode =
    activeIncoisMode === 'OSF' ||
    activeIncoisMode === 'HIGH_WAVES' ||
    activeIncoisMode === 'SWELL' ||
    operationalMode === 'OSF' ||
    operationalMode === 'HIGH_WAVES';

  return (
    <div className="h-screen w-screen bg-[#1f242d] text-slate-900 flex flex-col overflow-hidden font-sans select-none">
      {/* 1. Official INCOIS Top App Bar (Matching Screenshots 1 & 2) */}
      <Header />

      {/* Offline Status Warning Banner */}
      <OfflineBanner isOffline={isOffline} />

      {/* 2. Slide-out Operational Navigation Drawer */}
      <NavigationDrawer />

      {/* 3. Main Workspace: Full-screen Esri World Topo Map */}
      <div className="flex-1 relative overflow-hidden">
        <MapView
          bbox={bbox}
          activeLayer={layers[0]}
          center={mapCenter}
          pfzZones={zones}
          onLocationSelect={setLocation}
          onZoneSelect={setSelectedZone}
        />

        {/* 4. INCOIS Active Alerts Selector (Floating Top-Right Card - Screenshot 2) */}
        <IncoisAlertsSelector
          activeMode={activeIncoisMode}
          onModeChange={handleAlertModeChange}
        />

        {/* 5. INCOIS Threat Status Legend (Floating Bottom-Right Card - Screenshot 2) */}
        {isAlertMode && <IncoisThreatLegend />}

        {/* 6. INCOIS Bottom Timeline Playback Bar & Integrated Color Scale Bar (Screenshots 1 & 2) */}
        <IncoisTimelineBar activeMode={activeIncoisMode} />

        {/* 7. ORCA Advisory Panels (when in Route or PFZ modes) */}
        {operationalMode === 'PFZ' && <PFZBottomPanel />}
        {operationalMode === 'ROUTE' && <RoutePlanningPanel />}

        {/* 8. Collapsible ORCA Pro Dock Toggle */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20">
          <button
            onClick={() => setShowOrcaTools(!showOrcaTools)}
            className="px-2.5 py-1 rounded-full text-[11px] font-bold shadow-md backdrop-blur-md border transition-all flex items-center gap-1.5 bg-slate-900/80 text-cyan-300 border-cyan-500/40 hover:bg-slate-900"
          >
            <span>🐋</span>
            <span>{showOrcaTools ? 'Hide ORCA Tools' : 'ORCA Tools'}</span>
          </button>
        </div>

        {/* 9. ORCA Pro Dock & AI Assistant (Visible when toggled) */}
        {showOrcaTools && (
          <>
            <BottomModeDock />
            <FloatingAIAssistant />
          </>
        )}
      </div>
    </div>
  );
}

function AuthenticatedApp() {
  const { user, profile, loading, isGuest, sessionExpired, clearSessionExpired, isPasswordRecovery } = useAuth();
  const { setLanguage, setLandingCentre } = useMarineContext();

  // Restore user preferences into MarineContext automatically
  useEffect(() => {
    if (profile?.preferred_language) {
      setLanguage(profile.preferred_language);
    }
    if (profile?.preferred_harbor) {
      const match = INDIAN_LANDING_CENTRES.find(
        (c) => c.name.toLowerCase() === profile.preferred_harbor.toLowerCase() ||
               c.id.toLowerCase() === profile.preferred_harbor.toLowerCase()
      );
      if (match) {
        setLandingCentre(match);
      }
    }
  }, [profile, setLanguage, setLandingCentre]);

  // Loading state during initial session check
  if (loading) {
    return (
      <div className="h-screen w-screen bg-[#0a0f1d] text-white flex flex-col items-center justify-center select-none">
        <div className="relative mb-4">
          <div className="w-16 h-16 rounded-2xl bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-3xl shadow-xl shadow-cyan-950/50 animate-pulse">
            🐋
          </div>
          <div className="absolute -inset-1 rounded-2xl bg-cyan-500/20 blur-md -z-10 animate-ping" />
        </div>
        <h2 className="text-base font-bold text-slate-200 tracking-wide">ORCA Marine Intelligence</h2>
        <p className="text-xs text-cyan-400 mt-1">Connecting secure marine session...</p>
        <div className="w-32 h-1 bg-slate-800 rounded-full mt-4 overflow-hidden">
          <div className="w-full h-full bg-gradient-to-r from-cyan-500 to-blue-500 animate-[pulse_1.5s_infinite]" />
        </div>
      </div>
    );
  }

  // Password recovery mode OR not authenticated & not guest -> Show auth screen
  if (isPasswordRecovery || (!user && !isGuest)) {
    return (
      <div className="relative">
        {sessionExpired && (
          <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-11/12 max-w-md p-3 rounded-xl bg-amber-950/90 border border-amber-500 text-amber-200 text-xs flex items-center justify-between shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <span>Your session has expired. Please sign in again to continue.</span>
            </div>
            <button
              onClick={clearSessionExpired}
              className="p-1 text-amber-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
        <AuthScreen />
      </div>
    );
  }

  // Authenticated workspace
  return <OperationalWorkspace />;
}

export default function App() {
  return (
    <AuthProvider>
      <MarineProvider>
        <AuthenticatedApp />
      </MarineProvider>
    </AuthProvider>
  );
}
