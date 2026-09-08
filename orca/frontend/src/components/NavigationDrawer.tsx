import { useState } from 'react';
import {
  X,
  Fish,
  Waves,
  Wind,
  Compass,
  AlertTriangle,
  ShieldCheck,
  PhoneCall,
  MapPin,
  Check,
  ChevronRight,
  Radio,
  ExternalLink,
  Layers,
  Sparkles,
  Route,
} from 'lucide-react';
import { useMarineContext, type OperationalMode } from '../context/MarineContext';
import { useAuth } from '../context/AuthContext';
import { INDIAN_LANDING_CENTRES } from '../data/landingCentres';
import { LogOut, User as UserIcon } from 'lucide-react';

export default function NavigationDrawer() {
  const {
    drawerOpen,
    setDrawerOpen,
    operationalMode,
    setOperationalMode,
    landingCentre,
    setLandingCentre,
    setAiAssistantOpen,
  } = useMarineContext();

  const { profile, user, signOut, isGuest } = useAuth();

  const [selectedState, setSelectedState] = useState<string>('All');
  const [centreSearch, setCentreSearch] = useState<string>('');

  if (!drawerOpen) return null;

  const states = ['All', 'Tamil Nadu', 'Kerala', 'Andhra Pradesh', 'Maharashtra', 'Gujarat', 'Karnataka', 'Odisha', 'West Bengal', 'Goa', 'Andaman and Nicobar'];

  const filteredCentres = INDIAN_LANDING_CENTRES.filter((c) => {
    const matchesState = selectedState === 'All' || c.state === selectedState;
    const matchesSearch = c.name.toLowerCase().includes(centreSearch.toLowerCase()) ||
                          c.district.toLowerCase().includes(centreSearch.toLowerCase()) ||
                          c.state.toLowerCase().includes(centreSearch.toLowerCase());
    return matchesState && matchesSearch;
  });

  const modes: Array<{
    id: OperationalMode;
    label: string;
    description: string;
    icon: any;
    color: string;
  }> = [
    {
      id: 'PFZ',
      label: 'Potential Fishing Zone (PFZ)',
      description: 'Satellite thermal & chlorophyll fronts for pelagic fish',
      icon: Fish,
      color: 'text-emerald-400',
    },
    {
      id: 'OSF',
      label: 'Ocean State Forecast (OSF)',
      description: 'Wave height, sea surface temperature & marine forecast',
      icon: Waves,
      color: 'text-cyan-400',
    },
    {
      id: 'HIGH_WAVES',
      label: 'High Wave & Swell Alert',
      description: 'Threat status matrix: Warning, Alert, Watch, No Threat',
      icon: AlertTriangle,
      color: 'text-amber-400',
    },
    {
      id: 'ROUTE',
      label: 'Space-Time Route Optimization',
      description: 'A* corridor avoiding high waves, IMBL & shoals',
      icon: Route,
      color: 'text-cyan-300',
    },
    {
      id: 'WINDS',
      label: 'Ocean Surface Winds',
      description: 'Streamline vector flow & surface wind intensity',
      icon: Wind,
      color: 'text-blue-400',
    },
    {
      id: 'CURRENTS',
      label: 'Ocean Currents & Flow',
      description: 'HYCOM velocity fields & surface drift trajectories',
      icon: Compass,
      color: 'text-indigo-400',
    },
    {
      id: 'SAFETY',
      label: 'IMBL & Maritime Geofencing',
      description: 'International boundary alerts & MPA protected zones',
      icon: ShieldCheck,
      color: 'text-rose-400',
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm transition-opacity"
        onClick={() => setDrawerOpen(false)}
      />

      {/* Drawer Body */}
      <div className="relative w-full max-w-md bg-slate-900 text-slate-100 h-full shadow-2xl flex flex-col z-10 border-r border-slate-800 animate-in slide-in-from-left duration-200">
        {/* Drawer Header */}
        <div className="px-5 py-4 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-cyan-600/30 border border-cyan-500/40 flex items-center justify-center text-lg">
              🐋
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-base tracking-wider text-white">ORCA SAMUDRA</span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-950 border border-cyan-500/50 text-cyan-300">
                  OPERATIONAL
                </span>
              </div>
              <p className="text-[11px] text-slate-400">INCOIS & MoES Ocean Intelligence Portal</p>
            </div>
          </div>
          <button
            onClick={() => setDrawerOpen(false)}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6">
          {/* Section 1: Operational Visualization Modes */}
          <div>
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2 px-1">
              Operational Visualization Modes
            </h3>
            <div className="space-y-1.5">
              {modes.map((mode) => {
                const Icon = mode.icon;
                const active = operationalMode === mode.id;
                return (
                  <button
                    key={mode.id}
                    onClick={() => {
                      setOperationalMode(mode.id);
                      setDrawerOpen(false);
                    }}
                    className={`w-full text-left p-3 rounded-xl flex items-center gap-3.5 transition-all ${
                      active
                        ? 'bg-cyan-950/70 border border-cyan-500/60 shadow-lg shadow-cyan-950/40 text-white'
                        : 'bg-slate-800/50 border border-slate-800/80 hover:bg-slate-800 hover:border-slate-700 text-slate-300'
                    }`}
                  >
                    <div
                      className={`p-2 rounded-lg ${
                        active ? 'bg-cyan-500/20 text-cyan-300' : 'bg-slate-900/80 ' + mode.color
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-bold text-xs text-white">{mode.label}</div>
                      <div className="text-[10px] text-slate-400 truncate">{mode.description}</div>
                    </div>
                    {active && <Check className="w-4 h-4 text-cyan-400 flex-shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Section 2: Fish Landing Centre (FLC) Directory */}
          <div className="border-t border-slate-800 pt-5">
            <div className="flex items-center justify-between mb-2 px-1">
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Fish Landing Centres (FLC)
              </h3>
              <span className="text-[10px] text-cyan-400 font-semibold">{filteredCentres.length} Centres</span>
            </div>

            {/* State filter chips */}
            <div className="flex gap-1.5 overflow-x-auto pb-2 mb-2 scrollbar-none">
              {states.map((st) => (
                <button
                  key={st}
                  onClick={() => setSelectedState(st)}
                  className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold whitespace-nowrap transition-colors ${
                    selectedState === st
                      ? 'bg-cyan-600 text-white shadow-sm'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <input
              type="text"
              placeholder="Search landing harbour, district..."
              value={centreSearch}
              onChange={(e) => setCentreSearch(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 mb-2"
            />

            {/* Centres list */}
            <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
              {filteredCentres.map((c) => {
                const isSelected = landingCentre.id === c.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => {
                      setLandingCentre(c);
                      setDrawerOpen(false);
                    }}
                    className={`w-full text-left p-2.5 rounded-lg flex items-center justify-between text-xs transition-colors ${
                      isSelected
                        ? 'bg-emerald-950/60 border border-emerald-500/50 text-emerald-300 font-bold'
                        : 'bg-slate-950/50 hover:bg-slate-800/80 border border-slate-900 text-slate-300'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <MapPin className={`w-3.5 h-3.5 flex-shrink-0 ${isSelected ? 'text-emerald-400' : 'text-slate-500'}`} />
                      <div className="truncate">
                        <div>{c.name}</div>
                        <div className="text-[10px] text-slate-500 font-normal">
                          {c.district}, {c.state} • {c.depth_m}m depth
                        </div>
                      </div>
                    </div>
                    {isSelected && <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 ml-2" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Section 3: Emergency & Marine Help Desk */}
          <div className="border-t border-slate-800 pt-5">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-rose-400 mb-2 px-1 flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-rose-500 animate-pulse" />
              Emergency & Coast Guard Hotlines
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <a
                href="tel:1554"
                className="p-2.5 rounded-xl bg-rose-950/40 border border-rose-500/30 flex items-center gap-2 hover:bg-rose-900/40 transition-colors text-white"
              >
                <PhoneCall className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <div>
                  <div className="text-[10px] text-slate-400">Coast Guard SAR</div>
                  <div className="font-extrabold text-sm text-rose-300">1554</div>
                </div>
              </a>

              <a
                href="tel:1093"
                className="p-2.5 rounded-xl bg-amber-950/40 border border-amber-500/30 flex items-center gap-2 hover:bg-amber-900/40 transition-colors text-white"
              >
                <PhoneCall className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <div>
                  <div className="text-[10px] text-slate-400">Coastal Police</div>
                  <div className="font-extrabold text-sm text-amber-300">1093</div>
                </div>
              </a>
            </div>
          </div>

          {/* Section 4: Authenticated User Account */}
          <div className="border-t border-slate-800 pt-4 pb-2">
            <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-700/60 flex items-center justify-between">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-full bg-cyan-700/50 border border-cyan-400 flex items-center justify-center text-white font-bold text-xs flex-shrink-0">
                  {profile?.full_name ? profile.full_name.charAt(0).toUpperCase() : '🐋'}
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-bold text-white truncate">
                    {profile?.full_name || 'ORCA Navigator'}
                  </div>
                  <div className="text-[10px] text-cyan-400 font-mono flex items-center gap-1.5">
                    <span>{profile?.user_role || 'FISHERMAN'}</span>
                    {isGuest && <span className="text-amber-400 font-sans">• Guest</span>}
                  </div>
                </div>
              </div>

              <button
                onClick={async () => {
                  setDrawerOpen(false);
                  await signOut();
                }}
                className="p-1.5 rounded-lg bg-rose-950/60 border border-rose-500/40 text-rose-300 hover:bg-rose-900/70 transition-colors flex-shrink-0"
                title="Sign Out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Drawer Footer: Open AI Assistant Button */}
        <div className="p-4 bg-slate-950 border-t border-slate-800 flex items-center justify-between">
          <button
            onClick={() => {
              setDrawerOpen(false);
              setAiAssistantOpen(true);
            }}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold text-xs shadow-lg shadow-cyan-600/30 hover:from-cyan-500 hover:to-blue-500 transition-all"
          >
            <Sparkles className="w-4 h-4" />
            <span>Launch ORCA AI Assistant & Voice</span>
          </button>
        </div>
      </div>
    </div>
  );
}
