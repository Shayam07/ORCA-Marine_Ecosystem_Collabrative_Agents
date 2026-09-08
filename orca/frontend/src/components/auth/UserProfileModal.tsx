import { useState, useEffect } from 'react';
import {
  X,
  User,
  Mail,
  Phone,
  Anchor,
  Ship,
  Languages,
  Shield,
  LogOut,
  Save,
  Check,
  AlertCircle,
  KeyRound,
  Eye,
  EyeOff,
  Database,
  RefreshCw,
} from 'lucide-react';
import { useAuth, type UserRole, type VesselClass } from '../../context/AuthContext';
import { useMarineContext, type SupportedLanguage } from '../../context/MarineContext';
import {
  getSupabaseConfig,
  configureSupabase,
  clearSupabaseConfig,
  testSupabaseConnection,
} from '../../lib/supabase';
import { INDIAN_LANDING_CENTRES } from '../../data/landingCentres';

interface UserProfileModalProps {
  open: boolean;
  onClose: () => void;
}

const SUPPORTED_LANGUAGES: Array<{ code: SupportedLanguage; label: string; native: string }> = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'ml', label: 'Malayalam', native: 'മലയാളം' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'gu', label: 'Gujarati', native: 'ગુજરાતી' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'or', label: 'Odia', native: 'ଓଡ଼ିଆ' },
];

const VESSEL_CLASSES: VesselClass[] = [
  'Motorized',
  'Mechanized',
  'Traditional',
  'Deep Sea Trawler',
];

type ActiveTab = 'PROFILE' | 'SECURITY' | 'SUPABASE';

