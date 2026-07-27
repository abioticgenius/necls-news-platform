import { Request, Response } from 'express';
import { User } from '../../db/app-db/models/user.model';
import { createCollection, resolveAndTagId } from '../collection/functions';
import { UserDevice } from '../../db/app-db/models/userdevice.model';
import { AppConfig } from '../../db/app-db/models/appconfig.model';

type InterestGroup = {
  group: number;
  label: string;
  interestIds: number[];
  collectionName: string | null;
  collectionTags: string | null;
  minSelection: number;
};

const SCOPE_TAGS = new Set(['india', 'global', 'state', 'regional']);

// Extract the scope tag (AND tag) from a comma-separated tags string
function extractAndTag(tagString: string | null): string | null {
  if (!tagString) return null;
  const tags = new Set(tagString.split(',').map(t => t.trim().toLowerCase()));
  for (const scope of SCOPE_TAGS) {
    if (tags.has(scope)) return scope;
  }
  return null;
}

export async function updateProfile(req: Request, res: Response) {
  try {
    const { interests } = req.body;
    const { uid } = req?.user || {};

    if (!uid) {
      return res.status(401).json({ error: "Unauthorized" });
    }

    if (!Array.isArray(interests)) {
      return res.status(400).json({ error: "Interests must be an array" });
    }

    const user = await User.findOne({ where: { uid } });

    if (!user) {
      return res.status(404).json({ error: "User not found" });
    }

    const existing = Array.isArray(user.interests)
      ? user.interests
      : [];
    const mergedMap = new Map<string, any>();

    [...existing, ...interests].forEach(item => {
      mergedMap.set(item.label, {
        ...mergedMap.get(item.label), // preserve old values (like collectionId)
        ...item                      // override with latest if needed
      });
    });
    const merged = Array.from(mergedMap.values());
    const [groupConfig, interestsConfig] = await Promise.all([
      AppConfig.findOne({ where: { config_key: 'onboarding_interest_groups' } }),
      AppConfig.findOne({ where: { config_key: 'onboarding_interests' } }),
    ]);
    const groups: InterestGroup[] = (groupConfig?.config_value as InterestGroup[]) ?? [];

    const idToGroup = new Map<number, InterestGroup>();
    for (const g of groups) {
      for (const id of g.interestIds) idToGroup.set(id, g);
    }

    // Fallback: resolve id from label if client sends interests without id
    const interestItems: any[] = (interestsConfig?.config_value as any[]) ?? [];
    const labelToId = new Map<string, number>(
      interestItems.filter(i => i.id != null).map((i: any) => [i.label, Number(i.id)])
    );

    // Stamp group + id onto each interest so it persists in the interests JSONB
    for (const interest of merged) {
      const id = interest.id != null ? Number(interest.id) : labelToId.get(interest.label);
      const g = id != null ? idToGroup.get(id) : undefined;
      if (g) {
        if (interest.id == null) interest.id = id;
        interest.group = g.group;
      }
    }

    // Count selected interests per group
    const groupCount = new Map<number, number>();
    for (const interest of merged) {
      if (interest.group !== undefined)
        groupCount.set(interest.group, (groupCount.get(interest.group) ?? 0) + 1);
    }

    // Groups where selected count meets the threshold
    const eligibleGroupIds = new Set<number>(
      [...groupCount.entries()]
        .filter(([gId, count]) => {
          const g = groups.find(x => x.group === gId);
          return g && count >= g.minSelection;
        })
        .map(([gId]) => gId)
    );

    const groupCollectionDoneThisCall = new Set<number>();
    for (const interest of merged) {
      const g = interest.group !== undefined
        ? groups.find(x => x.group === interest.group)
        : undefined;

      if (g && eligibleGroupIds.has(g.group) && g.collectionTags && g.collectionName) {
        // Eligible group — create one shared collection, skip individual
        const alreadyGrouped = merged.some(
          i => i.group === interest.group && i.groupCollectionCreated
        );
        if (!alreadyGrouped && !groupCollectionDoneThisCall.has(interest.group)) {
          const andTag = extractAndTag(g.collectionTags);
          const tagArray = g.collectionTags.split(',')
            .map((t: string) => t.trim())
            .filter((t: string) => t.toLowerCase() !== andTag);
          const andTagId = andTag ? await resolveAndTagId(andTag) : null;
          await createCollection(g.collectionName, tagArray, user.id, null, andTagId);
          for (const i of merged) {
            if (i.group === interest.group) i.groupCollectionCreated = true;
          }
          groupCollectionDoneThisCall.add(interest.group);
        }
        if (!interest.collectionCreated) interest.collectionCreated = true;
      } else {
        // Ungrouped, below threshold, or group has no collection — individual collection
        if (!interest.collectionCreated && interest.tags) {
          const andTag = extractAndTag(interest.tags);
          const tagArray = interest.tags.split(',')
            .map((t: string) => t.trim())
            .filter((t: string) => t.toLowerCase() !== andTag);
          const andTagId = andTag ? await resolveAndTagId(andTag) : null;
          await createCollection(interest.collectionName || interest.label, tagArray, user.id, null, andTagId);
          interest.collectionCreated = true;
        }
      }
    }

    // NOW update user (after loop finishes)
    await user.update({
      interests: merged,
    });
    return res.json({ success: true, interests: merged });

  } catch (error) {
    console.error("Error updating profile", error);
    return res.status(500).json({ error: "Failed to update user" });
  }
}

