import admin from "firebase-admin";

let firebaseInitialized = false;

if (!admin.apps.length) {
  try {
    const raw = process.env.FIREBASE_SERVICE_ACCOUNT || '{}';
    const serviceAccount = JSON.parse(raw);
    if (serviceAccount.private_key && serviceAccount.client_email && serviceAccount.project_id) {
      serviceAccount.private_key = serviceAccount.private_key.replace(/\\n/g, "\n");
      admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
      firebaseInitialized = true;
    } else {
      console.warn("[Firebase] No valid service account found — running in DEMO MODE (auth bypassed)");
    }
  } catch (e) {
    console.warn("[Firebase] Failed to initialize — running in DEMO MODE (auth bypassed):", e);
  }
}

export { firebaseInitialized };
export const firebaseAuth = firebaseInitialized ? admin.auth() : null;
export const firebaseMessaging = firebaseInitialized ? admin.messaging() : null;
