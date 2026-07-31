/**
 * Welcome / first-launch view.
 *
 * Local-first philosophy: NO login required to start using the app.
 * Primary CTA = "Open my vault" (skips cloud sync).
 * Secondary CTA = "Sync with Akaion Cloud" (optional Google sign-in).
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
  /** Called when the user picks local-only ("Open my vault") */
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
        setError(e?.message ?? "Google sign-in failed");
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
          title="Annona"
          subtitle="Your local-first knowledge vault"
        />

        <button
          className="ak-btn-primary"
          onClick={handleSkip}
          disabled={loading}
          aria-label="Open my vault — local mode"
        >
          <span aria-hidden="true">✦</span>
          Open my vault
        </button>

        <div className="ak-or-divider">or</div>

        <SocialButton
          provider="google"
          variant="full"
          isLoading={loading}
          onClick={handleGoogle}
          label="Sync with Akaion Cloud"
        />

        {error && <div className="ak-auth-error">{error}</div>}

        <p className="ak-welcome-footer">
          Local vault: <code>{vaultPath}</code><br />
          Your notes stay on this machine. Cloud sign-in is optional.
        </p>
      </div>
    </div>
  );
}
