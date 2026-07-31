import { fbAuth, gProvider, signInWithPopup } from "./firebase"
import { auth as authApi, AuthStatus } from "../api/runner"

/**
 * Signing in to cloud sync, from a window that cannot open a popup.
 *
 * `signInWithPopup` calls `window.open`. A Tauri webview has no popup to open,
 * so the packaged app answered every attempt with
 *
 *     Firebase: Error (auth/popup-blocked)
 *
 * — not a misconfiguration, a structural fact about the container. Retrying it
 * there can only fail, and offering a button that can only fail is worse than
 * offering none.
 *
 * The way out is that this interface is *served by the daemon over HTTP*. The
 * same page, opened in the user's real browser at `localhost:7070`, has popups,
 * a URL bar, a password manager, and an origin Firebase already authorises
 * (`localhost` is on the authorised-domains list of every Firebase project by
 * default — which is why this opens `localhost` and not `127.0.0.1`).
 *
 * So the desktop app hands sign-in to the browser and waits: the browser tab
 * completes the exchange and posts the token to the daemon, and the app — which
 * talks to the same daemon — sees it appear. No hosted callback page, no
 * loopback OAuth server, no second copy of the credential handling.
 */

/**
 * The one URL the app is allowed to hand to the operating system.
 *
 * The scope that enforces it is `plugins.shell.open` in `tauri.conf.json`, as a
 * regex anchored to this exact string — *not* the capability's allow-list, which
 * the shell plugin ignores for `open`. Without a scope the plugin's default
 * applies, which permits any http(s) URL: every page in this window could then
 * ask the OS to open anything. Keep the two in step.
 *
 * That config section is strict JSON with no comment field — a `"//"` key there
 * is not ignored, it aborts plugin initialisation and the app never starts. Ask
 * how this comment ended up over here.
 */
const SIGNIN_URL = "http://localhost:7070/?signin=1"
const POLL_MS = 2_000
const GIVE_UP_MS = 5 * 60_000

export function isTauri(): boolean {
  if (typeof window === "undefined") return false
  const w = window as unknown as Record<string, unknown>
  return "__TAURI__" in w || "__TAURI_INTERNALS__" in w
}

/** True when this page was opened by the desktop app to perform the sign-in. */
export function isSigninHandoff(): boolean {
  if (typeof window === "undefined") return false
  return new URLSearchParams(window.location.search).get("signin") === "1"
}

/** The exchange itself. Only ever called where popups exist. */
export async function signInWithGoogle(): Promise<AuthStatus> {
  const cred = await signInWithPopup(fbAuth, gProvider)
  const token = await cred.user.getIdToken()
  const refresh = (cred.user as any).stsTokenManager?.refreshToken ?? ""
  return authApi.save({
    firebase_token: token,
    refresh_token: refresh,
    expires_in: 3600,
    email: cred.user.email ?? "",
  })
}

/**
 * Sign in from wherever this is running.
 *
 * In a browser: the popup, directly. In the desktop app: open the browser and
 * watch the daemon until the token lands there.
 *
 * @param onWaiting Called once, when the browser has been opened, so the UI can
 *   say what it is waiting for rather than spinning silently for five minutes.
 * @throws Error if the browser could not be opened, or nobody finished signing
 *   in before the deadline. Cancellation is not an error and is reported as
 *   `auth/popup-closed-by-user`, as the browser path already does.
 */
export async function signIn(onWaiting?: () => void): Promise<AuthStatus> {
  if (!isTauri()) return signInWithGoogle()

  const { open } = await import("@tauri-apps/plugin-shell")
  await open(SIGNIN_URL)
  onWaiting?.()

  const deadline = Date.now() + GIVE_UP_MS
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, POLL_MS))
    try {
      const status = await authApi.status()
      if (status.authenticated) return status
    } catch {
      // The daemon is momentarily busy; the loop is the retry.
    }
  }
  throw new Error(
    "Sign-in was not completed in the browser. The window is still open — finish there, or try again.",
  )
}
