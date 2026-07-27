import { Router, Request, Response } from 'express';
import { getAllArticles } from './getAll';
import { getArticleById } from './getById';
import { getArticleSources } from './getSources';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';

// Express handler for getting all articles
async function getAllArticlesHandler(req: Request, res: Response) {
  try {
    const { locale, after, before, limit, category, collectionId } = req.query;
    
    const params = {
      languageId: locale as string, // Convert locale to languageId internally
      after: after as string,
      before: before as string,
      limit: limit ? parseInt(limit as string) : undefined,
      // category: category as string | undefined ?? undefined,
      collectionId: collectionId as string | undefined ?? undefined,
    };
    
    const result = await getAllArticles(params);
    res.json(result);
  } catch (error) {
    console.error('Error in getAllArticlesHandler:', error);
    res.status(500).json({ error: 'Failed to fetch articles' });
  }
}

// Express handler for getting article by ID
async function getArticleByIdHandler(req: Request, res: Response) {
  try {
    const { id } = req.params;
    const { locale } = req.query;
    
    const article = await getArticleById(id, (locale as string) || 'en');
    
    if (!article) {
      return res.status(404).json({ error: 'Article not found' });
    }
    
    res.json(article);
  } catch (error) {
    console.error('Error in getArticleByIdHandler:', error);
    res.status(500).json({ error: 'Failed to fetch article' });
  }
}

// Express handler for getting article sources by ID
async function getArticleSourcesHandler(req: Request, res: Response) {
  try {
    const { id } = req.params;
    
    const sources = await getArticleSources(id);
    res.json(sources);
  } catch (error) {
    console.error('Error in getArticleSourcesHandler:', error);
    res.status(500).json({ error: 'Failed to fetch article sources' });
  }
}

export function articleApi() {
  const router = Router();
  router.get('/', verifyFirebaseToken, getAllArticlesHandler);
  router.get('/:id/sources', verifyFirebaseToken, getArticleSourcesHandler);
  router.get('/:id', verifyFirebaseToken, getArticleByIdHandler);
  return router;
}
