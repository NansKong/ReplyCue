import { createHash } from 'node:crypto';
import { cert, getApps, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import { reserve, reserveTrial } from '../budget.js';
import { answerReserve, generateAnswer } from '../replicate-answer.js';

function configInt(name) {
  const value = Number(process.env[name]);
  if (!Number.isSafeInteger(value) || value <= 0) throw new Error('Invalid configuration');
  return value;
}

function operation(body) {
  if (body?.kind === 'answer' && typeof body.prompt === 'string' &&
      Buffer.byteLength(body.prompt) <= 32000 && body.prompt.trim()) {
    return { prompt: body.prompt, cost: answerReserve(process.env.ANSWER_RESERVE_MICROUSD) };
  }
  if (body?.kind === 'transcribe' && typeof body.pcm === 'string' &&
      body.pcm.length <= 896000 && /^[A-Za-z0-9+/]+={0,2}$/.test(body.pcm)) {
    const pcm = Buffer.from(body.pcm, 'base64');
    if (!pcm.length || pcm.length > 672000 || pcm.length % 2) return null;
    const wav = Buffer.alloc(44);
    wav.write('RIFF'); wav.writeUInt32LE(36 + pcm.length, 4); wav.write('WAVEfmt ', 8);
    wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
    wav.writeUInt32LE(16000, 24); wav.writeUInt32LE(32000, 28);
    wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34);
    wav.write('data', 36); wav.writeUInt32LE(pcm.length, 40);
    const form = new FormData();
    form.set('model', 'whisper-large-v3-turbo');
    form.set('file', new Blob([wav, pcm], { type: 'audio/wav' }), 'turn.wav');
    return { path: 'audio/transcriptions', cost: configInt('AUDIO_RESERVE_MICROUSD'),
      body: form, output: result => result.text };
  }
  return null;
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST required' });
  const token = /^Bearer ([^\s]+)$/.exec(req.headers.authorization || '')?.[1];
  if (!token || token.length > 8192) return res.status(401).json({ error: 'Sign in required' });
  try {
    const app = getApps()[0] || initializeApp({
      credential: cert(JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_JSON)),
    });
    const identity = await getAuth(app).verifyIdToken(token, true).catch(() => null);
    if (!identity) return res.status(401).json({ error: 'Sign in again' });
    if (!identity.email_verified || !identity.email) return res.status(403).json({ error: 'Verify your email' });
    const db = getFirestore(app);
    const global = db.doc('managedBudgets/beta');
    const email = identity.email.trim().toLowerCase();
    const allowed = process.env.BETA_ALLOWED_EMAILS?.split(',').map(value => value.trim().toLowerCase());
    if (allowed && !allowed.includes(email)) return res.status(403).json({ error: 'Beta invitation required' });
    const user = db.collection('managedUsers').doc(createHash('sha256').update(email).digest('hex'));
    const trialLimit = configInt('TRIAL_LIMIT_MICROUSD');
    if (req.body?.kind === 'usage') {
      const account = await user.get();
      const connection = db.collection('desktopConnections').doc(user.id);
      try {
        if (!(await connection.get()).exists) await connection.create({ firstSeenAt: new Date() });
      } catch (error) {
        // Concurrent sign-ins can race to create the same marker.
        if (error.code !== 6) console.warn('Could not record desktop connection');
      }
      return res.json({ remainingMicroUsd: Math.max(0, trialLimit - (account.get('reserved') ?? 0)) });
    }
    const job = operation(req.body);
    if (!job) return res.status(400).json({ error: 'Unsupported or oversized request' });
    if (!process.env.GROQ_API_KEY || !process.env.REPLICATE_API_TOKEN || process.env.BETA_ENABLED !== 'true') {
      return res.status(503).json({ error: 'Managed usage is unavailable' });
    }
    const globalLimit = process.env.BETA_LIMIT_MICROUSD === undefined ? null : configInt('BETA_LIMIT_MICROUSD');
    const status = await db.runTransaction(async tx => {
      const [account, total] = await tx.getAll(user, ...(globalLimit === null ? [] : [global]));
      const spent = account.exists ? account.get('reserved') : 0;
      const minute = Math.floor(Date.now() / 60000);
      const requests = account.get('minute') === minute ? account.get('requests') : 0;
      if (requests >= 30) return 'rate';
      const userSpent = reserveTrial(spent, job.cost, trialLimit);
      if (userSpent === null) return 'trial';
      if (globalLimit !== null) {
        const next = reserve(total.exists ? total.get('reserved') : 0, spent,
          job.cost, globalLimit, trialLimit);
        if (!next) return 'global';
        tx.set(global, { reserved: next.globalSpent }, { merge: true });
      }
      tx.set(user, { reserved: userSpent, minute, requests: requests + 1 }, { merge: true });
      return userSpent;
    });
    if (typeof status !== 'number') {
      const errors = {
        rate: 'Try again shortly.',
        trial: 'Your free trial allowance is used up. Check your ReplyCue profile for plan options.',
        global: 'The beta is temporarily at capacity.',
      };
      return res.status(429).json({ error: errors[status], code: status });
    }
    // Reservations stay charged even when a timeout leaves provider billing uncertain.
    let text;
    if (job.prompt !== undefined) {
      const result = await generateAnswer(job.prompt, process.env.REPLICATE_API_TOKEN);
      if (result.rateLimited) return res.status(429).json({ error: 'Answer provider is busy. Try again shortly.', code: 'provider_rate' });
      text = result.text;
    } else {
      const response = await fetch('https://api.groq.com/openai/v1/' + job.path, {
        method: 'POST', headers: { Authorization: 'Bearer ' + process.env.GROQ_API_KEY },
        body: job.body, signal: AbortSignal.timeout(15000), redirect: 'error',
      });
      if (response.status === 429) {
        return res.status(429).json({ error: 'Transcription provider is busy. Try again shortly.', code: 'provider_rate' });
      }
      if (!response.ok) return res.status(502).json({ error: 'Transcription provider unavailable' });
      text = job.output(await response.json());
    }
    if (typeof text !== 'string' || (job.prompt !== undefined && !text)) {
      return res.status(502).json({ error: 'AI provider returned no completed answer' });
    }
    return res.json({ text, remainingMicroUsd: trialLimit - status });
  } catch {
    return res.status(503).json({ error: 'Managed usage is unavailable' });
  }
}

