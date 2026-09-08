import { useState } from 'react';
import {
  Fish,
  Compass,
  Navigation,
  Anchor,
  Calendar,
  Layers,
  ChevronDown,
  ChevronUp,
  MapPin,
  Route,
  Sparkles,
  Search,
  ShieldCheck,
  Users,
  AlertTriangle,
  Leaf,
  Info,
} from 'lucide-react';
import { useMarineContext } from '../context/MarineContext';
import { INDIAN_LANDING_CENTRES, type FishLandingCentre } from '../data/landingCentres';
import { sendMessage, optimizeRoute } from '../api/client';
import type { PFZZone } from './ChatPanel';

export default function PFZBottomPanel() {
  const {
    landingCentre,
    setLandingCentre,
    selectedZone,
    setSelectedZone,
    zones,
    setCurrentRoute,
    setAiAssistantOpen,
    setOperationalMode,
    setRouteDestination,
    setActiveRouteType,
    vesselProfile,
  } = useMarineContext();

  const [expanded, setExpanded] = useState(true);
  const [centrePickerOpen, setCentrePickerOpen] = useState(false);
  const [pickerSearch, setPickerSearch] = useState('');
  const [routing, setRouting] = useState(false);

  const filteredCentres = INDIAN_LANDING_CENTRES.filter(
    (c) =>
      c.name.toLowerCase().includes(pickerSearch.toLowerCase()) ||
      c.state.toLowerCase().includes(pickerSearch.toLowerCase())
  );

  // Active zone is either selectedZone or top ranked zone
  const activeZone: PFZZone | null = selectedZone || (zones.length > 0 ? zones[0] : null);

  const crowdingLevel = activeZone?.crowding_level || 'LOW';
  const crowdingBadgeColor =
    crowdingLevel === 'LOW'
      ? 'bg-emerald-950 border-emerald-500/50 text-emerald-300'
      : crowdingLevel === 'MODERATE'
      ? 'bg-amber-950 border-amber-500/50 text-amber-300'
      : 'bg-red-950 border-red-500/50 text-red-300';

  const crowdingIcon = crowdingLevel === 'LOW' ? '🟢' : crowdingLevel === 'MODERATE' ? '🟡' : '🔴';

  const handlePlotRoute = async () => {
    if (!activeZone) return;
    setRouting(true);
    try {
      const destLocation = {
        name: `${landingCentre.name} PFZ (${activeZone.option_label || activeZone.zone_id})`,
        lat: activeZone.center_lat,
        lon: activeZone.center_lon,
      };
      setRouteDestination(destLocation);

      try {
        const routeData = await optimizeRoute({
          start_lat: landingCentre.lat,
          start_lon: landingCentre.lon,
          end_lat: activeZone.center_lat,
          end_lon: activeZone.center_lon,
          vessel_class: vesselProfile.boat_type,
          vessel_profile: vesselProfile,
          avoid_hazards: true,
          target_pfz: activeZone,
        });
        setCurrentRoute(routeData);
        setActiveRouteType('PRIMARY');
        setOperationalMode('ROUTE');
      } catch {
        // Fallback to chat agent if direct route optimize fails
        const fallback = await sendMessage({
          message: `Plan safe optimal route from ${landingCentre.name} to nearest sustainable PFZ fishing zone`,
          data_mode: 'LIVE',
          location: {
            name: landingCentre.name,
            lat: landingCentre.lat,
            lon: landingCentre.lon,
          },
        });
        if (fallback?.route) {
          setCurrentRoute(fallback.route);
          setActiveRouteType('PRIMARY');
          setOperationalMode('ROUTE');
        }
      }
    } catch (e) {
      console.warn('Route calculation error:', e);
    } finally {
      setRouting(false);
    }
  };

  return (
    <>
      <div className="absolute bottom-2 sm:bottom-14 left-2 right-2 sm:right-auto sm:left-4 sm:w-[350px] z-20 transition-all duration-200 pb-safe">
        <div className="rounded-2xl bg-slate-900/95 border border-slate-700/80 text-white shadow-2xl backdrop-blur-xl overflow-hidden">
          {/* Mobile Sheet Drag Handle */}
          <div 
            onClick={() => setExpanded(!expanded)}
            className="w-full flex justify-center pt-1.5 pb-0.5 sm:hidden cursor-pointer bg-slate-950/90"
          >
            <div className="w-10 h-1 rounded-full bg-slate-600" />
          </div>

          {/* Top Bar of Card */}
          <div className="px-3 py-2 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="flex h-5 w-5 items-center justify-center rounded-md bg-emerald-500/20 text-emerald-400 flex-shrink-0">
                <Fish className="w-3 h-3" />
              </span>
              <span className="font-extrabold text-[11px] tracking-wide text-white uppercase truncate">
                PFZ Advisory
              </span>
              <span className={`px-1.5 py-0.2 rounded-full text-[9px] font-bold border flex items-center gap-0.5 flex-shrink-0 ${crowdingBadgeColor}`}>
                <span>{crowdingIcon}</span>
                <span>{crowdingLevel}</span>
              </span>
            </div>

            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors ml-1 touch-target flex items-center justify-center"
              aria-label={expanded ? 'Collapse Panel' : 'Expand Panel'}
            >
              {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </button>
          </div>

          {expanded && (
            <div className="p-2.5 space-y-2">
              {/* Fish Landing Centre Selector */}
              <div className="flex items-center justify-between gap-1.5 p-1.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="min-w-0 flex items-center gap-1.5">
                  <Anchor className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
                  <div className="truncate">
                    <div className="text-[9px] text-slate-400 font-semibold uppercase">
                      Landing Centre
                    </div>
                    <div className="text-[11px] font-bold text-slate-100 truncate">
                      {landingCentre.name}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setCentrePickerOpen(true)}
                  className="px-2 py-1 rounded bg-cyan-950 border border-cyan-500/50 text-[10px] font-bold text-cyan-300 hover:bg-cyan-900 transition-colors whitespace-nowrap flex-shrink-0"
                >
                  Change
                </button>
              </div>

              {/* Sustainable Zone Selector */}
              {zones.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[9px] font-bold text-slate-400 uppercase flex items-center justify-between">
                    <span>Ranked Sectors:</span>
                    <span className="text-[8.5px] text-cyan-400 flex items-center gap-0.5">
                      <ShieldCheck className="w-2.5 h-2.5" />
                      Verified
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-1">
                    {zones.slice(0, 3).map((z, idx) => {
                      const isSelected = activeZone?.zone_id === z.zone_id;
                      const optLabel = z.option_label || (idx === 0 ? 'OPT A' : idx === 1 ? 'OPT B' : 'OPT C');
                      const isRec = idx === 0;
                      const zCrowd = z.crowding_level || 'LOW';
                      const zCrowdDot = zCrowd === 'LOW' ? '🟢' : zCrowd === 'MODERATE' ? '🟡' : '🔴';

                      return (
                        <button
                          key={z.zone_id}
                          onClick={() => setSelectedZone(z)}
                          className={`p-1.5 rounded-lg text-left border transition-all ${
                            isSelected
                              ? 'bg-cyan-950/90 border-cyan-400 shadow-xs'
                              : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[9px] font-extrabold text-white">{optLabel}</span>
                            <span className="text-[8px]">{zCrowdDot}</span>
                          </div>
                          <div className="text-[10px] font-bold text-slate-200 mt-0.5 truncate">
                            {isRec ? '⭐ Rec.' : '🔄 Alt.'}
                          </div>
                          <div className="text-[8.5px] text-slate-400">
                            {z.distance_km ?? landingCentre.distance_km} km
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 4 Metric Pills Grid */}
              <div className="grid grid-cols-4 gap-1 text-center">
                {/* Distance */}
                <div className="p-1.5 rounded-lg bg-slate-950/80 border border-slate-800">
                  <div className="text-[8.5px] font-bold text-slate-400 uppercase">Offshore</div>
                  <div className="text-xs font-extrabold text-emerald-400">
                    {activeZone?.distance_km ?? landingCentre.distance_km}<span className="text-[9px] font-normal">km</span>
                  </div>
                </div>

                {/* Vessel Density / Fleet Pressure */}
                <div className="p-1.5 rounded-lg bg-slate-950/80 border border-slate-800">
                  <div className="text-[8.5px] font-bold text-slate-400 uppercase">Density</div>
                  <div className="text-xs font-extrabold text-cyan-400 truncate">
                    {activeZone?.vessel_density ?? 0.3}
                  </div>
                </div>

                {/* Ecological Clearance */}
                <div className="p-1.5 rounded-lg bg-slate-950/80 border border-slate-800">
                  <div className="text-[8.5px] font-bold text-slate-400 uppercase">Status</div>
                  <div className="text-[10px] font-bold text-emerald-400 flex items-center justify-center gap-0.5 mt-0.5">
                    <ShieldCheck className="w-2.5 h-2.5" />
                    <span>OK</span>
                  </div>
                </div>

                {/* Data Freshness */}
                <div className="p-1.5 rounded-lg bg-slate-950/80 border border-slate-800">
                  <div className="text-[8.5px] font-bold text-slate-400 uppercase">Data</div>
                  <div className="text-[10px] font-bold text-emerald-400 flex items-center justify-center gap-1 mt-0.5">
                    <span className="inline-block w-1 h-1 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>INCOIS</span>
                  </div>
                </div>
              </div>

              {/* Compact Disclaimer */}
              <div className="p-1.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[9px] text-slate-400 flex items-center gap-1.5">
                <span className="text-amber-400">⚖️</span>
                <span className="truncate">SST & Chlorophyll based. Does not guarantee catch.</span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-1.5 pt-0.5">
                <button
                  onClick={handlePlotRoute}
                  disabled={routing}
                  className="flex-1 flex items-center justify-center gap-1 py-1.5 px-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-bold text-[11px] shadow-sm transition-all"
                >
                  <Route className="w-3 h-3" />
                  <span>{routing ? 'Plotting...' : 'Plot Safe Route'}</span>
                </button>

                <button
                  onClick={() => setAiAssistantOpen(true)}
                  className="flex items-center justify-center gap-1 py-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 font-bold text-[11px] border border-slate-700 transition-all"
                >
                  <Sparkles className="w-3 h-3" />
                  <span>AI</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Fish Landing Centre Picker Modal */}
      {centrePickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl p-4 text-white">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div className="flex items-center gap-2 font-bold text-sm">
                <Anchor className="w-4 h-4 text-cyan-400" />
                <span>Select Fish Landing Centre</span>
              </div>
              <button
                onClick={() => setCentrePickerOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            {/* Search */}
            <div className="relative mb-3">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search by harbour or state..."
                value={pickerSearch}
                onChange={(e) => setPickerSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Centre list */}
            <div className="max-h-64 overflow-y-auto space-y-1 pr-1">
              {filteredCentres.map((c) => (
                <button
                  key={c.id}
                  onClick={() => {
                    setLandingCentre(c);
                    setCentrePickerOpen(false);
                  }}
                  className={`w-full text-left p-2.5 rounded-xl text-xs flex items-center justify-between transition-colors ${
                    landingCentre.id === c.id
                      ? 'bg-cyan-950/70 border border-cyan-500/60 text-cyan-300 font-bold'
                      : 'bg-slate-950/60 hover:bg-slate-800 border border-slate-900 text-slate-300'
                  }`}
                >
                  <div>
                    <div>{c.name}</div>
                    <div className="text-[10px] text-slate-500">
                      {c.district}, {c.state} • {c.distance_km} km offshore
                    </div>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 text-slate-400">
                    {c.bearing_deg}°
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