export default function UserProfileModal({ open, onClose }: UserProfileModalProps) {
  const { user, profile, updateProfile, updatePassword, signOut, isGuest, isConfigured, reloadAuthConfig } = useAuth();
  const { setLanguage, setLandingCentre } = useMarineContext();

  const [activeTab, setActiveTab] = useState<ActiveTab>('PROFILE');

  // Profile fields
  const [fullName, setFullName] = useState(profile?.full_name || '');
  const [phone, setPhone] = useState(profile?.phone_number || '');
  const [role, setRole] = useState<UserRole>(profile?.user_role || 'FISHERMAN');
  const [vesselClass, setVesselClass] = useState<VesselClass>((profile?.vessel_class as VesselClass) || 'Motorized');
  const [lang, setLang] = useState<SupportedLanguage>(profile?.preferred_language || 'en');
  const [harbor, setHarbor] = useState(
    profile?.preferred_harbor || 'Kasimedu Fishing Harbour, Chennai'
  );

  // Password fields
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [updatingPassword, setUpdatingPassword] = useState(false);
  const [passwordMsg, setPasswordMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Supabase config fields
  const [configUrl, setConfigUrl] = useState('');
  const [configKey, setConfigKey] = useState('');
  const [testingConnection, setTestingConnection] = useState(false);
  const [configMsg, setConfigMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (profile) {
      setFullName(profile.full_name || '');
      setPhone(profile.phone_number || '');
      setRole(profile.user_role || 'FISHERMAN');
      setVesselClass((profile.vessel_class as VesselClass) || 'Motorized');
      setLang(profile.preferred_language || 'en');
      setHarbor(profile.preferred_harbor || 'Kasimedu Fishing Harbour, Chennai');
    }
  }, [profile, open]);

  useEffect(() => {
    const cfg = getSupabaseConfig();
    setConfigUrl(cfg.url || '');
    if (typeof window !== 'undefined') {
      const storedKey = window.localStorage.getItem('orca_supabase_anon_key');
      if (storedKey) setConfigKey(storedKey);
    }
  }, [open]);

  if (!open) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrorMsg(null);
    setSavedSuccess(false);

    try {
      const { error } = await updateProfile({
        full_name: fullName.trim(),
        phone_number: phone.trim() || null,
        user_role: role,
        vessel_class: vesselClass,
        preferred_language: lang,
        preferred_harbor: harbor,
      });

      if (error) {
        setErrorMsg('Failed to update profile settings.');
      } else {
        setLanguage(lang);
        const matchedCentre = INDIAN_LANDING_CENTRES.find((c) => c.name === harbor);
        if (matchedCentre) {
          setLandingCentre(matchedCentre);
        }
        setSavedSuccess(true);
        setTimeout(() => setSavedSuccess(false), 2500);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error updating profile.');
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordMsg(null);

    if (newPassword.length < 6) {
      setPasswordMsg({ ok: false, text: 'Password must be at least 6 characters.' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ ok: false, text: 'Passwords do not match.' });
      return;
    }

    setUpdatingPassword(true);
    try {
      const { error } = await updatePassword(newPassword);
      if (error) {
        setPasswordMsg({ ok: false, text: error.message || 'Failed to update password.' });
      } else {
        setPasswordMsg({ ok: true, text: 'Password updated successfully!' });
        setNewPassword('');
        setConfirmPassword('');
      }
    } catch (err: any) {
      setPasswordMsg({ ok: false, text: err.message || 'Error updating password.' });
    } finally {
      setUpdatingPassword(false);
    }
  };

  const handleSaveSupabaseConfig = () => {
    setConfigMsg(null);
    if (!configUrl.trim() || !configKey.trim()) {
      setConfigMsg({ ok: false, text: 'Please provide both URL and Anon Key.' });
      return;
    }
    const res = configureSupabase(configUrl.trim(), configKey.trim());
    if (res.success) {
      reloadAuthConfig();
      setConfigMsg({ ok: true, text: 'Supabase credentials saved successfully!' });
    } else {
      setConfigMsg({ ok: false, text: res.error || 'Failed to configure Supabase.' });
    }
  };

  const handleTestSupabaseLink = async () => {
    setTestingConnection(true);
    setConfigMsg(null);
    const res = await testSupabaseConnection(configUrl, configKey);
    setTestingConnection(false);
    setConfigMsg({ ok: res.ok, text: res.message });
  };

  const handleResetSupabaseConfig = () => {
    clearSupabaseConfig();
    reloadAuthConfig();
    setConfigUrl('');
    setConfigKey('');
    setConfigMsg({ ok: true, text: 'Reset to environment defaults.' });
  };

  const handleLogout = async () => {
    onClose();
    await signOut();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-md rounded-2xl bg-[#111a2e] border border-slate-700 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-[#0d1424]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-cyan-600/30 border border-cyan-400 flex items-center justify-center text-cyan-300 font-bold text-sm">
              {fullName ? fullName.charAt(0).toUpperCase() : 'O'}
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">Marine Profile & Settings</h2>
              <p className="text-[10px] text-cyan-400 font-mono">
                {isGuest ? 'Guest Navigator Mode' : user?.email || 'Authenticated User'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center border-b border-slate-800 bg-slate-900/50 px-5 pt-2 gap-1 text-xs">
          <button
            type="button"
            onClick={() => setActiveTab('PROFILE')}
            className={`pb-2 px-3 font-semibold transition-all border-b-2 ${
              activeTab === 'PROFILE'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Profile
          </button>
          {!isGuest && (
            <button
              type="button"
              onClick={() => setActiveTab('SECURITY')}
              className={`pb-2 px-3 font-semibold transition-all border-b-2 ${
                activeTab === 'SECURITY'
                  ? 'border-cyan-400 text-cyan-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              Security
            </button>
          )}
          <button
            type="button"
            onClick={() => setActiveTab('SUPABASE')}
            className={`pb-2 px-3 font-semibold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === 'SUPABASE'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>Supabase</span>
          </button>
        </div>

        {/* Tab 1: Profile Form */}
        {activeTab === 'PROFILE' && (
          <form onSubmit={handleSave} className="p-5 space-y-4 overflow-y-auto flex-1 text-xs">
            {errorMsg && (
              <div className="p-2.5 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {savedSuccess && (
              <div className="p-2.5 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 flex items-center gap-2">
                <Check className="w-4 h-4 flex-shrink-0" />
                <span>Profile preferences updated successfully!</span>
              </div>
            )}

            {/* Full Name */}
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Full Name</label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-cyan-500"
                  placeholder="Navigator Name"
                />
              </div>
            </div>

            {/* Phone */}
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Mobile Phone (Alerts)</label>
              <div className="relative">
                <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-cyan-500"
                  placeholder="+91 98400 12345"
                />
              </div>
            </div>

            {/* Role */}
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Role</label>
              <div className="grid grid-cols-3 gap-2">
                {(['FISHERMAN', 'RESEARCHER', 'ADMIN'] as UserRole[]).map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRole(r)}
                    className={`py-1.5 px-2 rounded-lg border font-semibold text-[11px] transition-all ${
                      role === r
                        ? 'bg-cyan-950/80 border-cyan-400 text-cyan-300 shadow-sm'
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-300'
                    }`}
                  >
                    {r === 'FISHERMAN' ? '🎣 Fisher' : r === 'RESEARCHER' ? '🔬 Scientist' : '⚓ Admin'}
                  </button>
                ))}
              </div>
            </div>

            {/* Vessel Class */}
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Vessel Class</label>
              <div className="relative">
                <Ship className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <select
                  value={vesselClass}
                  onChange={(e) => setVesselClass(e.target.value as VesselClass)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-cyan-500"
                >
                  {VESSEL_CLASSES.map((v) => (
                    <option key={v} value={v}>
                      {v} Boat
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Preferred Language */}
            <div>
              <label className="block font-semibold text-slate-300 mb-1">
                Preferred Language / மொழி
              </label>
              <div className="relative">
                <Languages className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <select
                  value={lang}
                  onChange={(e) => setLang(e.target.value as SupportedLanguage)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-cyan-500"
                >
                  {SUPPORTED_LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.native} ({l.label})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Preferred Harbour */}
            <div>
              <label className="block font-semibold text-slate-300 mb-1">
                Home Fishing Harbour
              </label>
              <div className="relative">
                <Anchor className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <select
                  value={harbor}
                  onChange={(e) => setHarbor(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-cyan-500"
                >
                  {INDIAN_LANDING_CENTRES.map((centre) => (
                    <option key={centre.id} value={centre.name}>
                      {centre.name} ({centre.state})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Save Button */}
            <button
              type="submit"
              disabled={saving}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold flex items-center justify-center gap-2 shadow-lg shadow-cyan-900/30 transition-all disabled:opacity-50"
            >
              {saving ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Save Preferences</span>
                </>
              )}
            </button>
          </form>
        )}

        {/* Tab 2: Security / Password */}
        {activeTab === 'SECURITY' && (
          <form onSubmit={handlePasswordUpdate} className="p-5 space-y-4 overflow-y-auto flex-1 text-xs">
            <div className="p-3 rounded-xl bg-cyan-950/40 border border-cyan-500/20 text-slate-300">
              <span className="font-semibold text-cyan-300">Change Password</span>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Update your authentication password across all connected ORCA marine sessions.
              </p>
            </div>

            {passwordMsg && (
              <div
                className={`p-2.5 rounded-xl border flex items-center gap-2 ${
                  passwordMsg.ok
                    ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-500/40 text-rose-300'
                }`}
              >
                {passwordMsg.ok ? (
                  <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                )}
                <span>{passwordMsg.text}</span>
              </div>
            )}

            <div>
              <label className="block font-semibold text-slate-300 mb-1">New Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Min. 6 characters"
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white pr-10 focus:outline-none focus:border-cyan-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1">Confirm New Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white pr-10 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={updatingPassword}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold flex items-center justify-center gap-2 shadow-lg shadow-cyan-900/30 transition-all disabled:opacity-50"
            >
              {updatingPassword ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <KeyRound className="w-4 h-4" />
                  <span>Update Password</span>
                </>
              )}
            </button>
          </form>
        )}

        {/* Tab 3: Supabase Configuration */}
        {activeTab === 'SUPABASE' && (
          <div className="p-5 space-y-4 overflow-y-auto flex-1 text-xs">
            <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-700 text-slate-300 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white">Connection Status</span>
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    isConfigured
                      ? 'bg-emerald-950 border border-emerald-500/50 text-emerald-300'
                      : 'bg-amber-950 border border-amber-500/50 text-amber-300'
                  }`}
                >
                  {isConfigured ? 'Connected' : 'Demo / Offline'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                You can configure your own Supabase project without changing code.
              </p>
            </div>

            {configMsg && (
              <div
                className={`p-2.5 rounded-xl border flex items-center gap-2 ${
                  configMsg.ok
                    ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-500/40 text-rose-300'
                }`}
              >
                {configMsg.ok ? (
                  <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                )}
                <span>{configMsg.text}</span>
              </div>
            )}

            <div>
              <label className="block font-semibold text-slate-300 mb-1">Project URL</label>
              <input
                type="url"
                value={configUrl}
                onChange={(e) => setConfigUrl(e.target.value)}
                placeholder="https://your-project.supabase.co"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white font-mono text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1">Anon Public Key</label>
              <input
                type="password"
                value={configKey}
                onChange={(e) => setConfigKey(e.target.value)}
                placeholder="your-supabase-anon-key"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white font-mono text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={handleTestSupabaseLink}
                disabled={testingConnection || !configUrl}
                className="flex-1 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
              >
                {testingConnection ? (
                  <div className="w-3.5 h-3.5 border border-slate-400 border-t-white rounded-full animate-spin" />
                ) : (
                  <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
                )}
                <span>Test Link</span>
              </button>
              <button
                type="button"
                onClick={handleSaveSupabaseConfig}
                className="flex-1 py-2 px-3 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold flex items-center justify-center gap-1.5 transition-colors"
              >
                <Save className="w-3.5 h-3.5" />
                <span>Save</span>
              </button>
            </div>

            <div className="text-right pt-1">
              <button
                type="button"
                onClick={handleResetSupabaseConfig}
                className="text-[11px] text-slate-500 hover:text-slate-400 underline"
              >
                Reset to .env Defaults
              </button>
            </div>
          </div>
        )}

        {/* Footer with Logout */}
        <div className="px-5 py-3 border-t border-slate-800 bg-[#0d1424] flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-slate-400 text-[10px]">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span>Encrypted Session</span>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="px-3 py-1.5 rounded-lg bg-rose-950/50 hover:bg-rose-900/60 border border-rose-500/40 text-rose-300 text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </div>
  );
}
