import { Request, Response } from 'express';
import { Collection } from '../../db/app-db/models/collection.model';
import { SeoTag } from '../../db/app-db/models/seotag.model';
import { CollectionSeoTag } from '../../db/app-db/models/collectionseotag.model';
import { User } from '../../db/app-db/models/user.model';
import { getFirstMatchedEventImage } from '../article/helpers';
import { getSignedImageUrl } from '../aws/client';
import { getAllArticles } from '../article/getAll';
import { GetAllArticlesParams } from '../../types/ReqResTypes';
import { AppConfig } from '../../db/app-db/models/appconfig.model';
import { Op } from 'sequelize';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const PILL_TAG_MAP: Record<string, string> = {
  global:   'global',
  regional: 'regional',
  national: 'india',
  india:    'india',
  state:    'state',
};

// Reverse: DB tag name → pill label (for responses back to frontend)
const REVERSE_PILL_MAP: Record<string, string> = {
  india:    'national',
  global:   'global',
  regional: 'regional',
  state:    'state',
};

type CollectionRule = {
  groupOperator: 'OR';
  groups: Array<{ operator: 'AND' | 'OR'; tags: string[] }>;
};

export async function resolveAndTagId(andTag?: string | null): Promise<string | null> {
  if (!andTag) return null;
  if (UUID_RE.test(andTag)) return andTag;           // already a real UUID (editing existing)
  const tagName = PILL_TAG_MAP[andTag.toLowerCase()];
  if (!tagName) return null;
  const tag = await SeoTag.findOne({ where: { name: tagName }, attributes: ['id'] });
  return tag?.id ?? null;
}

// Normalize AndTag.name to the pill label expected by the frontend
function normalizeAndTag(col: any): any {
  if (col?.AndTag?.name) {
    col.AndTag = { ...col.AndTag, name: REVERSE_PILL_MAP[col.AndTag.name] ?? col.AndTag.name };
  }
  return col;
}

// ─────────────────────────────────────────────
// CREATE / UPDATE COLLECTION
// ─────────────────────────────────────────────
export async function saveCollection(req: Request, res: Response) {
  try {
    const uid = (req as any)?.user?.uid;
    const { id, title, description, orTags = [], tags = [], andTag, collectionRule } = req.body;
    const tagIds = orTags.length ? orTags : tags;
    const resolvedAndTagId = await resolveAndTagId(andTag);

    const user = await User.findOne({ where: { uid } });
    if (!title || !user?.id) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    let collection: any;

    if (id) {
      // UPDATE
      collection = await Collection.findByPk(id);
      if (!collection) {
        return res.status(404).json({ error: "Collection not found" });
      }

      await collection.update({
        title,
        description,
        is_thinko: false,
        and_tag_id: resolvedAndTagId,
        collection_rule: collectionRule || null,
      });

      // Replace OR tags - filter out the AND tag from OR tags
      await CollectionSeoTag.destroy({ where: { collection_id: id } });

      const orTagIds = tagIds.filter((tagId: string) => tagId !== resolvedAndTagId);
      const tagRows = orTagIds.map((tagId: string) => ({
        id: crypto.randomUUID(),
        collection_id: id,
        seo_tag_id: tagId,
      }));

      if (tagRows.length > 0) {
        await CollectionSeoTag.bulkCreate(tagRows);
      }

    } else {
      // CREATE — guard against duplicates from rapid concurrent requests
      const existing = await Collection.findOne({
        where: { user_id: user.id, title },
        include: [{ model: SeoTag, as: "SeoTags", through: { attributes: [] } }],
      });
      if (existing) {
        return res.json(existing);
      }

      try {
        collection = await Collection.create({
          user_id: user?.id,
          title,
          description,
          and_tag_id: resolvedAndTagId,
          collection_rule: collectionRule || null,
        });
      } catch (createErr: any) {
        if (createErr.name === 'SequelizeUniqueConstraintError') {
          const existing = await Collection.findOne({
            where: { user_id: user.id, title },
            include: [{ model: SeoTag, as: "SeoTags", through: { attributes: [] } }],
          });
          if (existing) return res.json(existing);
        }
        throw createErr;
      }

      // Filter out the AND tag from OR tags
      const orTagIds = tagIds.filter((tagId: string) => tagId !== resolvedAndTagId);
      const tagRows = orTagIds.map((tagId: string) => ({
        id: crypto.randomUUID(),
        collection_id: collection.id,
        seo_tag_id: tagId,
      }));

      if (tagRows.length > 0) {
        await CollectionSeoTag.bulkCreate(tagRows);
      }
    }

    // Return full collection with tags
    const finalCollection = await Collection.findByPk(collection.id, {
      include: [
        { model: SeoTag, as: "SeoTags", attributes: ["id", "name"], through: { attributes: [] } },
        { model: SeoTag, as: "AndTag", attributes: ["id", "name"], required: false },
      ],
    });

    return res.json(normalizeAndTag(finalCollection?.toJSON()));
  } catch (err) {
    console.error("Error saving collection:", err);
    return res.status(500).json({ error: "Failed to save collection" });
  }
}

