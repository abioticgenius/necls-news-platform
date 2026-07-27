import { Op, Sequelize } from 'sequelize';
import { Event } from '../../db/app-db/models/event.model';
import { Language } from '../../db/app-db/models/language.model';
import { LocalizedEventData } from '../../db/app-db/models/localizedeventdata.model';
import { Source } from '../../db/app-db/models/source.model';
import { Logos } from '../../db/app-db/models/logos.model';
import { CollectionSeoTag } from '../../db/app-db/models/collectionseotag.model';
import { SeoTag } from '../../db/app-db/models/seotag.model';
import { Collection } from '../../db/app-db/models/collection.model';
import { AppConfig } from '../../db/app-db/models/appconfig.model';
import { getSignedAudioUrl, getSignedImageUrl } from '../aws/client';
import { GetAllArticlesParams, PaginatedArticlesResponse } from '../../types/ReqResTypes';

/* -------------------- pagination -------------------- */

type Direction = 'older' | 'newer';

function buildCursorQuery(after?: string, before?: string) {
  if (after && before) {
    throw new Error('Use either after or before, not both');
  }

  if (!after && !before) {
    return {
      where: {},
      order: 'DESC' as const,
      direction: 'older' as Direction,
    };
  }

  const direction: Direction = after ? 'older' : 'newer';
  const [ts, id] = (after || before)!.split('|');
  const timestamp = new Date(Number(ts));

  return {
    direction,
    order: direction === 'older' ? 'DESC' : 'ASC',
    where: {
      [Op.or]: [
        { time_stamp: { [direction === 'older' ? Op.lt : Op.gt]: timestamp } },
        {
          time_stamp: timestamp,
          id: { [direction === 'older' ? Op.lt : Op.gt]: id },
        },
      ],
    },
  };
}

function buildCursors(
  items: any[],
  hasMore: boolean,
  direction: Direction
) {
  if (!items.length) return {};

  const makeCursor = (e: any) =>
    `${e.time_stamp.getTime()}|${e.id}`;

  if (direction === 'older') {
    return {
      nextCursor: hasMore ? makeCursor(items[items.length - 1]) : undefined,
      prevCursor: undefined,
    };
  }

  return {
    nextCursor: undefined,
    prevCursor: hasMore ? makeCursor(items[0]) : undefined,
  };
}

/* -------------------- tags -------------------- */

type CuratedCollectionGroup = {
  operator: 'AND' | 'OR';
  tags: string[];
};

