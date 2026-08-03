// verifyFirebaseToken.js
import { Request, Response } from "express";
import { firebaseAuth, firebaseInitialized } from "./firebase";

export async function verifyFirebaseToken(req: Request, res: Response, next: any) {
  // DEMO MODE: Firebase not configured, attach a mock user and continue
  if (!firebaseInitialized || !firebaseAuth) {
    req.user = {
      uid: "demo-user-001",
      email: "demo@example.com",
      name: "Demo User",
    } as any;
    return next();
  }

  try {
    const authHeader = req.headers.authorization;
    if (!authHeader) {
      return res.status(401).json({ error: "Missing token" });
    }

    const token = authHeader.split(" ")[1];
    if (!token) {
      return res.status(401).json({ error: "Missing token" });
    }

    const decoded = await firebaseAuth.verifyIdToken(token);
    req.user = decoded;
    next();
  } catch (e) {
    console.error("Token verify error:", e);
    return res.status(401).json({ error: "Invalid token" });
  }
}