// ─────────────────────────────────────────────
// DELETE COLLECTION
// ─────────────────────────────────────────────
export async function deleteCollection(req: Request, res: Response) {
  try {
    const { id } = req.params;

    const collection = await Collection.findByPk(id);
    if (!collection) {
      return res.status(404).json({ error: "Collection not found" });
    }

    await collection.destroy(); // CASCADE removes CollectionSeoTag entries

    res.json({ success: true });
  } catch (err) {
    console.error("Error deleting collection", err);
    res.status(500).json({ error: "Failed to delete collection" });
  }
}


// ─────────────────────────────────────────────
// LIST THINKO COLLECTIONS
// ─────────────────────────────────────────────
export async function getThinkoCollections(_req: Request, res: Response) {
  try {
    const collections = await Collection.findAll({
      where: { is_thinko: true, is_public: true },
      include: [
        {
          model: User,
          as: "User",
          where: { uid: "thinkoadminuser" },
          attributes: [], // don't need user fields
          required: true  // INNER JOIN
        },
        {
          model: SeoTag,
          as: "SeoTags",
          attributes: ["id", "name"],
          through: { attributes: [] }
        }
      ],
      order: [["createdAt", "DESC"]],
    });

    // Fetch matching event image for each collection
    const results = await populateFirstArticleImage(collections);

    res.json(results);
  } catch (err) {
    console.error("Error fetching thinko collections", err);
    res.status(500).json({ error: "Failed to fetch collections" });
  }
}

async function populateFirstArticleImage(collections: Collection[]) {
  return await Promise.all(
    collections.map(async (col: any) => {
      const tagIds = col.SeoTags.map((t: any) => t.id);

      let firstEventImage = await getFirstMatchedEventImage(tagIds, col.and_tag_id);
      // Sign backup images (S3 URIs) before returning; never return raw S3 URLs
      if (firstEventImage) {
        const signed = await getSignedImageUrl(firstEventImage);
        firstEventImage = firstEventImage.startsWith('s3://') ? (signed || '') : signed;
      }

      return normalizeAndTag({
        ...col.toJSON(),
        firstEventImage,
      });
    })
  );
}

// ─────────────────────────────────────────────
// LIST USER COLLECTIONS
// ─────────────────────────────────────────────
export async function getUserCollections(req: Request, res: Response) {
  try {
    const uid = (req as any)?.user?.uid;
    const user = await User.findOne({ where: { uid } });
    if (!user) {
      return res.json([]);
    }
    let collections = await Collection.findAll({
      where: { user_id: user.id },
      include: [
        {
          model: SeoTag,
          as: "SeoTags",
          attributes: ["id", "name"],
          through: { attributes: [] }
        },
        {
          model: SeoTag,
          as: "AndTag",
          attributes: ["id", "name"],
          required: false,
        }
      ],
      order: [["createdAt", "DESC"]],
    });
    // Fetch matching event image for each collection
    const results = await populateFirstArticleImage(collections);

    res.json(results);
  } catch (err) {
    console.error("Error fetching user collections", err);
    res.status(500).json({ error: "Failed to fetch collections" });
  }
}

