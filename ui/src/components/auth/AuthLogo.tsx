/**
 * Auth Logo — reusable brand block for the welcome / login screens.
 * Plain CSS (no Tailwind required). Italian copy by default.
 */

interface AuthLogoProps {
  title?: string;
  subtitle?: string;
}

export default function AuthLogo({
  title = "Annona",
  subtitle = "Where it runs is a decision",
}: AuthLogoProps) {
  return (
    <div style={{ textAlign: "center", marginBottom: 32 }}>
      <div
        style={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 132,
          height: 132,
          marginBottom: 10,
        }}
      >
        {/* The mascot, not a mark: this window is the product's face, and the
            product is Annona. */}
        <img
          src="/annona-mascot.png"
          alt="Annona"
          style={{
            width: 132,
            height: 132,
            objectFit: "contain",
            filter: "drop-shadow(0 12px 28px rgba(0,0,0,.45))",
          }}
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
