import { useState, useEffect } from 'react';
import {
  Eye,
  EyeOff,
  Ship,
  Lock,
  Mail,
  User,
  Phone,
  Compass,
  Languages,
  ShieldCheck,
  ArrowRight,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Anchor,
  Database,
  KeyRound,
  RefreshCw,
  X,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useAuth, type UserRole, type VesselClass } from '../../context/AuthContext';
import {
  getSupabaseConfig,
  configureSupabase,
  clearSupabaseConfig,
  testSupabaseConnection,
} from '../../lib/supabase';
import { INDIAN_LANDING_CENTRES } from '../../data/landingCentres';
import type { SupportedLanguage } from '../../context/MarineContext';
import IncoisLogo from '../IncoisLogo';

type AuthMode = 'LOGIN' | 'SIGNUP' | 'MAGIC_LINK' | 'FORGOT_PASSWORD' | 'RECOVERY';

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

export default function AuthScreen() {
  const {
    signIn,
    signUp,
    signInWithOtp,
    signInWithGoogle,
    resetPassword,
    updatePassword,
    authError,
    isConfigured,
    isPasswordRecovery,
    clearPasswordRecovery,
    continueAsGuest,
    reloadAuthConfig,
  } = useAuth();

  const [mode, setMode] = useState<AuthMode>(() => (isPasswordRecovery ? 'RECOVERY' : 'LOGIN'));
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Onboarding fields for SIGNUP
  const [fullName, setFullName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [userRole, setUserRole] = useState<UserRole>('FISHERMAN');
  const [vesselClass, setVesselClass] = useState<VesselClass>('Motorized');
  const [preferredLang, setPreferredLang] = useState<SupportedLanguage>('en');
  const [preferredHarbor, setPreferredHarbor] = useState<string>(
    INDIAN_LANDING_CENTRES[0]?.name || 'Kasimedu Fishing Harbour, Chennai'
  );

  // Supabase dynamic setup modal/accordion
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configUrl, setConfigUrl] = useState('');
  const [configKey, setConfigKey] = useState('');
  const [testingConnection, setTestingConnection] = useState(false);
  const [configFeedback, setConfigFeedback] = useState<{ ok: boolean; message: string } | null>(null);

  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isPasswordRecovery) {
      setMode('RECOVERY');
    }
  }, [isPasswordRecovery]);

  useEffect(() => {
    const cfg = getSupabaseConfig();
    setConfigUrl(cfg.url || '');
    // Only display key if it's already in localStorage
    if (typeof window !== 'undefined') {
      const storedKey = window.localStorage.getItem('orca_supabase_anon_key');
      if (storedKey) setConfigKey(storedKey);
    }
  }, [showConfigModal]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    setSuccessMessage(null);

    // Mode-specific validations
    if (mode === 'RECOVERY') {
      if (!password) {
        setLocalError('Please enter your new password.');
        return;
      }
      if (password.length < 6) {
        setLocalError('Password must be at least 6 characters long.');
        return;
      }
      if (password !== confirmPassword) {
        setLocalError('Passwords do not match.');
        return;
      }

      setLoading(true);
      try {
        const { error } = await updatePassword(password);
        if (error) {
          setLocalError(error.message || 'Failed to update password.');
        } else {
          setSuccessMessage('Password successfully updated! You are now securely logged in.');
          setTimeout(() => {
            clearPasswordRecovery();
            setMode('LOGIN');
          }, 1500);
        }
      } catch (err: any) {
        setLocalError(err.message || 'Error updating password.');
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!email.trim()) {
      setLocalError('Please enter your email address');
      return;
    }

    if (mode === 'MAGIC_LINK') {
      setLoading(true);
      try {
        const { error } = await signInWithOtp(email.trim());
        if (error) {
          setLocalError(error.message || 'Failed to dispatch magic link.');
        } else {
          setSuccessMessage('A secure passwordless login link has been sent to your email.');
        }
      } catch (err: any) {
        setLocalError(err.message || 'Error sending magic link.');
      } finally {
        setLoading(false);
      }
      return;
    }

    if (mode !== 'FORGOT_PASSWORD' && !password) {
      setLocalError('Please enter your password');
      return;
    }

    if (mode === 'SIGNUP') {
      if (password.length < 6) {
        setLocalError('Password must be at least 6 characters long');
        return;
      }
      if (password !== confirmPassword) {
        setLocalError('Passwords do not match');
        return;
      }
    }

    setLoading(true);

    try {
      if (mode === 'LOGIN') {
        const { error } = await signIn(email.trim(), password);
        if (error) {
          setLocalError(error.message || 'Login failed. Please check your credentials.');
        }
      } else if (mode === 'SIGNUP') {
        const { error } = await signUp(email.trim(), password, {
          full_name: fullName.trim() || undefined,
          phone_number: phoneNumber.trim() || undefined,
          preferred_language: preferredLang,
          preferred_harbor: preferredHarbor,
          user_role: userRole,
          vessel_class: vesselClass,
        });

        if (error) {
          setLocalError(error.message || 'Signup failed. Please try again.');
        } else {
          setSuccessMessage(
            isConfigured
              ? 'Account created! If confirmation is required, please check your inbox.'
              : 'Account initialized successfully in local session!'
          );
        }
      } else if (mode === 'FORGOT_PASSWORD') {
        const { error } = await resetPassword(email.trim());
        if (error) {
          setLocalError(error.message || 'Failed to send password reset email.');
        } else {
          setSuccessMessage('Password reset link has been dispatched to your email.');
        }
      }
    } catch (err: any) {
      setLocalError(err.message || 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleAuth = async () => {
    setLocalError(null);
    setSuccessMessage(null);
    setLoading(true);
    try {
      const { error } = await signInWithGoogle();
      if (error) {
        setLocalError(error.message || 'Google sign-in failed.');
      }
    } catch (err: any) {
      setLocalError(err.message || 'Failed to initiate Google authentication.');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveConfig = () => {
    setConfigFeedback(null);
    if (!configUrl.trim() || !configKey.trim()) {
      setConfigFeedback({ ok: false, message: 'Please enter both the Supabase URL and Anon Key.' });
      return;
    }
    const result = configureSupabase(configUrl.trim(), configKey.trim());
    if (result.success) {
      reloadAuthConfig();
      setConfigFeedback({ ok: true, message: 'Supabase credentials saved and client reloaded successfully!' });
      setTimeout(() => setShowConfigModal(false), 1200);
    } else {
      setConfigFeedback({ ok: false, message: result.error || 'Failed to save configuration.' });
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setConfigFeedback(null);
    const result = await testSupabaseConnection(configUrl, configKey);
    setTestingConnection(false);
    setConfigFeedback(result);
  };

  const handleClearConfig = () => {
    clearSupabaseConfig();
    reloadAuthConfig();
    setConfigUrl('');
    setConfigKey('');
    setConfigFeedback({ ok: true, message: 'Cleared custom credentials. Restored default environment values.' });
  };

  return (
    <div className="min-h-screen w-full bg-[#0a0f1d] text-slate-100 flex flex-col justify-center items-center p-4 sm:p-6 select-none relative overflow-y-auto">
      {/* Dynamic Background Marine Glow Effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[550px] bg-cyan-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-10 right-10 w-96 h-96 bg-blue-700/10 rounded-full blur-3xl" />
        <div className="absolute top-10 left-10 w-80 h-80 bg-emerald-600/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative z-10 my-auto">
        {/* Top Header */}
        <div className="text-center mb-5">
          <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-gradient-to-br from-cyan-950/80 to-blue-950/80 border border-cyan-500/30 shadow-xl shadow-cyan-950/40 mb-3 backdrop-blur-sm">
            <span className="text-3xl">🐋</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white flex items-center justify-center gap-2">
            <span>ORCA Marine Portal</span>
          </h1>
          <p className="text-xs sm:text-sm text-cyan-400 font-medium tracking-wide mt-1">
            Ocean Reconnaissance & Coastal Analytics
          </p>

          <div className="flex items-center justify-center gap-2 mt-2 text-[11px] text-slate-400">
            <IncoisLogo className="w-4 h-4" />
            <span>INCOIS • MOSDAC • NavIC Operational System</span>
          </div>
        </div>

        {/* Main Card */}
        <div className="bg-[#111a2e]/90 border border-slate-700/60 backdrop-blur-xl rounded-2xl shadow-2xl p-6 sm:p-7 relative overflow-hidden">
          {/* Top Accent Line */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-cyan-500 via-blue-500 to-emerald-400" />

          {/* Mode Switch Tabs (shown unless in Recovery mode) */}
          {mode !== 'RECOVERY' ? (
            <div className="flex items-center rounded-xl bg-slate-900/80 p-1 mb-5 border border-slate-800">
              <button
                type="button"
                onClick={() => {
                  setMode('LOGIN');
                  setLocalError(null);
                  setSuccessMessage(null);
                }}
                className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  mode === 'LOGIN'
                    ? 'bg-cyan-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode('SIGNUP');
                  setLocalError(null);
                  setSuccessMessage(null);
                }}
                className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  mode === 'SIGNUP'
                    ? 'bg-cyan-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Register
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode('MAGIC_LINK');
                  setLocalError(null);
                  setSuccessMessage(null);
                }}
                className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  mode === 'MAGIC_LINK'
                    ? 'bg-cyan-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Magic Link
              </button>
            </div>
          ) : (
            <div className="mb-5 text-center">
              <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-cyan-950 border border-cyan-500/40 text-cyan-400 mb-2">
                <KeyRound className="w-5 h-5" />
              </div>
              <h2 className="text-base font-bold text-white">Set New Password</h2>
              <p className="text-xs text-slate-400">Choose a strong password for your ORCA account</p>
            </div>
          )}

          {/* Error & Success Feedback Banners */}
          {(localError || authError) && (
            <div className="mb-4 p-3 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs flex items-start gap-2 animate-in fade-in">
              <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
              <span>{localError || authError}</span>
            </div>
          )}

          {successMessage && (
            <div className="mb-4 p-3 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs flex items-start gap-2 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Auth Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email Field (hidden during password recovery) */}
            {mode !== 'RECOVERY' && (
              <div>
                <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="navigator@ocean.in"
                    className="w-full pl-10 pr-3 py-2.5 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
                  />
                </div>
              </div>
            )}

            {/* Password Field */}
            {(mode === 'LOGIN' || mode === 'SIGNUP' || mode === 'RECOVERY') && (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
                    {mode === 'RECOVERY' ? 'New Password' : 'Password'}
                  </label>
                  {mode === 'LOGIN' && (
                    <button
                      type="button"
                      onClick={() => setMode('FORGOT_PASSWORD')}
                      className="text-[11px] text-cyan-400 hover:text-cyan-300 transition-colors"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors p-1"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}

            {/* Confirm Password (for Signup and Recovery) */}
            {(mode === 'SIGNUP' || mode === 'RECOVERY') && (
              <div>
                <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Confirm Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors p-1"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}

            {/* Additional Profile Onboarding Fields during Signup */}
            {mode === 'SIGNUP' && (
              <div className="space-y-3.5 pt-1 border-t border-slate-800 animate-in fade-in">
                {/* Full Name */}
                <div>
                  <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1">
                    Full Name
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="e.g. Murugan Selvam"
                      className="w-full pl-10 pr-3 py-2 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                    />
                  </div>
                </div>

                {/* Phone Number */}
                <div>
                  <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1">
                    Mobile Phone <span className="text-slate-500 font-normal">(for SMS/Voice alerts)</span>
                  </label>
                  <div className="relative">
                    <Phone className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="tel"
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      placeholder="+91 98400 12345"
                      className="w-full pl-10 pr-3 py-2 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                    />
                  </div>
                </div>

                {/* Role Selector */}
                <div>
                  <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1">
                    Role / Profile Type
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {(['FISHERMAN', 'RESEARCHER', 'ADMIN'] as UserRole[]).map((r) => (
                      <button
                        key={r}
                        type="button"
                        onClick={() => setUserRole(r)}
                        className={`py-1.5 px-2 text-[11px] font-semibold rounded-lg border transition-all truncate ${
                          userRole === r
                            ? 'bg-cyan-950/70 border-cyan-400 text-cyan-300 shadow-sm'
                            : 'bg-slate-900/70 border-slate-800 text-slate-400 hover:text-slate-300'
                        }`}
                      >
                        {r === 'FISHERMAN' ? '🎣 Fisher' : r === 'RESEARCHER' ? '🔬 Scientist' : '⚓ Admin'}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Vessel Class Selector */}
                <div>
                  <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1">
                    Vessel Class / Type
                  </label>
                  <div className="relative">
                    <Ship className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <select
                      value={vesselClass}
                      onChange={(e) => setVesselClass(e.target.value as VesselClass)}
                      className="w-full pl-10 pr-3 py-2 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-xs focus:outline-none focus:border-cyan-500 transition-colors"
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
                  <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1">
                    Preferred Language / மொழி
                  </label>
                  <div className="relative">
                    <Languages className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <select
                      value={preferredLang}
                      onChange={(e) => setPreferredLang(e.target.value as SupportedLanguage)}
                      className="w-full pl-10 pr-3 py-2 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-xs focus:outline-none focus:border-cyan-500 transition-colors"
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
                  <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1">
                    Home Fishing Harbour / Coastal Port
                  </label>
                  <div className="relative">
                    <Anchor className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <select
                      value={preferredHarbor}
                      onChange={(e) => setPreferredHarbor(e.target.value)}
                      className="w-full pl-10 pr-3 py-2 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-xs focus:outline-none focus:border-cyan-500 transition-colors"
                    >
                      {INDIAN_LANDING_CENTRES.map((centre) => (
                        <option key={centre.id} value={centre.name}>
                          {centre.name} ({centre.state})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Submit Action Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-xs shadow-lg shadow-cyan-900/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : mode === 'LOGIN' ? (
                <>
                  <span>Sign In to Marine Portal</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              ) : mode === 'SIGNUP' ? (
                <>
                  <span>Create ORCA Account</span>
                  <Sparkles className="w-4 h-4" />
                </>
              ) : mode === 'MAGIC_LINK' ? (
                <>
                  <span>Send Magic Link</span>
                  <Mail className="w-4 h-4" />
                </>
              ) : mode === 'RECOVERY' ? (
                <>
                  <span>Save New Password</span>
                  <CheckCircle2 className="w-4 h-4" />
                </>
              ) : (
                <>
                  <span>Send Reset Link</span>
                  <Mail className="w-4 h-4" />
                </>
              )}
            </button>

            {/* Back to Login option if in Forgot Password / Magic Link mode */}
            {(mode === 'FORGOT_PASSWORD' || mode === 'MAGIC_LINK') && (
              <button
                type="button"
                onClick={() => setMode('LOGIN')}
                className="w-full text-center text-xs text-cyan-400 hover:text-cyan-300 transition-colors pt-2"
              >
                Back to Sign In
              </button>
            )}
          </form>

          {/* Social OAuth & Guest Access (hidden in recovery mode) */}
          {mode !== 'RECOVERY' && (
            <>
              {/* Divider */}
              <div className="relative my-5">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-800" />
                </div>
                <div className="relative flex justify-center text-[10px] uppercase">
                  <span className="bg-[#111a2e] px-2 text-slate-500 font-semibold tracking-wider">
                    Or Continue With
                  </span>
                </div>
              </div>

              {/* Google Sign-in */}
              <button
                type="button"
                onClick={handleGoogleAuth}
                disabled={loading}
                className="w-full py-2.5 px-3 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-white font-semibold text-xs flex items-center justify-center gap-2 transition-all shadow-sm"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.8-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.26v3.15C3.25 21.36 7.33 24 12 24z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.26C.46 8.16 0 9.94 0 12s.46 3.84 1.26 5.42l4.02-3.15z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.25 2.64 1.26 6.58l4.02 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
                  />
                </svg>
                <span>Continue with Google</span>
              </button>

              {/* Demo / Guest Access Button */}
              <div className="mt-4 pt-3 border-t border-slate-800/80 text-center">
                <button
                  type="button"
                  onClick={continueAsGuest}
                  className="text-xs text-slate-400 hover:text-cyan-300 font-medium transition-colors flex items-center justify-center gap-1.5 mx-auto"
                >
                  <span>Explore Dashboard as Guest</span>
                  <Compass className="w-3.5 h-3.5 text-cyan-400" />
                </button>
              </div>
            </>
          )}

          {/* Supabase Connection Setup Toggle */}
          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  isConfigured ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-amber-400 animate-pulse'
                }`}
              />
              <span>{isConfigured ? 'Supabase Connected' : 'Demo / Unlinked Mode'}</span>
            </div>
            <button
              type="button"
              onClick={() => setShowConfigModal(!showConfigModal)}
              className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium transition-colors"
            >
              <Database className="w-3.5 h-3.5" />
              <span>Project Config</span>
              {showConfigModal ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          </div>

          {/* Collapsible Supabase Project Setup Drawer */}
          {showConfigModal && (
            <div className="mt-4 p-3.5 rounded-xl bg-slate-900/90 border border-cyan-500/30 text-xs space-y-3 animate-in fade-in">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Configure Supabase Project</span>
                </span>
                <button
                  type="button"
                  onClick={() => setShowConfigModal(false)}
                  className="text-slate-400 hover:text-slate-200"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-[11px] text-slate-400">
                Connect your hosted or local Supabase project URL and anon public key:
              </p>

              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">
                  Project URL
                </label>
                <input
                  type="url"
                  value={configUrl}
                  onChange={(e) => setConfigUrl(e.target.value)}
                  placeholder="https://your-project-id.supabase.co"
                  className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-white text-xs placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">
                  Anon Public Key
                </label>
                <input
                  type="password"
                  value={configKey}
                  onChange={(e) => setConfigKey(e.target.value)}
                  placeholder="your-supabase-anon-key"
                  className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-white text-xs placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>

              {configFeedback && (
                <div
                  className={`p-2 rounded-lg text-[11px] flex items-center gap-1.5 ${
                    configFeedback.ok
                      ? 'bg-emerald-950/60 border border-emerald-500/40 text-emerald-300'
                      : 'bg-rose-950/60 border border-rose-500/40 text-rose-300'
                  }`}
                >
                  {configFeedback.ok ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                  ) : (
                    <AlertCircle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
                  )}
                  <span>{configFeedback.message}</span>
                </div>
              )}

              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testingConnection || !configUrl}
                  className="flex-1 py-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 font-medium text-[11px] flex items-center justify-center gap-1 transition-all disabled:opacity-50"
                >
                  {testingConnection ? (
                    <div className="w-3 h-3 border border-slate-400 border-t-white rounded-full animate-spin" />
                  ) : (
                    <RefreshCw className="w-3 h-3 text-cyan-400" />
                  )}
                  <span>Test Link</span>
                </button>
                <button
                  type="button"
                  onClick={handleSaveConfig}
                  className="flex-1 py-1.5 px-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-[11px] flex items-center justify-center gap-1 transition-all"
                >
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Save & Connect</span>
                </button>
              </div>

              <div className="text-right">
                <button
                  type="button"
                  onClick={handleClearConfig}
                  className="text-[10px] text-slate-500 hover:text-slate-400 underline"
                >
                  Reset to .env Defaults
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer Security Badges */}
        <div className="flex items-center justify-center gap-4 mt-5 text-[11px] text-slate-400">
          <div className="flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Row-Level Security (RLS)</span>
          </div>
          <span>•</span>
          <div className="flex items-center gap-1">
            <Lock className="w-3.5 h-3.5 text-cyan-400" />
            <span>Supabase JWT Auth</span>
          </div>
        </div>
      </div>
    </div>
  );
}