type CuratedCollectionRule = {
  groupOperator?: 'OR';
  groups?: CuratedCollectionGroup[];
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function sqlString(value: string) {
  return `'${value}'`;
}

function tagIdList(ids: string[]) {
  return ids
    .filter(id => UUID_RE.test(id))
    .map(sqlString)
    .join(',');
}

function tagClause(tagIds: string[]) {
  return {
    [Op.in]: Sequelize.literal(`
      (
        SELECT event_id
        FROM event_seo_tag
        WHERE seo_tag_id IN ('${tagIds.join("','")}')
        GROUP BY event_id
      )
    `),
  };
}

// Implements: (orTag1 AND andTag) OR (orTag2 AND andTag) OR ...
// Which simplifies to: event has andTag AND event has at least one orTag
function orAndTagClause(orTagIds: string[], andTagId: string) {
  const safeOrIds = orTagIds.filter(id => UUID_RE.test(id)).map(sqlString).join(',');
  const safeAndId = UUID_RE.test(andTagId) ? sqlString(andTagId) : null;
  if (!safeOrIds || !safeAndId) return tagClause(orTagIds);

  return {
    [Op.in]: Sequelize.literal(`
      (
        SELECT event_id FROM event_seo_tag WHERE seo_tag_id = ${safeAndId}
        INTERSECT
        SELECT event_id FROM event_seo_tag WHERE seo_tag_id IN (${safeOrIds})
      )
    `),
  };
}

function isCuratedRule(value: any): value is CuratedCollectionRule {
  return Boolean(
    value &&
    Array.isArray(value.groups) &&
    value.groups.every((group: any) =>
      group &&
      (group.operator === 'AND' || group.operator === 'OR') &&
      Array.isArray(group.tags) &&
      group.tags.every((tag: any) => typeof tag === 'string' && tag.trim())
    )
  );
}

async function getCuratedCollectionRule(collectionId: string): Promise<CuratedCollectionRule | null> {
  const config = await AppConfig.findOne({
    where: { config_key: 'curated_collection_rules' },
  });

  const rules = config?.config_value;
  if (!rules || typeof rules !== 'object') return null;

  const collection = await Collection.findByPk(collectionId, {
    attributes: ['id', 'title'],
  });

  const candidates = [
    rules[collectionId],
    collection?.title ? rules[collection.title] : undefined,
  ];

  const rule = candidates.find(isCuratedRule);
  return rule ?? null;
}

async function advancedTagClause(rule: CuratedCollectionRule) {
  const groups = (rule.groups || []).filter(group => group.tags.length > 0);
  if (!groups.length) return null;

  const tagNames = [...new Set(groups.flatMap(group => group.tags.map(tag => tag.trim())))];
  const tags = await SeoTag.findAll({
    where: { name: { [Op.in]: tagNames } },
    attributes: ['id', 'name'],
  });

  const idsByName = new Map<string, string[]>();
  for (const tag of tags as any[]) {
    const ids = idsByName.get(tag.name) || [];
    ids.push(tag.id);
    idsByName.set(tag.name, ids);
  }

  const groupQueries = groups.map(group => {
    if (group.operator === 'OR') {
      const ids = group.tags.flatMap(tag => idsByName.get(tag.trim()) || []);
      const idsSql = tagIdList(ids);
      if (!idsSql) return '';

      return `
        SELECT event_id
        FROM event_seo_tag
        WHERE seo_tag_id IN (${idsSql})
        GROUP BY event_id
      `;
    }

    const existsClauses = group.tags.map((tag, idx) => {
      const idsSql = tagIdList(idsByName.get(tag.trim()) || []);
      if (!idsSql) return '';

      return `
        EXISTS (
          SELECT 1
          FROM event_seo_tag est_${idx}
          WHERE est_${idx}.event_id = e.id
            AND est_${idx}.seo_tag_id IN (${idsSql})
        )
      `;
    });

    if (existsClauses.some(clause => !clause)) return '';

    return `
      SELECT e.id AS event_id
      FROM event e
      WHERE ${existsClauses.join(' AND ')}
    `;
  }).filter(Boolean);

  if (!groupQueries.length) return null;

  return {
    [Op.in]: Sequelize.literal(`
      (
        ${groupQueries.join('\nUNION\n')}
      )
    `),
  };
}

async function collectionTagClause(collectionId: string) {
  const [collectionTags, collection] = await Promise.all([
    CollectionSeoTag.findAll({
      where: { collection_id: collectionId },
      attributes: ['seo_tag_id'],
    }),
    Collection.findByPk(collectionId, { attributes: ['and_tag_id', 'collection_rule'] }),
  ]);

  // STEP 1: Use collection_rule column stored on the collection (highest priority)
  const storedRule = (collection as any)?.collection_rule;
  if (storedRule && isCuratedRule(storedRule)) {
    const clause = await advancedTagClause(storedRule);
    if (clause) return clause;
  }

  // STEP 2: Fall back to curated_collection_rules app_config (legacy)
  const configRule = await getCuratedCollectionRule(collectionId);
  if (configRule) {
    const clause = await advancedTagClause(configRule);
    if (clause) return clause;
  }

  // STEP 3: Fall back to flat OR tags with optional AND scope tag
  const tagIds = collectionTags.map(t => t.seo_tag_id);
  if (!tagIds.length) return null;

  const andTagId = (collection as any)?.and_tag_id;
  return andTagId ? orAndTagClause(tagIds, andTagId) : tagClause(tagIds);
}

/* -------------------- formatting -------------------- */

async function formatEvent(event: Event) {
  const e = event.toJSON();
  const localized = e.localizedData[0];

  const faviconPaths = [
    ...new Set(
      (e.Sources || [])
        .map((s: any) => s.Logo?.favicon_s3_path)
        .filter(Boolean)
    ),
  ];

  const favicons = (
    await Promise.all(faviconPaths.map(p => getSignedImageUrl(p as string)))
  ).filter(Boolean);

  const impactTags = (e.SeoTags || [])
    .filter((t: any) => t.type === 'Impact')
    .map((t: any) => t.name as string)
    .filter(Boolean);

  return {
    id: e.id,
    image: (await getSignedImageUrl(e.image)) || '',
    audio: (await getSignedAudioUrl(localized?.audio)) || '',
    audioFullStory: await getSignedAudioUrl(localized?.audioFullStory),
    date: new Date(e.time_stamp),
    sourceCount: e.Sources?.length ?? 0,
    favicons,
    title: localized?.title ?? 'Event Title',
    description: localized?.description ?? 'Event Description',
    impactTags: impactTags.length > 0 ? impactTags : undefined,
  };
}

/* -------------------- main API -------------------- */

export async function getAllArticles({
  languageId = 'en',
  after,
  before,
  limit = 10,
  collectionId,
  orTags,
  andTag,
}: GetAllArticlesParams): Promise<PaginatedArticlesResponse> {

  /* -------- resolve tags -------- */

  let idClause = orTags?.length
    ? (andTag ? orAndTagClause(orTags, andTag) : tagClause(orTags))
    : null;

  if (collectionId) {
    idClause = await collectionTagClause(collectionId);

    if (!idClause) {
      return { articles: [], hasMore: false };
    }
  }

  /* -------- cursor logic -------- */

  const { where, order, direction } = buildCursorQuery(after, before);

  /* -------- language -------- */

  const language = await Language.findByPk(languageId);
  if (!language) {
    throw new Error(`Language not found: ${languageId}`);
  }

  /* -------- query -------- */

  const finalWhere = {
    ...where,
    ...(idClause && { id: idClause }),
  };

  const events = await Event.findAll({
    where: finalWhere,
    include: [
      {
        model: LocalizedEventData,
        as: 'localizedData',
        required: true,
        where: { language_id: language.id },
        attributes: ['title', 'description', 'audio', 'audioFullStory'],
      },
      {
        model: Source,
        as: 'Sources',
        include: [{ model: Logos, as: 'Logo', required: false }],
      },
      {
        model: SeoTag,
        as: 'SeoTags',
        attributes: ['name', 'type'],
        through: { attributes: [] },
        required: false,
      },
    ],
    order: [
      ['time_stamp', order],
      ['id', order],
    ],
    limit: limit + 1,
  });

  /* -------- pagination -------- */

  const hasMore = events.length > limit;
  const page = hasMore ? events.slice(0, limit) : events;

  if (direction === 'newer') page.reverse();

  const articles = await Promise.all(page.map(formatEvent));
  const { nextCursor, prevCursor } = buildCursors(page, hasMore, direction);

  return { articles, hasMore, nextCursor, prevCursor };
}
