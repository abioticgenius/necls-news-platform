import { Category } from '../../db/app-db/models/category.model';
import { Request, Response } from 'express';

export async function getAllCategories(req: Request, res: Response) {
  try {
    const categories = await Category.findAll();
    res.json(categories);
  } catch (error) {
    console.error('Error in getAllCategories:', error);
    res.status(500).json({ error: 'Failed to fetch categories' });
  }
}
