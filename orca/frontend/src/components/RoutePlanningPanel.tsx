import { useState, useMemo } from 'react';
import {
  Navigation,
  MapPin,
  Anchor,
  Compass,
  ShieldCheck,
  Fuel,
  Clock,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Sparkles,
  Search,
  Check,
  Crosshair,
  Route,
} from 'lucide-react';
import { useMarineContext } from '../context/MarineContext';
import { INDIAN_LANDING_CENTRES } from '../data/landingCentres';
import { DEFAULT_VESSEL_PROFILES } from '../utils/offlineStorage';
import { getDevicePosition } from '../utils/nativeLocation';
import { optimizeRoute, ApiError } from '../api/client';

export default function RoutePlanningPanel() {
  const {
    landingCentre,
    setLandingCentre,
    routeOrigin,
    setRouteOrigin,
    routeDestination,
    setRouteDestination,
    isPickingDestinationOnMap,
    setIsPickingDestinationOnMap,
    currentRoute,
    setCurrentRoute,
    activeRouteType,
    setActiveRouteType,
    vesselProfile,
    setVesselProfile,
    dataMode,
  } = useMarineContext();

  const [expanded, setExpanded] = useState(true);
  const [loading, setLoading] = useState(false);
  const [avoidHazards, setAvoidHazards] = useState<boolean>(true);
  const [originModalOpen, setOriginModalOpen] = useState(false);
  const [destModalOpen, setDestModalOpen] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Compute nearest coastal harbor to origin
  const nearestHarbor = useMemo(() => {
    if (!routeOrigin) return { ...INDIAN_LANDING_CENTRES[0], distance_km: 0 };
    let minD = Infinity;
    let best = INDIAN_LANDING_CENTRES[0];
    for (const h of INDIAN_LANDING_CENTRES) {
      const R = 6371;
      const dLat = ((h.lat - routeOrigin.lat) * Math.PI) / 180;
      const dLon = ((h.lon - routeOrigin.lon) * Math.PI) / 180;
      const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos((routeOrigin.lat * Math.PI) / 180) *
          Math.cos((h.lat * Math.PI) / 180) *
          Math.sin(dLon / 2) ** 2;
      const d = R * 2 * Math.asin(Math.sqrt(a));
      if (d < minD) {
        minD = d;
        best = h;
      }
    }
    return { ...best, distance_km: Math.round(minD) };
  }, [routeOrigin]);

  const isInlandOrigin = nearestHarbor.distance_km > 12;

  const handleCalculateRoute = async () => {
    if (!routeOrigin) return;
    setLoading(true);
    setErrorMessage(null);

    const dest = routeDestination || {
      name: `${landingCentre.name} PFZ Core`,
      lat: routeOrigin.lat + 0.18,
      lon: routeOrigin.lon + 0.26,
    };
    if (!routeDestination) {
      setRouteDestination(dest);
    }

    try {
      const data = await optimizeRoute({
        start_lat: routeOrigin.lat,
        start_lon: routeOrigin.lon,
        end_lat: dest.lat,
        end_lon: dest.lon,
        vessel_class: vesselProfile.boat_type,
        vessel_profile: vesselProfile,
        avoid_hazards: avoidHazards,
        origin: routeOrigin,
        destination: dest,
      });

      setCurrentRoute(data);
      setActiveRouteType('PRIMARY');
    } catch (err: any) {
      console.error('Route calculation failed:', err);
      const msg = err instanceof ApiError ? err.message : 'Unable to optimize route. Verify marine network connection.';
      setErrorMessage(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleUseGPS = async () => {
    try {
      const pos = await getDevicePosition();
      setRouteOrigin({
        name: 'GPS Vessel Position',
        lat: parseFloat(pos.latitude.toFixed(4)),
        lon: parseFloat(pos.longitude.toFixed(4)),
      });
    } catch {
      // Fallback to active landing centre
      setRouteOrigin({
        name: landingCentre.name,
        lat: landingCentre.lat,
        lon: landingCentre.lon,
      });
    }
  };

  const handleClearRoute = () => {
    setCurrentRoute(null);
    setIsPickingDestinationOnMap(false);
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

          {/* Header */}
          <div className="px-3 py-2 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-md bg-cyan-500/20 text-cyan-400">
                <Route className="w-3 h-3" />
              </span>
              <span className="font-extrabold text-[11px] tracking-wide text-white uppercase">
                Route Engine
              </span>
              <span className="px-1.5 py-0.2 rounded-full text-[8.5px] font-bold bg-cyan-950 border border-cyan-500/40 text-cyan-300">
                Current-Assisted
              </span>
            </div>

            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors touch-target flex items-center justify-center"
              aria-label={expanded ? 'Collapse Panel' : 'Expand Panel'}
            >
              {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </button>
          </div>

          {expanded && (
            <div className="p-2.5 space-y-2">
              {/* Origin & Destination Selector Box */}
              <div className="space-y-1.5 p-2 rounded-lg bg-slate-950/80 border border-slate-800">
                {/* ORIGIN (Departure) */}
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 min-w-0 flex-1">
                    <div className="h-4 w-4 rounded-full bg-emerald-500/20 border border-emerald-500/60 flex items-center justify-center text-[9px] text-emerald-400 font-bold flex-shrink-0">
                      A
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[8.5px] font-bold text-slate-400 uppercase">Origin</div>
                      <div className="text-[11px] font-bold text-slate-100 truncate">
                        {routeOrigin?.name || landingCentre.name}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={handleUseGPS}
                      className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 text-[9px]"
                      title="Use GPS"
                    >
                      <Crosshair className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => setOriginModalOpen(true)}
                      className="px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-[9px] font-bold text-slate-200"
                    >
                      Change
                    </button>
                  </div>
                </div>

                {/* Inland Location Warning & Action */}
                {isInlandOrigin && (
                  <div className="p-2 rounded-lg bg-amber-950/80 border border-amber-500/60 text-amber-200 text-[10px] space-y-1">
                    <div className="flex items-start gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <div className="font-bold text-[10px] text-amber-300">
                          Inland Location ({nearestHarbor.distance_km} km to coast)
                        </div>
                        <div className="text-[9px] text-slate-300">
                          Switch to coastal harbor: <strong className="text-white">{nearestHarbor.name}</strong>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setLandingCentre(nearestHarbor);
                        setRouteOrigin({
                          name: nearestHarbor.name,
                          lat: nearestHarbor.lat,
                          lon: nearestHarbor.lon,
                        });
                      }}
                      className="w-full py-1 px-2 rounded bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold text-[10px] flex items-center justify-center gap-1"
                    >
                      <Anchor className="w-3 h-3" />
                      <span>Use {nearestHarbor.name}</span>
                    </button>
                  </div>
                )}

                <div className="h-[1px] bg-slate-800 my-0.5" />

                {/* DESTINATION (Target PFZ / Map Point) */}
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 min-w-0 flex-1">
                    <div className="h-4 w-4 rounded-full bg-cyan-500/20 border border-cyan-500/60 flex items-center justify-center text-[9px] text-cyan-400 font-bold flex-shrink-0">
                      B
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[8.5px] font-bold text-slate-400 uppercase">Destination</div>
                      <div className="text-[11px] font-bold text-cyan-200 truncate">
                        {routeDestination?.name || 'PFZ Recommended Zone'}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => {
                        setIsPickingDestinationOnMap(!isPickingDestinationOnMap);
                      }}
                      className={`px-1.5 py-0.5 rounded text-[9px] font-bold transition-all ${
                        isPickingDestinationOnMap
                          ? 'bg-amber-600 text-white animate-pulse'
                          : 'bg-slate-800 hover:bg-slate-700 text-cyan-300'
                      }`}
                      title="Click any point on the map to set destination"
                    >
                      <MapPin className="w-2.5 h-2.5 inline mr-0.5" />
                      {isPickingDestinationOnMap ? 'Clicking...' : 'Pick'}
                    </button>

                    <button
                      onClick={() => setDestModalOpen(true)}
                      className="px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-[9px] font-bold text-slate-200"
                    >
                      Presets
                    </button>
                  </div>
                </div>
              </div>

              {/* Vessel & Hazard Preferences */}
              <div className="flex items-center justify-between gap-1.5 text-xs">
                <div className="flex items-center gap-1 bg-slate-950/60 border border-slate-800 rounded-lg px-2 py-1 flex-1 min-w-0">
                  <span className="text-[9px] text-slate-400 font-semibold flex-shrink-0">Vessel:</span>
                  <select
                    value={vesselProfile.boat_type}
                    onChange={(e) => {
                      const selected = e.target.value;
                      const profile = DEFAULT_VESSEL_PROFILES[selected] || DEFAULT_VESSEL_PROFILES.Motorized;
                      setVesselProfile(profile);
                    }}
                    className="bg-transparent text-slate-200 font-bold text-[10px] focus:outline-none truncate w-full"
                  >
                    <option value="Motorized" className="bg-slate-900">Motorized</option>
                    <option value="Artisanal" className="bg-slate-900">Artisanal</option>
                    <option value="Mechanized Trawler" className="bg-slate-900">Trawler</option>
                  </select>
                </div>

                <button
                  onClick={() => setAvoidHazards(!avoidHazards)}
                  className={`flex items-center gap-0.5 px-2 py-1 rounded-lg border text-[9px] font-bold transition-all flex-shrink-0 ${
                    avoidHazards
                      ? 'bg-emerald-950/70 border-emerald-500/50 text-emerald-300'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400'
                  }`}
                >
                  <ShieldCheck className="w-3 h-3 text-emerald-400" />
                  <span>Safe Sea</span>
                </button>
              </div>

              {/* Action Button: Find Route */}
              <button
                onClick={handleCalculateRoute}
                disabled={loading}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 text-white font-extrabold text-[11px] shadow-sm hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 transition-all"
              >
                <Route className="w-3 h-3" />
                <span>{loading ? 'Simulating Corridor...' : 'Find Safest Route'}</span>
              </button>

              {errorMessage && (
                <div className="p-2 rounded-lg bg-rose-950/60 border border-rose-500/40 text-[11px] text-rose-300 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              {/* Route Results Box */}
              {currentRoute && (
                <div className="p-3 rounded-xl bg-slate-950/90 border border-cyan-500/40 space-y-2.5 animate-in fade-in duration-200">
                  {/* Route Type Tabs: Recommended vs Alternative */}
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <div className="flex items-center gap-1 bg-slate-900 rounded-lg p-0.5 border border-slate-800 text-[10px]">
                      <button
                        onClick={() => setActiveRouteType('PRIMARY')}
                        className={`px-2.5 py-1 rounded-md font-bold transition-all ${
                          activeRouteType === 'PRIMARY'
                            ? 'bg-cyan-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        Recommended
                      </button>
                      <button
                        onClick={() => setActiveRouteType('ALTERNATIVE')}
                        className={`px-2.5 py-1 rounded-md font-bold transition-all ${
                          activeRouteType === 'ALTERNATIVE'
                            ? 'bg-cyan-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        Alternative (+6%)
                      </button>
                    </div>

                    {/* Safety Badge */}
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold border ${
                        (currentRoute.safety_score ?? 90) >= 80
                          ? 'bg-emerald-950 border-emerald-500/50 text-emerald-300'
                          : 'bg-amber-950 border-amber-500/50 text-amber-300'
                      }`}
                    >
                      🛡️ {currentRoute.safety_score ?? 92}/100 {currentRoute.risk_level ?? 'SAFE'}
                    </span>
                  </div>

                  {/* 4 Metric Stats */}
                  <div className="grid grid-cols-4 gap-1 text-center">
                    <div className="p-1.5 rounded-lg bg-slate-900 border border-slate-800">
                      <div className="text-[8px] font-bold text-slate-400 uppercase">Distance</div>
                      <div className="text-xs font-extrabold text-cyan-300">
                        {currentRoute.distance_km} <span className="text-[9px] font-normal">km</span>
                      </div>
                    </div>

                    <div className="p-1.5 rounded-lg bg-slate-900 border border-slate-800">
                      <div className="text-[8px] font-bold text-slate-400 uppercase">ETA</div>
                      <div className="text-xs font-extrabold text-emerald-300">
                        {currentRoute.eta_hours} <span className="text-[9px] font-normal">hrs</span>
                      </div>
                    </div>

                    <div className="p-1.5 rounded-lg bg-slate-900 border border-slate-800">
                      <div className="text-[8px] font-bold text-slate-400 uppercase">Fuel Est.</div>
                      <div className="text-xs font-extrabold text-amber-300">
                        {currentRoute.estimated_diesel_liters} <span className="text-[9px] font-normal">L</span>
                      </div>
                    </div>

                    <div className="p-1.5 rounded-lg bg-slate-900 border border-slate-800">
                      <div className="text-[8px] font-bold text-slate-400 uppercase">Saved</div>
                      <div className="text-xs font-extrabold text-emerald-400">
                        ~{currentRoute.fuel_saved_percent ?? 18}%
                      </div>
                    </div>
                  </div>

                  {/* Warnings List */}
                  {currentRoute.warnings && currentRoute.warnings.length > 0 && (
                    <div className="space-y-1">
                      {currentRoute.warnings.map((w, idx) => (
                        <div
                          key={idx}
                          className="text-[10px] text-slate-300 bg-slate-900/60 rounded-lg px-2 py-1 border border-slate-800/80 leading-relaxed"
                        >
                          {w}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Clear Button */}
                  <div className="flex justify-end pt-1">
                    <button
                      onClick={handleClearRoute}
                      className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-rose-300 font-semibold"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Clear Route Polyline</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Modal: Select Origin */}
      {originModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl p-4 text-white">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-3">
              <div className="flex items-center gap-2 font-bold text-xs">
                <Anchor className="w-4 h-4 text-emerald-400" />
                <span>Select Departure Point</span>
              </div>
              <button onClick={() => setOriginModalOpen(false)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <div className="max-h-60 overflow-y-auto space-y-1 pr-1">
              {INDIAN_LANDING_CENTRES.map((c) => (
                <button
                  key={c.id}
                  onClick={() => {
                    setLandingCentre(c);
                    setRouteOrigin({
                      name: c.name,
                      lat: c.lat,
                      lon: c.lon,
                    });
                    setOriginModalOpen(false);
                  }}
                  className="w-full text-left p-2 rounded-xl text-xs hover:bg-slate-800 flex items-center justify-between text-slate-200"
                >
                  <div>
                    <div>{c.name}</div>
                    <div className="text-[10px] text-slate-500">{c.district}, {c.state}</div>
                  </div>
                  {routeOrigin.name === c.name && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Modal: Select Destination */}
      {destModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl p-4 text-white">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-3">
              <div className="flex items-center gap-2 font-bold text-xs">
                <Compass className="w-4 h-4 text-cyan-400" />
                <span>Select Marine Destination Preset</span>
              </div>
              <button onClick={() => setDestModalOpen(false)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <div className="space-y-1.5">
              {/* Option 1: Recommended PFZ for Current Harbour */}
              <button
                onClick={() => {
                  setRouteDestination({
                    name: `${landingCentre.name} PFZ Core (${landingCentre.distance_km} km)`,
                    lat: landingCentre.lat + 0.16,
                    lon: landingCentre.lon + 0.22,
                  });
                  setDestModalOpen(false);
                }}
                className="w-full text-left p-2.5 rounded-xl bg-emerald-950/50 border border-emerald-500/40 text-emerald-300 text-xs font-bold"
              >
                🐟 Recommended PFZ Core Zone (Optimal Catch)
                <div className="text-[10px] font-normal text-slate-400">
                  {landingCentre.distance_km} km offshore • Heading {landingCentre.recommended_heading}
                </div>
              </button>

              {/* Option 2: Deep Sea Tuna Fishing Sector */}
              <button
                onClick={() => {
                  setRouteDestination({
                    name: `${landingCentre.district} Deep-Sea Oceanic Ridge`,
                    lat: landingCentre.lat + 0.28,
                    lon: landingCentre.lon + 0.42,
                  });
                  setDestModalOpen(false);
                }}
                className="w-full text-left p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-slate-200 text-xs"
              >
                🌊 Deep-Sea Oceanic Thermal Front (Tuna / Pelagics)
                <div className="text-[10px] text-slate-400">38 km offshore • Bathymetric Drop-off</div>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
