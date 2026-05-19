/**
 * Welcome / first-launch view.
 *
 * Local-first philosophy: NO login required to start using the app.
 * Primary CTA = "Apri il mio Brain" (skip cloud sync).
 * Secondary CTA = "Sincronizza con Akaion Cloud" (optional Google login).
 *
 * Once dismissed (either path), `localStorage.akaion_onboarding_done = "true"`,
 * so the next launch skips this view altogether.
 */
import { useState } from "react";
import { fbAuth, gProvider, signInWithPopup } from "../../lib/firebase";
import { auth as authApi, AuthStatus } from "../../api/runner";
import AuthLogo from "../auth/AuthLogo";
import SocialButton from "../auth/SocialButton";

interface Props {
  /** Path to the local vault (footer info, e.g. ~/akaion-brain) */
  vaultPath?: string;
  /** Called when the user picks local-only ("Apri il mio Brain") */
  onSkip: () => void;
  /** Called after a successful Google login */
  onLogin: (status: AuthStatus) => void;
}

export const ONBOARDING_FLAG = "akaion_onboarding_done";

export default function WelcomeView({ vaultPath = "~/akaion-brain", onSkip, onLogin }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const handleSkip = () => {
    try { localStorage.setItem(ONBOARDING_FLAG, "true"); } catch { /* private mode */ }
    onSkip();
  };

  const handleGoogle = async () => {
    setLoading(true);
    setError(null);
    try {
      const cred    = await signInWithPopup(fbAuth, gProvider);
      const token   = await cred.user.getIdToken();
      const refresh = (cred.user as any).stsTokenManager?.refreshToken ?? "";
      const status  = await authApi.save({
        firebase_token: token,
        refresh_token:  refresh,
        expires_in:     3600,
        email:          cred.user.email ?? "",
      });
      try { localStorage.setItem(ONBOARDING_FLAG, "true"); } catch { /* */ }
      onLogin(status);
    } catch (e: any) {
      // Silently swallow user-driven cancellations
      if (e?.code !== "auth/popup-closed-by-user" && e?.code !== "auth/cancelled-popup-request") {
        setError(e?.message ?? "Login Google fallito");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ak-welcome-shell">
      <div className="ak-welcome-orb ak-welcome-orb--violet" />
      <div className="ak-welcome-orb ak-welcome-orb--blue" />

      <div className="ak-welcome-card animate-fade-in-up">
        <AuthLogo
          title="Akaion Runner"
          subtitle="Your local-first knowledge vault"
        />

        <button
          className="ak-btn-primary"
          onClick={handleSkip}
          disabled={loading}
          aria-label="Apri il mio Brain — modalità locale"
        >
          <span aria-hidden="true">✦</span>
          Apri il mio Brain
        </button>

        <div className="ak-or-divider">oppure</div>

        <SocialButton
          provider="google"
          variant="full"
          isLoading={loading}
          onClick={handleGoogle}
          label="Sincronizza con Akaion Cloud"
        />

        {error && <div className="ak-auth-error">{error}</div>}

        <p className="ak-welcome-footer">
          Vault locale: <code>{vaultPath}</code><br />
          Le tue note restano sul tuo Mac. Il login al cloud è opzionale.
        </p>
      </div>
    </div>
  );
}
