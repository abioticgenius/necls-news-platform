import { Request, Response } from 'express';
import { User } from '../../db/app-db/models/user.model';

export async function getProfile(req: Request, res: Response) {
  try {
    const { uid, email, name, picture } = req?.user || {};
    if (!uid) {
      return res.status(400).json({ error: "UID missing" });
    }
    const provider = req?.user?.firebase?.sign_in_provider;
    const before = await User.findOne({ where: { uid } });
    // Sequelize upsert → insert or update based on primary key (uid)
    const user = await User.upsert(
      { uid, email, name, picture, provider, locale: "en", updatedAt: new Date() },
      { returning: true, conflictFields: ['uid'] }
    );
    const after = user[0];
    // created if it didn't exist before
    const firstTimeLogin = before ? false : true;
    return res.json({ user: after, firstTimeLogin });
  } catch (error) {
    console.error("Profile error", error);
    return res.status(500).json({ error: "Failed to fetch profile" });
  }
}
