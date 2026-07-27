import admin from "firebase-admin";

declare global {
  namespace Express {
    interface Request {
      appDbSequelize: Sequelize;
      user?: admin.auth.DecodedIdToken & {
        uid?: string;
        name?: string;
        picture?: string;
        email?: string;
      };
    }
  }
}
