/**
 * Auth Logo — reusable brand block for the welcome / login screens.
 * Plain CSS (no Tailwind required). Italian copy by default.
 */
import LogoAkaion from "../brand/LogoAkaion";

interface AuthLogoProps {
  title?: string;
  subtitle?: string;
}

export default function AuthLogo({
  title = "Annona",
  subtitle = "Your local-first knowledge vault",
}: AuthLogoProps) {
  return (
    <div style={{ textAlign: "center", marginBottom: 32 }}>
      <div
        style={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 72,
          height: 72,
          borderRadius: 22,
          marginBottom: 18,
          overflow: "hidden",
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.10)",
          boxShadow:
            "0 10px 30px rgba(0,0,0,0.40), 0 0 40px hsl(270 100% 70% / 0.18)",
        }}
      >
        <LogoAkaion
          variant="glow"
          size={44}
          withShadow
          style={{ position: "relative", zIndex: 1, borderRadius: 12 }}
        />
      </div>
      <h1
        style={{
          fontSize: 26,
          fontWeight: 700,
          letterSpacing: "-0.5px",
          color: "hsl(var(--auth-text))",
          margin: 0,
        }}
      >
        {title}
      </h1>
      <p
        style={{
          fontSize: 13,
          marginTop: 6,
          color: "hsl(var(--auth-text-subtle))",
          fontWeight: 500,
        }}
      >
        {subtitle}
      </p>
    </div>
  );
}
