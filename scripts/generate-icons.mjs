#!/usr/bin/env node
/**
 * Generate premium Akaion app icon master (1024x1024) for Tauri.
 *
 * Look:
 *   - Diagonal gradient #3D5BFF -> #9B51E0 (akaion primary-blue -> electric-violet)
 *   - macOS squircle (28% rounded) baked into master (Tauri CLI will keep alpha)
 *   - Akaion logo glyph in white, ~58% of canvas, centered
 *   - Outer violet glow ~25% opacity contained inside canvas
 *
 * Outputs:
 *   ui/src-tauri/icons/icon-1024.png  (master, hi-res, kept in repo)
 *
 * Then run `npx tauri icon icon-1024.png` to fan out to .icns/.ico/.png.
 *
 * Usage:
 *   node scripts/generate-icons.mjs
 */
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs/promises";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Sharp lives in the PWA frontend; reuse it (no extra install).
const pwaRequire = createRequire(
  path.join(
    __dirname,
    "..",
    "..",
    "akaion-pwa-frontend",
    "node_modules",
    "sharp",
    "package.json",
  ),
);
const sharp = pwaRequire("sharp");

const REPO_ROOT = path.resolve(__dirname, "..");
const PWA_PUBLIC = path.resolve(
  REPO_ROOT,
  "..",
  "akaion-pwa-frontend",
  "public",
);
const OUT_DIR = path.join(REPO_ROOT, "ui", "src-tauri", "icons");
const MASTER = path.join(OUT_DIR, "icon-1024.png");

const SIZE = 1024;
const CORNER = Math.round(SIZE * 0.225); // 230px — Apple squircle approx
const PAD = Math.round(SIZE * 0.21); // 215px each side
const LOGO_SIZE = SIZE - PAD * 2; // ~594px

const GRAD_FROM = "#3D5BFF";
const GRAD_TO = "#9B51E0";

/** Background: diagonal gradient + inner violet glow rim. */
function backgroundSvg() {
  return Buffer.from(`
<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 ${SIZE} ${SIZE}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="${SIZE}" y2="${SIZE}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="${GRAD_FROM}"/>
      <stop offset="100%" stop-color="${GRAD_TO}"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="60%" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="100%" stop-color="#9B51E0" stop-opacity="0.35"/>
    </radialGradient>
    <radialGradient id="hi" cx="30%" cy="20%" r="60%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.18"/>
      <stop offset="70%" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="${SIZE}" height="${SIZE}" rx="${CORNER}" ry="${CORNER}" fill="url(#bg)"/>
  <rect width="${SIZE}" height="${SIZE}" rx="${CORNER}" ry="${CORNER}" fill="url(#glow)"/>
  <rect width="${SIZE}" height="${SIZE}" rx="${CORNER}" ry="${CORNER}" fill="url(#hi)"/>
</svg>`);
}

/** Squircle mask for the whole canvas (keeps transparent corners). */
function squircleMaskSvg() {
  return Buffer.from(`
<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}">
  <rect width="${SIZE}" height="${SIZE}" rx="${CORNER}" ry="${CORNER}" fill="#fff"/>
</svg>`);
}

async function buildWhiteLogo() {
  // Logo_Black.png: white/silver glyph on dark grey opaque background.
  // Strategy: read RGB, use luminance as alpha (bright→opaque), force RGB to white.
  const src = path.join(PWA_PUBLIC, "Logo_Black.png");
  const resized = await sharp(src)
    .resize(LOGO_SIZE, LOGO_SIZE, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const { data, info } = resized;
  const { width, height, channels } = info;
  const out = Buffer.alloc(width * height * 4);
  for (let i = 0, j = 0; i < data.length; i += channels, j += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    // Perceived luminance 0..255
    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    // Map: lum<120 (dark grey backdrop) → alpha 0; lum>200 (glyph) → alpha 255.
    // The Logo_Black.png backdrop is ~grey 60-80, glyph is silver/white 180-255.
    let a;
    if (lum <= 120) a = 0;
    else if (lum >= 200) a = 255;
    else a = Math.round(((lum - 120) / (200 - 120)) * 255);
    out[j] = 255;
    out[j + 1] = 255;
    out[j + 2] = 255;
    out[j + 3] = a;
  }
  const buffer = await sharp(out, { raw: { width, height, channels: 4 } })
    .png()
    .toBuffer();
  return { buffer };
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });

  const bg = await sharp(backgroundSvg()).png().toBuffer();
  const mask = await sharp(squircleMaskSvg()).png().toBuffer();
  const { buffer: logo } = await buildWhiteLogo();

  // Outer glow under the logo: blurred copy at lower opacity for soft halo.
  // Use ensureAlpha + linear to dim, so screen blend stays subtle.
  const glowLayer = await sharp(logo)
    .blur(36)
    .ensureAlpha()
    .composite([{ input: Buffer.from([255, 255, 255, 90]), raw: { width: 1, height: 1, channels: 4 }, tile: true, blend: "dest-in" }])
    .png()
    .toBuffer();

  // Step 1: bg + glow + logo into a single raster.
  const filled = await sharp(bg)
    .composite([
      { input: glowLayer, top: PAD, left: PAD, blend: "screen" },
      { input: logo, top: PAD, left: PAD, blend: "over" },
    ])
    .png()
    .toBuffer();

  // Step 2: apply squircle mask (dest-in) on the filled raster.
  const composed = await sharp(filled)
    .composite([{ input: mask, blend: "dest-in" }])
    .png({ compressionLevel: 9 })
    .toBuffer();

  await fs.writeFile(MASTER, composed);
  const stat = await fs.stat(MASTER);
  console.log(`master  ${MASTER}  (${stat.size} bytes)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