// ─────────────────────────────────────────────
// GET ONE COLLECTION
// ─────────────────────────────────────────────
export async function getCollectionById(req: Request, res: Response) {
  try {
    const { id } = req.params;

    const collection: any = await Collection.findByPk(id, {
      include: [
        {
          model: SeoTag,
          as: "SeoTags",
          attributes: ["id", "name"],
          through: { attributes: [] }
        },
        {
          model: SeoTag,
          as: "AndTag",
          attributes: ["id", "name"],
          required: false,
        }
      ]
    });

    if (!collection) {
      return res.status(404).json({ error: "Collection not found" });
    }

    const tagIds = collection.SeoTags.map((t: any) => t.id);
    let firstEventImage = await getFirstMatchedEventImage(tagIds);
    // Sign backup images (S3 URIs) before returning; never return raw S3 URLs
    if (firstEventImage) {
      const signed = await getSignedImageUrl(firstEventImage);
      firstEventImage = firstEventImage.startsWith('s3://') ? (signed || '') : signed;
    }

    res.json(normalizeAndTag({
      ...collection.toJSON(),
      firstEventImage,
    }));
  } catch (err) {
    console.error("Error fetching collection", err);
    res.status(500).json({ error: "Failed to fetch collection" });
  }
}

// ─────────────────────────────────────────────
// PREVIEW COLLECTION
// ─────────────────────────────────────────────
export async function previewCollection(req: Request, res: Response) {
  try {
    const { orTags = [], tags = [], andTag } = req.body;
    const tagIds = orTags.length ? orTags : tags;
    const resolvedAndTagId = await resolveAndTagId(andTag);
    const { locale, limit = 4, after, before, collectionId } = req.query;

    const params: GetAllArticlesParams = {
      languageId: locale as string,
      limit: limit ? parseInt(limit as string) : undefined,
      after: after as string,
      before: before as string,
      collectionId: collectionId as string | undefined ?? undefined,
      orTags: tagIds as string[],
      andTag: resolvedAndTagId ?? undefined,
    };

    const result = await getAllArticles(params);
    res.json(result);
  } catch (err) {
    console.error("Error deleting collection", err);
    res.status(500).json({ error: "Failed to delete collection" });
  }
}

// ─────────────────────────────────────────────
// GET RECOMMENDED COLLECTIONS
// ─────────────────────────────────────────────
export async function getRecommendedCollections(req: Request, res: Response) {
  try {
    const uid = (req as any)?.user?.uid;
    const { limit = 4 } = req.query;
    const user = await User.findOne({ where: { uid } });
    if (!user) {
      return res.status(404).json({ error: "User not found" });
    }
    const results = await getRecommendedForUser(user.id, limit ? parseInt(limit as string) : 4);

    res.json(results);
  } catch (err) {
    console.error("Error fetching recommended collections", err);
    res.status(500).json({ error: "Failed to fetch collections" });
  }
}

async function getRecommendedForUser(userId: string, limit: number = 4) {
  const userCollections = await Collection.findAll({
    where: { user_id: userId },
    include: [
      {
        model: SeoTag,
        as: "SeoTags",
        attributes: ["id", "name"],
        through: { attributes: [] }
      }
    ],
    order: [["createdAt", "DESC"]],
  });
  const allTags = userCollections.flatMap((col: any) =>
    col.SeoTags ?? []
  );

  const eligibleCollections = await buildEligibleMappingPool(allTags, limit, limit === 40);
  // Fetch matching event image for each collection
  const collections = await Promise.all(
    eligibleCollections?.slice(0, limit).map(async (group: RecommendationMetaData) => {
      return await getThinkoCollectionForTags(group.collectionName, group?.tags?.split(',').map(t => t.trim()));
    })
  );
  // Deduplicate by collection id — multiple mapping groups can share the same collectionName
  // which resolves to the same DB row, producing duplicate entries in the response.
  const unique = Array.from(
    new Map(
      collections.filter((c): c is Collection => c !== null).map(c => [(c as any).id, c])
    ).values()
  ) as Collection[];
  return await populateFirstArticleImage(unique);
}

