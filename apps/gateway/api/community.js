import { cert, getApps, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';

const website = 'https://reply-cue.vercel.app';
const categories = new Set(['Sign-in', 'Installation', 'Suggestion', 'Other']);

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.headers.origin === website) {
    res.setHeader('Access-Control-Allow-Origin', website);
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
  }
  res.setHeader('Vary', 'Origin');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (!['GET', 'POST'].includes(req.method)) return res.status(405).end();
  const token = /^Bearer ([^\s]+)$/.exec(req.headers.authorization || '')?.[1];
  if (req.method === 'POST' && (!token || token.length > 8192)) {
    return res.status(401).json({ error: 'Sign in to send feedback.' });
  }
  try {
    const app = getApps()[0] || initializeApp({
      credential: cert(JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_JSON)),
    });
    const db = getFirestore(app);
    if (req.method === 'GET') {
      const result = await db.collection('desktopConnections').count().get();
      res.setHeader('Vercel-CDN-Cache-Control', 'public, s-maxage=300, stale-while-revalidate=600');
      return res.json({ connectedAccounts: result.data().count });
    }
    const identity = await getAuth(app).verifyIdToken(token, true).catch(() => null);
    if (!identity?.email_verified) return res.status(403).json({ error: 'Sign in with a verified email to send feedback.' });
    const category = req.body?.category;
    const message = typeof req.body?.message === 'string' ? req.body.message.trim() : '';
    if (!categories.has(category) || message.length < 10 || message.length > 1500) {
      return res.status(400).json({ error: 'Choose a category and enter 10–1,500 characters.' });
    }
    const now = new Date();
    const day = now.toISOString().slice(0, 10);
    try {
      await db.collection('betaFeedback').doc(identity.uid + '_' + day).create({
        category, message, createdAt: now,
      });
    } catch (error) {
      if (error.code === 6) return res.status(429).json({ error: 'You already sent feedback today. Thank you!' });
      throw error;
    }
    return res.status(201).json({ received: true });
  } catch {
    return res.status(503).json({ error: 'Temporarily unavailable. Please try again later.' });
  }
}
