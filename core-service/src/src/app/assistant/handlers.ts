import { Router, Request, Response } from 'express';
import { queryAssistant, getEventFaqs, answerEventQuestion } from './query';
import { triggerTrendingRefresh } from './trending-scheduler';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';
import { User } from '../../db/app-db/models/user.model';
import { recordActivity } from '../activity/track';

// Express handler for assistant query
async function queryAssistantHandler(req: Request, res: Response) {
  try {
    const { question } = req.body;
    const locale = (req.query.locale as string) || 'en'; // Extract locale from query params, default to 'en'

    if (!question || typeof question !== 'string' || question.trim().length === 0) {
      console.error('❌ Invalid question provided');
      return res.status(400).json({ error: 'Question is required and must be a non-empty string' });
    }

    if (!process.env.OPENAI_API_KEY) {
      console.error('❌ OPENAI_API_KEY not configured');
      return res.status(500).json({ error: 'Assistant service not configured' });
    }

    const result = await queryAssistant({
      question: question.trim(),
      sequelize: req.appDbSequelize,
      openaiApiKey: process.env.OPENAI_API_KEY,
      locale: locale,
    });

    // Track assistant query activity
    try {
      const user = await User.findOne({ where: { uid: req.user?.uid } });
      if (user) {
        await recordActivity(user, 'assistant_query');
      }
    } catch (trackError) {
      console.error('Error recording activity:', trackError);
      // Don't fail the request if activity tracking fails
    }

    // Add cache invalidation headers so frontend knows to refresh
    res.set('X-Invalidate-Cache', 'milestones,activityDates,earnedBadges,milestoneProgress');
    res.json(result);
  } catch (error) {
    console.error('Error in queryAssistantHandler:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    const errorStack = error instanceof Error ? error.stack : undefined;
    console.error('Error details:', { errorMessage, errorStack });
    res.status(500).json({
      error: 'Failed to process assistant query',
      message: errorMessage
    });
  }
}

async function getEventFaqsHandler(req: Request, res: Response) {
  try {
    const { eventId } = req.params;
    const locale = (req.query.locale as string) || 'en'; // Extract locale from query params, default to 'en'

    if (!eventId) {
      return res.status(400).json({ error: 'eventId is required' });
    }

    const faqs = await getEventFaqs(eventId, locale);
    res.json({ faqs });
  } catch (error) {
    console.error('Error in getEventFaqsHandler:', error);
    const errorMessage = error instanceof Error ? error.message : 'Failed to fetch FAQs';
    res.status(500).json({ error: errorMessage });
  }
}

async function answerEventQuestionHandler(req: Request, res: Response) {
  try {
    const { eventId } = req.params;
    const { question } = req.body;
    const locale = (req.query.locale as string) || 'en'; // Extract locale from query params, default to 'en'


    if (!eventId) {
      return res.status(400).json({ error: 'eventId is required' });
    }

    if (!question || typeof question !== 'string' || question.trim().length === 0) {
      return res.status(400).json({ error: 'Question is required and must be a non-empty string' });
    }

    if (!process.env.OPENAI_API_KEY) {
      console.error('OPENAI_API_KEY not configured');
      return res.status(500).json({ error: 'Assistant service not configured' });
    }

    const result = await answerEventQuestion({
      eventId,
      question: question.trim(),
      sequelize: req.appDbSequelize,
      openaiApiKey: process.env.OPENAI_API_KEY,
      locale: locale,
    });

    // Track assistant query activity
    try {
      const user = await User.findOne({ where: { uid: req.user?.uid } });
      if (user) {
        await recordActivity(user, 'assistant_query');
      }
    } catch (trackError) {
      console.error('Error recording activity:', trackError);
      // Don't fail the request if activity tracking fails
    }

    // Add cache invalidation headers so frontend knows to refresh
    res.set('X-Invalidate-Cache', 'milestones,activityDates,earnedBadges,milestoneProgress');
    res.json(result);
  } catch (error) {
    console.error('Error in answerEventQuestionHandler:', error);
    res.status(500).json({ error: 'Failed to answer question' });
  }
}

async function refreshTrendingHandler(req: Request, res: Response) {
  try {
    if (!process.env.OPENAI_API_KEY) {
      return res.status(500).json({ error: 'OPENAI_API_KEY not configured' });
    }

    const { categoryId } = req.query;

    const result = await triggerTrendingRefresh(
      req.appDbSequelize,
      process.env.OPENAI_API_KEY,
      categoryId as string | undefined
    );

    res.json({
      success: true,
      message: `Trending tags refreshed: ${result.matched} matched, ${result.tagged} tagged`,
      ...result,
    });
  } catch (error) {
    console.error('Error in refreshTrendingHandler:', error);
    res.status(500).json({ error: 'Failed to refresh trending tags' });
  }
}

export function assistantApi() {
  const router = Router();
  
  
  router.post('/query', verifyFirebaseToken, queryAssistantHandler);
  router.get('/events/:eventId/faqs', verifyFirebaseToken, getEventFaqsHandler);
  router.post('/events/:eventId/query', verifyFirebaseToken, answerEventQuestionHandler);
  router.get('/trending/refresh', verifyFirebaseToken, refreshTrendingHandler); // Manual refresh endpoint
  return router;
}
