import { Op, Sequelize } from "sequelize";
import {  getSignedImageUrl } from "../aws/client";
import { Event } from "../../db/app-db/models/event.model";

async function getFirstMatchedEventImage(tagIds: string[], andTagId?: string | null) {
    if (!tagIds || tagIds.length === 0) return null;
    const where: any = {};
    where.id = andTagId ? getAndOrTagsClause(tagIds, andTagId) : getTagsClause(tagIds);
    const event = await Event.findOne({
        where,
        attributes: ["id", "image"],
        order: [["time_stamp", "DESC"]],
    });

    if (!event?.image) return null;

    // Sign backup images (S3 URIs) only; regular HTTPS/HTTP URLs are returned unchanged
    const signedImageUrl = await getSignedImageUrl(event.image);
    return signedImageUrl || null;
}

function getTagsClause(tagIds: string[]): any {
    return {
        [Op.in]: Sequelize.literal(`
        (
            SELECT event_id
            FROM event_seo_tag
            WHERE seo_tag_id IN ('${tagIds.join("','")}')
            GROUP BY event_id
        )
    `) //  HAVING COUNT(DISTINCT seo_tag_id) = ${tagIds.length}
    };
}

function getAndOrTagsClause(orTagIds: string[], andTagId: string): any {
    return {
        [Op.in]: Sequelize.literal(`
        (
            SELECT event_id FROM event_seo_tag WHERE seo_tag_id = '${andTagId}'
            INTERSECT
            SELECT event_id FROM event_seo_tag WHERE seo_tag_id IN ('${orTagIds.join("','")}')
        )
    `),
    };
}

export {
    getFirstMatchedEventImage
}
