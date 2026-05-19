/**
 * Akaion logo — image-based logo with optional violet glow halo.
 * Ported from akaion-pwa-frontend, kept dependency-free (no i18n).
 */
import React from "react";

export type LogoVariant = "glow" | "mark";
export type LogoSize = "xs" | "sm" | "md" | "lg" | "xl" | number;

export interface LogoAkaionProps
  extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, "src" | "alt"> {
  variant?: LogoVariant;
  size?: LogoSize;
  alt?: string;
  /** Soft violet halo behind the logo */
  withShadow?: boolean;
  /** Corner radius in px (default 22% of size for square glow, 0 for mark) */
  rounded?: number | boolean;
}

const SIZE_MAP: Record<Exclude<LogoSize, number>, number> = {
  xs: 16,
  sm: 24,
  md: 40,
  lg: 64,
  xl: 96,
};

const SRC_MAP: Record<LogoVariant, string> = {
  glow: "/akaion-logo-glow-square.png",
  mark: "/akaion-logo-glow.png",
};

export function LogoAkaion({
  variant = "glow",
  size = "md",
  alt = "Akaion",
  withShadow = false,
  rounded,
  className,
  style,
  ...rest
}: LogoAkaionProps) {
  const px = typeof size === "number" ? size : SIZE_MAP[size];
  const radius =
    typeof rounded === "number"
      ? rounded
      : rounded === false
      ? 0
      : variant === "glow"
      ? Math.round(px * 0.22)
      : 0;

  const filter = withShadow
    ? "drop-shadow(0 0 14px rgba(139,92,246,0.45)) drop-shadow(0 4px 14px rgba(0,0,0,0.25))"
    : undefined;

  return (
    <img
      src={SRC_MAP[variant]}
      alt={alt}
      width={px}
      height={px}
      className={className}
      style={{
        width: px,
        height: variant === "mark" ? "auto" : px,
        objectFit: "cover",
        borderRadius: radius,
        filter,
        ...style,
      }}
      {...rest}
    />
  );
}

export default LogoAkaion;
