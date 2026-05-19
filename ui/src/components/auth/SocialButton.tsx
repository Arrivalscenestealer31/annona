/**
 * Social auth button — ported from akaion-pwa-frontend.
 * Tailwind-free: uses .ak-social-btn classes defined in css/auth-animations.css.
 */
interface SocialButtonProps {
  provider: "google" | "microsoft" | "apple";
  onClick: () => void;
  isLoading?: boolean;
  disabled?: boolean;
  variant?: "icon-only" | "full";
  /** Optional override label (e.g. "Sincronizza con Akaion Cloud"). */
  label?: string;
}

const icons = {
  google: (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  ),
  microsoft: (
    <svg width="18" height="18" viewBox="0 0 21 21" aria-hidden="true" focusable="false">
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  ),
  apple: (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="#ffffff">
      <path d="M17.05 12.04c-.03-3.16 2.58-4.68 2.7-4.75-1.47-2.15-3.76-2.45-4.57-2.48-1.95-.2-3.8 1.15-4.79 1.15-.99 0-2.51-1.12-4.13-1.09-2.13.03-4.09 1.24-5.18 3.14-2.21 3.83-.57 9.5 1.59 12.61 1.05 1.52 2.31 3.23 3.96 3.17 1.59-.06 2.19-1.03 4.11-1.03 1.93 0 2.47 1.03 4.16 1 1.71-.03 2.79-1.55 3.84-3.07 1.21-1.76 1.71-3.46 1.74-3.55-.04-.02-3.34-1.28-3.37-5.1zM13.96 3.94c.88-1.07 1.47-2.55 1.31-4.03-1.27.05-2.81.84-3.71 1.91-.81.95-1.51 2.46-1.32 3.91 1.41.11 2.85-.72 3.72-1.79z" />
    </svg>
  ),
};

const providerLabels: Record<string, string> = {
  google: "Google",
  microsoft: "Microsoft",
  apple: "Apple",
};

export default function SocialButton({
  provider,
  onClick,
  isLoading,
  disabled,
  variant = "full",
  label,
}: SocialButtonProps) {
  const providerName = providerLabels[provider] ?? provider;
  const fullLabel = label ?? `Continua con ${providerName}`;
  const a11yLabel = variant === "full" ? fullLabel : `Sign in with ${providerName}`;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || isLoading}
      aria-label={a11yLabel}
      aria-busy={isLoading}
      className={`ak-social-btn ${variant === "full" ? "ak-social-btn--full" : "ak-social-btn--icon"}`}
    >
      {isLoading ? (
        <span className="ak-spinner" aria-hidden="true" />
      ) : (
        <span className="ak-social-icon" aria-hidden="true">
          {icons[provider]}
        </span>
      )}
      <span className="ak-social-label">
        {variant === "full" ? fullLabel : providerName}
      </span>
    </button>
  );
}
