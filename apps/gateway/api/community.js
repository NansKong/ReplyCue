import { createHash } from 'node:crypto';
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
    if (!identity) return res.status(401).json({ error: 'Sign in again to continue.' });
    if (!identity.email_verified || !identity.email) {
      return res.status(403).json({ error: 'Verify your email to continue.' });
    }
    if (req.body?.kind === 'profile') {
      const email = identity.email.trim().toLowerCase();
      const allowed = process.env.BETA_ALLOWED_EMAILS?.split(',').map(value => value.trim().toLowerCase());
      if (allowed && !allowed.includes(email)) {
        return res.status(403).json({ error: 'An invitation is required for trial access.' });
      }
      const limitMicroUsd = Number(process.env.TRIAL_LIMIT_MICROUSD);
      if (!Number.isSafeInteger(limitMicroUsd) || limitMicroUsd <= 0) {
        return res.status(503).json({ error: 'Trial usage is unavailable right now.' });
      }
      const account = await db.collection('managedUsers').doc(createHash('sha256').update(email).digest('hex')).get();
      const reserved = account.exists ? account.get('reserved') : 0;
      if (!Number.isSafeInteger(reserved) || reserved < 0) {
        return res.status(503).json({ error: 'Trial usage is unavailable right now.' });
      }
      return res.json({
        limitMicroUsd,
        remainingMicroUsd: Math.max(0, limitMicroUsd - reserved),
        aiEnabled: process.env.BETA_ENABLED === 'true' && Boolean(process.env.GROQ_API_KEY),
      });
    }
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
