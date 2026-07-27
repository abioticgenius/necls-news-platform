-- Remove duplicate (user_id, title) pairs, keeping the row with the latest created_at (or highest id if no timestamp)
DELETE FROM collection
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (PARTITION BY user_id, title ORDER BY "createdAt" DESC, id DESC) AS rn
        FROM collection
    ) dupes
    WHERE rn > 1
);

ALTER TABLE collection
ADD CONSTRAINT collection_user_title_unique UNIQUE (user_id, title);
