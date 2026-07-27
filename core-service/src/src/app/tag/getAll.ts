import { Request, Response } from 'express';
import { SeoTag } from '../../db/app-db/models/seotag.model';
import { QueryTypes, Sequelize } from 'sequelize';

export async function getAllTags(req: Request, res: Response) {
  try {
    const { limit = 100000, type } = req.query;
    const where = type ? { type: type as string } : {};
    const tags = await SeoTag.findAll({
      where,
      order: [['type', 'ASC'], ['name', 'ASC']],
      limit: Number(limit)
    });
    res.json(tags);
  } catch (error) {
    console.error('Error in getAllTags:', error);
    res.status(500).json({ error: 'Failed to fetch tags' });
  }
}

export async function getContextualTags(req: Request, res: Response) {
  try {
    const seoTags = await getRelevantTags(req?.body, req?.appDbSequelize);
    res.json(seoTags);
  } catch (err: any) {
    console.error('getContextualTags error:', err?.message ?? err);
    res.status(500).json({ error: 'Failed to fetch contextual tags' });
  }
}

export async function getRelevantTags(params: any, appDbSequelize: Sequelize) {
  const { tagIds = [], partialTagName = '', limit = 100, sortPreference = '' } = params;
  const normalizedPartial = partialTagName?.toLowerCase()?.replace(/\s+/g, '_')?.trim();

  const hasPartial = normalizedPartial.length > 0;
  const hasTagIds = Array.isArray(tagIds) && tagIds.length > 0;

  // Step 1: Compute the centroid of selected tags.
  // Done in a separate query so the result can be embedded as a typed literal
  // in the main query — this avoids GROUP BY on the vector type entirely.
  let centroidLiteral: string | null = null;
  if (hasTagIds) {
    const rows: any[] = await appDbSequelize.query(
      `SELECT AVG(embedding)::text AS vec
       FROM seo_tag
       WHERE id IN (:tagIds) AND embedding IS NOT NULL`,
      { replacements: { tagIds }, type: QueryTypes.SELECT }
    );
    centroidLiteral = rows[0]?.vec ?? null;
  }

  const requestedLimit = Number(limit);
  // Activate type-diversity pinning whenever tags are selected (even if sortPreference
  // hasn't propagated yet from the frontend) and we're not in partial-search mode.
  const hasSortPreference = (sortPreference || hasTagIds) && !hasPartial;
  // Fall back to 'Entity' when no explicit sort preference was sent (first tag selected,
  // state race condition on frontend) so results are SVD-ordered with type diversity.
  const effectiveSortPref = hasSortPreference ? (sortPreference || 'Entity') : sortPreference;
  // When pinning is active, fetch a larger pool so each type has candidates to pick from.
  // When partial search is active, fetch extra so we can find the shortest contains-matches
  // even if they would not normally appear in the top N by SVD alone.
  const fetchLimit = hasSortPreference
    ? Math.min(requestedLimit * 4, 800)
    : hasPartial
      ? Math.min(requestedLimit + 80, 300)
      : requestedLimit;

  const sql = getQuery(hasTagIds, hasPartial, effectiveSortPref, centroidLiteral);

  const seoTags = await appDbSequelize.query(sql, {
    replacements: {
      tagIds,
      limit: fetchLimit,
      hasPartial,
      exact: normalizedPartial,
      startsWith: `${normalizedPartial}%`,
      contains: `%${normalizedPartial}%`,
    },
    type: QueryTypes.SELECT,
  }) as any[];

  // When partial search is active: run a dedicated pin query that scans ALL tags
  // for whole-word matches (not limited by SVD fetch limit), then prepend pins
  // to the SVD results.  This guarantees prominent tags like "narendra_modi" always
  // surface even when there are hundreds of substring matches (e.g. "commodities").
  if (hasPartial) {
    // Correlated subcount: only counts events for the small set of whole-word matches,
    // not the entire event_seo_tag table. Fast with an index on event_seo_tag.seo_tag_id.
    const pinRows: any[] = await appDbSequelize.query(`
      SELECT
        st.*,
        array_length(string_to_array(st.name, '_'), 1) AS word_count,
        (SELECT COUNT(event_id) FROM event_seo_tag WHERE seo_tag_id = st.id) AS total_event_count
      FROM seo_tag st
      WHERE EXISTS (
        SELECT 1
        FROM unnest(string_to_array(LOWER(st.name), '_')) AS w(word)
        WHERE w.word = :exact
      )
      ORDER BY
        CASE WHEN LOWER(st.name) = :exact THEN 0 ELSE 1 END ASC,
        array_length(string_to_array(st.name, '_'), 1) ASC,
        (SELECT COUNT(event_id) FROM event_seo_tag WHERE seo_tag_id = st.id) DESC
      LIMIT 3
    `, { replacements: { exact: normalizedPartial }, type: QueryTypes.SELECT });

    const pinIds = new Set(pinRows.map((t: any) => t.id));
    const rest = seoTags.filter((t: any) => !pinIds.has(t.id));

    return [...pinRows, ...rest].slice(0, requestedLimit);
  }

  // When a sort preference is active (and not in search/partial mode), restructure results
  // so that the top 2 tags of each type appear first (in SORT_ORDER priority), followed by
  // the remaining tags in their original SVD-similarity order.
  if (hasSortPreference) {
    const PINS_PER_TYPE = 2;
    const typeOrder = getTagOrder(effectiveSortPref);

    // Group all results by type (preserving SVD order within each group)
    const typeGroups: Record<string, any[]> = {};
    for (const tag of seoTags) {
      if (!typeGroups[tag.type]) typeGroups[tag.type] = [];
      typeGroups[tag.type].push(tag);
    }

    // Collect pinned: top PINS_PER_TYPE per type, in SORT_ORDER priority.
    // Only pin tags that meet a minimum quality threshold — this prevents
    // irrelevant tags from being bolted to the front just because they are
    // the closest of their type by a noisy SVD score.
    const MIN_PIN_SVD = 0.18;
    const MIN_PIN_MATCH = 5;
    const pinnedIds = new Set<string>();
    const pinned: any[] = [];
    for (const type of typeOrder) {
      const top = (typeGroups[type] ?? [])
        .filter((tag: any) =>
          Number(tag.match_count) >= 1 &&
          (tag.svd_distance < MIN_PIN_SVD || Number(tag.match_count) >= MIN_PIN_MATCH)
        )
        .slice(0, PINS_PER_TYPE);
      for (const tag of top) {
        pinned.push(tag);
        pinnedIds.add(tag.id);
      }
    }

    // Remaining: original SVD order, excluding pinned
    const rest = seoTags.filter(tag => !pinnedIds.has(tag.id));

    return [...pinned, ...rest].slice(0, requestedLimit);
  }

  return seoTags;
}

