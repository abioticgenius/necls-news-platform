// verifyFirebaseToken.js
import { Request, Response } from "express";
import { firebaseAuth } from "./firebase";

export async function verifyFirebaseToken(req: Request, res: Response, next: any) {
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
