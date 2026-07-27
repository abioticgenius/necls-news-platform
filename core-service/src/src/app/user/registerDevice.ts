import { Request, Response } from 'express';
import { User } from '../../db/app-db/models/user.model';
import { UserDevice } from '../../db/app-db/models/userdevice.model';


export async function registerDevice(req: Request, res: Response) {
  try {
    const { device_id, fcm_token, platform } = req.body;
    const { uid } = req.user || {};

    if (!uid) {
      return res.status(400).json({ error: "UID missing" });
    }

    const user = await User.findOne({ where: { uid } });

    if (!user) {
      return res.status(404).json({ error: "User not found" });
    }

    await UserDevice.upsert({
      user_id: user.id,
      device_id,
      fcm_token,
      platform,
      last_active_at: new Date(),
      is_active: true,
    });

    res.json({ success: true });
  } catch (err) {
    console.error("Error registering device", err);
    res.status(500).json({ error: "Failed to register device" });
  }
}
