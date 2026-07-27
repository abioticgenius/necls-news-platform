import { Request, Response, Router } from 'express';
import { User } from '../../db/app-db/models/user.model';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';
import { recordActivity } from './track';

export async function articleReadHandler(req: Request, res: Response) {
  try {
    const { event_id, read_duration_ms } = req.body;
    const { uid } = req?.user || {};

    if (!uid) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    if (!event_id) {
      return res.status(400).json({ error: 'event_id is required' });
    }

    const user = await User.findOne({ where: { uid } });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    const milestones = await recordActivity(user, 'article_read');
    res.json({ success: true, milestones });
  } catch (error) {
    console.error('Error recording article read', error);
    res.status(500).json({ error: 'Failed to record article read' });
  }
}

export async function takeSharedHandler(req: Request, res: Response) {
  try {
    const { event_id } = req.body;
    const { uid } = req?.user || {};

    if (!uid) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    if (!event_id) {
      return res.status(400).json({ error: 'event_id is required' });
    }

    const user = await User.findOne({ where: { uid } });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    const milestones = await recordActivity(user, 'take_shared');
    res.json({ success: true, milestones });
  } catch (error) {
    console.error('Error recording share', error);
    res.status(500).json({ error: 'Failed to record share' });
  }
}

export function activityApi(): Router {
  const router = Router();
  router.post('/article-read', verifyFirebaseToken, articleReadHandler);
  router.post('/take-shared', verifyFirebaseToken, takeSharedHandler);
  return router;
}
