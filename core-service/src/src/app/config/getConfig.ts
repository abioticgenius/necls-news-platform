import { Request, Response } from 'express';
import { AppConfig } from '../../db/app-db/models/appconfig.model';
import { getSignedImageUrl } from '../aws/client';
import { normalizeString } from '../../helper';

export async function getConfig(req: Request, res: Response) {
  try {
    const { key } = req.params;

    const config = await AppConfig.findOne({
      where: { config_key: key },
    });

    if (!config) {
      return res.json(null);
    }

    let value = config.config_value;

    if (key === "onboarding_interests" && Array.isArray(value)) {
      value = await Promise.all(
        value.map(async (interest: any) => ({
          ...interest,
          icon: await getSignedImageUrl(
            `s3://${process.env.ONBOARDING_BUCKET_PATH}/${normalizeString(
              interest.label
            )}.svg`
          ),
        }))
      );
    }

    return res.json(value);
  } catch (error) {
    console.error('Error in getConfig:', error);
    res.status(500).json({ error: 'Failed to fetch config' });
  }
}