export async function getThinkoCollectionForTags(
  collectionName: string,
  tagNames: string[],
  collectionRule?: CollectionRule
): Promise<Collection | null> {
  if (!collectionName) return null;

  // Just find the existing thinko collection by title
  // Don't try to create it - it should already exist in the database
  const collection = await Collection.findOne({
    where: {
      title: collectionName,
      is_thinko: true,
      is_public: false
    },
    include: [
      {
        model: SeoTag,
        as: "SeoTags",
        attributes: ["id", "name"],
        through: { attributes: [] },
      },
      {
        model: SeoTag,
        as: "AndTag",
        attributes: ["id", "name"],
        required: false,
      },
    ],
  });

  return collection || null;
}

export async function createCollection(
  title: string,
  tagArray: string[],
  user: string | null = null,
  collectionRule: CollectionRule | null = null,
  andTagId: string | null = null
): Promise<Collection | null> {
  let is_thinko = false;
  if (!user) {
    is_thinko = true;
    const admin = await User.findOne({ where: { uid: "thinkoadminuser" } });
    user = admin?.id || null;
  }

  const [collection] = await Collection.findOrCreate({
    where: { user_id: user, title },
    defaults: {
      description: `A collection of ${title} articles`,
      is_public: false,
      is_thinko,
      collection_rule: collectionRule,
      and_tag_id: andTagId,
    },
  });

  // Always align DB with the latest mapping/rule.
  // This fixes stale recommended collections created before V11 (and ensures AND pill highlighting).
  await collection.update({
    description: `A collection of ${title} articles`,
    is_public: false,
    is_thinko,
    collection_rule: collectionRule,
    and_tag_id: andTagId,
  });

  await CollectionSeoTag.destroy({ where: { collection_id: collection.id } });

  if (tagArray.length > 0) {
    const tags = await SeoTag.findAll({
      where: { name: { [Op.in]: tagArray } },
    });

    const tagRows = tags.map((tag: SeoTag) => ({
      id: crypto.randomUUID(),
      collection_id: collection.id,
      seo_tag_id: tag.id,
    }));

    if (tagRows.length > 0) {
      await CollectionSeoTag.bulkCreate(tagRows);
    }
  }

  return await Collection.findByPk(collection.id, {
    include: [
      {
        model: SeoTag,
        as: "SeoTags",
        attributes: ["id", "name"],
        through: { attributes: [] },
      },
      {
        model: SeoTag,
        as: "AndTag",
        attributes: ["id", "name"],
        required: false,
      },
    ],
  });
}
export async function buildEligibleMappingPool(
  allTags: SeoTag[],
  limit: number = 4,
  showAll: boolean = false
): Promise<RecommendationMetaData[]> {

  const config = await AppConfig.findOne({
    where: { config_key: 'recommended_interests_mapping' }
  });

  const master: RecommendationMetaData[] =
    (config?.config_value as RecommendationMetaData[]) ?? [];

  if (!master.length) return [];

  const owned = new Set(allTags.map(t => t.name));

  // When showAll is true (limit=40), return all collections except those already owned
  if (showAll) {
    return master.filter(r =>
      !r?.tags?.split(",")?.some(t => owned.has(t.trim()))
    );
  }

  const useLower = allTags.length === 0;

  const grouped = master
    .filter(r =>
      useLower ? Number(r.group) < 100 : Number(r.group) > 100
    )
    .reduce((map, row) => {
      if (!map.has(row.group)) map.set(row.group, []);
      map.get(row.group)!.push(row);
      return map;
    }, new Map<string, RecommendationMetaData[]>());

  const pools = owned.size === 0
    ? [...grouped.values()]
    : [...grouped.values()].filter(rows =>
      !rows.some(r =>
        r?.tags?.split(",")?.some(t => owned.has(t.trim()))
      )
    );

  const selected: RecommendationMetaData[] = [];

  for (const pool of pools) {
    if (selected.length >= limit) break;
    selected.push(pool.splice(Math.random() * pool.length | 0, 1)[0]);
  }

  while (selected.length < limit) {
    let added = false;
    for (const pool of pools) {
      if (selected.length >= limit) break;
      if (pool.length) {
        selected.push(pool.shift()!);
        added = true;
      }
    }
    if (!added) break;
  }

  return selected;
}
type RecommendationMetaData = {
  group: string,
  collectionName: string,
  tags: string, // csv
  collectionRule?: CollectionRule,
}