export async function migrateUser(req: Request, res: Response) {
  const sequelize = req.appDbSequelize;
  const transaction = await sequelize.transaction();

  try {
    const { anonymousUid } = req.body;
    const { uid: realUid } = req.user || {};

    if (!realUid) {
      return res.status(401).json({ error: "Unauthorized" });
    }

    // ------------------------------------------------
    // Get or create REAL user
    // ------------------------------------------------
    let realUser = await User.findOne({
      where: { uid: realUid },
      transaction,
    });

    if (!realUser) {
      realUser = await User.create(
        {
          uid: realUid,
          interests: [],
        },
        { transaction }
      );
    }

    // ------------------------------------------------
    // Find anonymous user
    // ------------------------------------------------
    const anonymousUser = anonymousUid
      ? await User.findOne({
        where: { uid: anonymousUid },
        transaction,
      })
      : null;

    if (!anonymousUser) {
      await transaction.commit();
      return res.json({ success: true });
    }

    // ------------------------------------------------
    // Merge interests
    // ------------------------------------------------
    const anonInterests: any[] = Array.isArray(anonymousUser.interests)
      ? anonymousUser.interests
      : [];

    const realInterests: any[] = Array.isArray(realUser.interests)
      ? realUser.interests
      : [];

    const mergedMap = new Map<string, any>();

    [...realInterests, ...anonInterests].forEach((item) => {
      mergedMap.set(item.label, {
        ...mergedMap.get(item.label),
        ...item,
      });
    });

    const mergedInterests = Array.from(mergedMap.values());

    // ------------------------------------------------
    // Transfer devices safely
    // ------------------------------------------------

    const devices = await UserDevice.findAll({
      where: { user_id: anonymousUser.id },
      transaction,
    });

    for (const device of devices) {
      const existing = await UserDevice.findOne({
        where: {
          user_id: realUser.id,
          device_id: device.device_id,
        },
        transaction,
      });

      if (existing) {
        // Update token if needed
        await existing.update(
          {
            fcm_token: device.fcm_token,
            last_active_at: new Date(),
          },
          { transaction }
        );

        await device.destroy({ transaction });
      } else {
        await device.update(
          { user_id: realUser.id },
          { transaction }
        );
      }
    }

    // ------------------------------------------------
    // Update real user
    // ------------------------------------------------

    await realUser.update(
      { interests: mergedInterests },
      { transaction }
    );

    // ------------------------------------------------
    // Delete anonymous user
    // ------------------------------------------------

    await anonymousUser.destroy({ transaction });

    await transaction.commit();

    return res.json({ success: true });
  } catch (error) {
    await transaction.rollback();
    console.error("Migration failed", error);

    return res.status(500).json({
      error: "Migration failed",
    });
  }
}
