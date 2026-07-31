import { initializeApp } from "firebase/app"
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithEmailAndPassword, signOut } from "firebase/auth"

/**
 * Firebase, for the optional cloud sync.
 *
 * This file used to name `akaion-app-213b6` — a project that no longer exists.
 * Every sign-in attempt therefore ended in
 *
 *     Firebase: Error (auth/api-key-not-valid.-please-pass-a-valid-api-key.)
 *
 * and had done since the environments moved to `akaion-{dev,prod}-eu`. The
 * daemon syncs against `api.prod.akaion.com` (see `runner/service_urls.py`), so
 * the identity provider has to be the production project — signing in to one
 * project and presenting the token to another fails later and less clearly.
 *
 * A Firebase web API key is not a secret: it identifies the project, is served
 * in the bundle of every web app that uses one, and is restricted by authorised
 * domain rather than by concealment. It is checked in here for the same reason
 * the PWA checks its own in — and read from the environment first, so a fork can
 * point at its own project without patching source.
 */
const firebaseConfig = {
  apiKey:     import.meta.env.VITE_FIREBASE_API_KEY     ?? "AIzaSyBqxpPTqCkqOUEXrBXz7DG_Z4ZrmtEB6AY",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? "akaion-prod-eu.firebaseapp.com",
  projectId:  import.meta.env.VITE_FIREBASE_PROJECT_ID  ?? "akaion-prod-eu",
}

const app      = initializeApp(firebaseConfig)
export const fbAuth   = getAuth(app)
export const gProvider = new GoogleAuthProvider()
gProvider.addScope("email")
gProvider.addScope("profile")
gProvider.setCustomParameters({ prompt: "select_account" })

export { signInWithPopup, signInWithEmailAndPassword, signOut }