const getCaseTagOrder = (sortPreference: string) => {
  const TAG_TYPE_ORDER = getTagOrder(sortPreference)
  return `
CASE st.type\n
  ${TAG_TYPE_ORDER.map(
    (type, index) => `WHEN '${type}' THEN ${index}`
  ).join('\n  ')}
  ELSE ${TAG_TYPE_ORDER.length}
END
`};

const getTagOrder = (sortPreference: string) => {

  let SORT_ORDER = ['Category', 'Sub Category', 'Core Event', 'Entity', 'Place', 'Associated Event', 'Impact'];

  switch (sortPreference) {
    case 'Category':
      SORT_ORDER = ['Category', 'Sub Category', 'Entity', 'Place', 'Core Event', 'Associated Event', 'Impact'];
      break;
    case 'Sub Category':
      SORT_ORDER = ['Sub Category', 'Category', 'Entity', 'Place', 'Core Event', 'Associated Event', 'Impact'];
      break;
    case 'Core Event':
      SORT_ORDER = ['Core Event', 'Entity', 'Place', 'Category', 'Sub Category', 'Associated Event', 'Impact'];
      break;
    case 'Associated Event':
      SORT_ORDER = ['Associated Event', 'Core Event', 'Sub Category', 'Category', 'Entity', 'Place', 'Impact'];
      break;
    case 'Entity':
      SORT_ORDER = ['Entity', 'Place', 'Core Event', 'Category', 'Sub Category', 'Associated Event', 'Impact'];
      break;
    case 'Place':
      SORT_ORDER = ['Place', 'Entity', 'Core Event', 'Category', 'Sub Category', 'Associated Event', 'Impact'];
      break;
    case 'Impact':
      SORT_ORDER = ['Impact', 'Category', 'Sub Category', 'Core Event', 'Entity', 'Place', 'Associated Event'];
      break;
  }
  return SORT_ORDER;
}

