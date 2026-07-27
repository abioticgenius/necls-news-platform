import FormData from 'form-data';
import { Request, Response } from 'express';
import axios from 'axios';

export async function transcribe (req: Request, res: Response) {
  try {
    if (!req.file) return res.status(400).json({ error: 'No file' });

    const openaiKey = process.env.OPENAI_API_KEY;
    if (!openaiKey) throw new Error('OPENAI_API_KEY missing');

    // Create FormData with file and model parameters
    const form = new FormData();
    form.append('file', req.file.buffer, { filename: 'recording.webm' });
    form.append('model', 'whisper-1');
    form.append('language', 'en');

    // Use axios to send FormData (handles form-data streams correctly)
    const response = await axios.post('https://api.openai.com/v1/audio/transcriptions', form, {
      headers: {
        Authorization: `Bearer ${openaiKey}`,
        ...form.getHeaders(),
      },
    });

    return res.json({ text: response.data.text || '' });
  } catch (e: any) {
    console.error('Transcription error:', e.response?.data || e.message);
    return res.status(500).json({
      error: 'Transcription failed',
      details: e.response?.data || String(e)
    });
  }
}