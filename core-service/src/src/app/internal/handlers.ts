import { Router, Request, Response } from 'express';
import { Op } from 'sequelize';
import { getActiveTokens, sendMulticast } from '../notification/notification.service';
import { SeoTag } from '../../db/app-db/models/seotag.model';
import { Collection } from '../../db/app-db/models/collection.model';
import { CollectionSeoTag } from '../../db/app-db/models/collectionseotag.model';
import { EventSeoTag } from '../../db/app-db/models/eventseotag.model';
import { User } from '../../db/app-db/models/user.model';

function normalizeDeepLink(link: string): string {
  try {
    const url = new URL(link);
    if (url.hostname === 'app.thinko.in') {
      const articleId = url.searchParams.get('articleId');
      const collectionId = url.searchParams.get('collectionId');
      const selectedTab = url.searchParams.get('selectedTab') ?? 'read';
      if (url.pathname === '/radio_player' && articleId) {
        const params = new URLSearchParams({ articleId });
        if (collectionId) params.set('collectionId', collectionId);
        return `thinkonewsapp://radio_player?${params.toString()}`;
      }
      if (articleId) return `thinkonewsapp://immersrsive_news_article?articleId=${articleId}`;
      if (collectionId) return `thinkonewsapp://home?selectedTab=${selectedTab}&collectionId=${collectionId}`;
    }
  } catch {
    // not a valid URL, return as-is
  }
  return link;
}

function verifyInternalSecret(req: Request, res: Response): boolean {
  const secret = process.env.INTERNAL_API_SECRET;
  if (!secret) {
    res.status(500).json({ error: 'INTERNAL_API_SECRET not configured' });
    return false;
  }
  if (req.headers['x-internal-secret'] !== secret) {
    res.status(403).json({ error: 'Forbidden' });
    return false;
  }
  return true;
}

export function internalApi(): Router {
  const router = Router();

  // ─────────────────────────────────────────────
  // Send breaking news notifications
  // ─────────────────────────────────────────────
  router.post('/notifications/breaking-news', async (req: Request, res: Response) => {
    if (!verifyInternalSecret(req, res)) return;

    const { title, body, link, image, target_user_ids } = req.body as {
      title?: string;
      body?: string;
      link?: string;
      image?: string;
      target_user_ids?: string[];
    };
    if (!title || !body) {
      res.status(400).json({ error: 'title and body are required' });
      return;
    }

    try {
      const where = Array.isArray(target_user_ids) && target_user_ids.length > 0
        ? { user_id: { [Op.in]: target_user_ids } }
        : {};
      const tokens = await getActiveTokens(where);
      if (tokens.length === 0) {
        res.json({ success: true, sent_count: 0, failed_count: 0 });
        return;
      }

      const normalizedLink = link ? normalizeDeepLink(link) : undefined;

      const fcmData: Record<string, string> = {};
      if (normalizedLink) fcmData.link = normalizedLink;
      if (image) fcmData.image = image;

      const { sent, failed } = await sendMulticast(
        tokens, title, body,
        { imageUrl: image, data: fcmData }
      );
      console.log(`[Notifications] Breaking news sent: ${sent} success, ${failed} failed`);
      res.json({ success: true, sent_count: sent, failed_count: failed });
    } catch (err) {
      console.error('[Notifications] Breaking news error:', err);
      res.status(500).json({ error: 'Failed to send breaking news notification' });
    }
  });

  // ─────────────────────────────────────────────
  // Update "For You" collection with top articles
  // ─────────────────────────────────────────────
  router.post('/update-for-you-collection', async (req: Request, res: Response) => {
    if (!verifyInternalSecret(req, res)) return;

    const { event_ids } = req.body as { event_ids?: string[] };
    if (!Array.isArray(event_ids) || event_ids.length === 0) {
      return res.status(400).json({ error: 'event_ids array is required and must not be empty' });
    }

    try {
      // 1. Get thinkoadminuser's internal UUID
      const adminUser = await User.findOne({ where: { uid: 'thinkoadminuser' } });
      if (!adminUser) {
        return res.status(400).json({ error: 'thinkoadminuser not found in database' });
      }

      // 2. Upsert the "for_you" seo_tag (created once, reused every run)
      const [seoTag] = await SeoTag.findOrCreate({
        where: { name: 'for_you', type: 'tag' },
        defaults: { name: 'for_you', type: 'tag' }
      });

      // 3. Upsert the "For You" collection (is_thinko=true, is_public=true → visible in app)
      const [collection] = await Collection.findOrCreate({
        where: { user_id: adminUser.id, title: 'For You' },
        defaults: {
          user_id: adminUser.id,
          title: 'For You',
          description: 'AI-curated top news, updated every 6 hours',
          is_thinko: true,
          is_public: true
        }
      });

      // 4. Link the collection to the tag (idempotent)
      await CollectionSeoTag.findOrCreate({
        where: { collection_id: collection.id, seo_tag_id: seoTag.id },
        defaults: { collection_id: collection.id, seo_tag_id: seoTag.id }
      });

      // 5. Clear previous events from the "For You" tag
      await EventSeoTag.destroy({ where: { seo_tag_id: seoTag.id } });

      // 6. Insert new top event IDs
      const eventTagRows = event_ids.map((event_id: string) => ({
        event_id,
        seo_tag_id: seoTag.id,
        weight: 100,
        role: 'core' as const
      }));

      if (eventTagRows.length > 0) {
        await EventSeoTag.bulkCreate(eventTagRows);
      }

      console.log(`[ForYou] Collection updated with ${event_ids.length} articles`);
      res.json({
        success: true,
        message: `'For You' collection updated with ${event_ids.length} articles`,
        collection_id: collection.id,
        tag_id: seoTag.id,
        event_count: event_ids.length
      });
    } catch (err) {
      console.error('[ForYou] Error updating collection:', err);
      res.status(500).json({ error: 'Failed to update For You collection' });
    }
  });

  return router;
}