function getQuery(hasTagIds: boolean, hasPartial: boolean, sortPreference: any, centroidLiteral: string | null) {
  const hasCentroid = hasTagIds && centroidLiteral !== null;

  return `
    SELECT
      st.*,

      /* event co-occurrence count with selected tags (meaningful fallback when no embeddings) */
      ${hasTagIds
      ? 'COALESCE(co.co_count, 0)'
      : '0'} AS match_count,

      /* SVD cosine distance to centroid of selected tags (lower = more similar) */
      ${hasCentroid
      ? `CASE
           WHEN st.embedding IS NOT NULL
             THEN st.embedding <=> '${centroidLiteral}'::vector
           ELSE 1.0
         END`
      : '1.0'} AS svd_distance,

      /* blended rank score: SVD distance reduced by match_count signal so that
         genuine co-occurrence can overcome the SVD noise floor (~0.11–0.14) */
      ${hasCentroid
      ? `CASE
           WHEN st.embedding IS NOT NULL
             THEN (st.embedding <=> '${centroidLiteral}'::vector)
                  - LEAST(LN(1 + COALESCE(co.co_count, 0)::float) * 0.025, 0.12)
           ELSE 1.0
         END`
      : '1.0'} AS blended_score,

      /* name ranking */
      CASE
        WHEN :hasPartial = true
             AND LOWER(REPLACE(st.name, ' ', '_')) = :exact
          THEN 0
        WHEN :hasPartial = true
             AND LOWER(REPLACE(st.name, ' ', '_')) LIKE :startsWith
          THEN 1
        WHEN :hasPartial = true
             AND LOWER(REPLACE(st.name, ' ', '_')) LIKE :contains
          THEN 2
        ELSE 3
      END AS name_match_rank,

      /* word count: fewer words rank higher within the same name_match_rank bucket */
      array_length(string_to_array(st.name, '_'), 1) AS word_count,

      /* exact-match pin: 0 = exact, 1 = everything else (used to pin exact to top) */
      CASE
        WHEN :hasPartial = true
             AND LOWER(REPLACE(st.name, ' ', '_')) = :exact
          THEN 0
        ELSE 1
      END AS is_exact_match

    FROM seo_tag st

    ${hasTagIds
      ? `
      LEFT JOIN (
        SELECT est.seo_tag_id, COUNT(DISTINCT est.event_id) AS co_count
        FROM event_seo_tag est
        WHERE est.event_id IN (
          SELECT event_id FROM event_seo_tag WHERE seo_tag_id IN (:tagIds)
        )
        AND est.seo_tag_id NOT IN (:tagIds)
        GROUP BY est.seo_tag_id
      ) co ON co.seo_tag_id = st.id
      `
      : ''}

    ${hasPartial
      ? `
      WHERE
        (LOWER(REPLACE(st.name, ' ', '_')) LIKE :startsWith
        OR LOWER(REPLACE(st.name, ' ', '_')) LIKE :contains)
        ${hasTagIds ? 'AND st.id NOT IN (:tagIds)' : ''}
      `
      : hasTagIds
        ? 'WHERE st.id NOT IN (:tagIds)'
        : ''}

    ORDER BY
      /* exact match always first */
      is_exact_match ASC,

      /* blended rank: SVD distance reduced by match_count signal */
      blended_score ASC,

      /* fallback when all blended scores are equal (e.g. all embeddings NULL) */
      match_count DESC,

      /* semantic tag priority */
      ${getCaseTagOrder(sortPreference)}

    LIMIT :limit;
  `;
}
