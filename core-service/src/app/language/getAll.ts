import { Request, Response } from 'express';
import { Language } from '../../db/app-db/models/language.model';

export async function getAllLanguages(req: Request, res: Response) {
  try {
    const languages = await Language.findAll({
      order: [['name', 'ASC']]
    });
    
    res.json({
      success: true,
      data: languages,
      count: languages.length
    });
  } catch (error) {
    console.error('Error fetching languages:', error);
    res.status(500).json({ 
      success: false,
      error: 'Failed to fetch languages' 
    });
  }
}
