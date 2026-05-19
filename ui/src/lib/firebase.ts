import { initializeApp } from "firebase/app"
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithEmailAndPassword, signOut } from "firebase/auth"

const firebaseConfig = {
  apiKey:     "AIzaSyA5RDLqm4zCJnpmYz_Ms15wgXLDEmaTiy0",
  authDomain: "akaion-app-213b6.firebaseapp.com",
  projectId:  "akaion-app-213b6",
}

const app      = initializeApp(firebaseConfig)
export const fbAuth   = getAuth(app)
export const gProvider = new GoogleAuthProvider()
gProvider.addScope("email")
gProvider.addScope("profile")
gProvider.setCustomParameters({ prompt: "select_account" })

export { signInWithPopup, signInWithEmailAndPassword, signOut }
