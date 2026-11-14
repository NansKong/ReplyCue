import { createHash } from 'node:crypto';
import { cert, getApps, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import { hasUnlimitedUsage, reserve, reserveTrial } from '../budget.js';
import { changeTrialSession, readTrial, trialUsage } from '../trial-time.js';
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
    form.set('language', 'en');
    form.set('temperature', '0');
    form.set('response_format', 'json');
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
    const unlimited = hasUnlimitedUsage(identity);
    const aiEnabled = process.env.BETA_ENABLED === 'true' &&
      Boolean(process.env.GROQ_API_KEY && process.env.REPLICATE_API_TOKEN);
    if (req.body?.kind === 'usage') {
      const account = await user.get();
      const connection = db.collection('desktopConnections').doc(user.id);
      try {
        if (!(await connection.get()).exists) await connection.create({ firstSeenAt: new Date() });
      } catch (error) {
        // Concurrent sign-ins can race to create the same marker.
        if (error.code !== 6) console.warn('Could not record desktop connection');
      }
      return res.json({
        ...trialUsage(account.data() ?? {}, Date.now(), unlimited),
        aiEnabled: aiEnabled && (unlimited || req.body.trialProtocol === 1),
        upgradeRequired: !unlimited && req.body.trialProtocol !== 1,
      });
    }
    if (!aiEnabled) return res.status(503).json({ error: 'Managed usage is unavailable' });
    const errors = {
      rate: 'Try again shortly.',
      trial: 'Your one-hour trial has ended. Check your ReplyCue profile for plan options.',
      session: 'Your session check-in expired. Resume the session to continue.',
      session_in_use: 'This account already has an active session. End it before starting another.',
      global: 'The beta is temporarily at capacity.',
    };
    const reject = code => res.status(code === 'session' || code === 'session_in_use' ? 409 : 429)
      .json({ error: errors[code], code });
    const action = req.body?.kind;
    const sessionAction = ['session-start', 'session-heartbeat', 'session-stop'].includes(action);
    const sessionId = req.body?.sessionId;
    if (!unlimited || sessionAction) {
      if (req.body?.trialProtocol !== 1) {
        return res.status(426).json({ error: 'Update ReplyCue to use the one-hour trial.', code: 'upgrade' });
      }
      if (typeof sessionId !== 'string' || !/^[a-zA-Z0-9-]{16,80}$/.test(sessionId)) {
        return res.status(400).json({ error: 'A valid session is required.' });
      }
    }
    if (sessionAction) {
      if (unlimited) return res.json({ ...trialUsage({}, Date.now(), true), aiEnabled });
      const status = await db.runTransaction(async tx => {
        const snapshot = await tx.get(user);
        const account = snapshot.data() ?? {};
        const now = Date.now();
        const change = changeTrialSession(account, sessionId, action, now);
        if (change.code) return change;
        const minute = Math.floor(now / 60000);
        const requests = account.minute === minute ? account.requests : 0;
        if (action !== 'session-stop' && requests >= 30) return { code: 'rate' };
        tx.set(user, { ...change.update, minute, requests: requests + 1 }, { merge: true });
        return { usage: trialUsage({ ...account, ...change.update }, now, false) };
      });
      if (status.code) return reject(status.code);
      return res.json({ ...status.usage, aiEnabled });
    }
    const job = operation(req.body);
    if (!job) return res.status(400).json({ error: 'Unsupported or oversized request' });
    const globalLimit = process.env.BETA_LIMIT_MICROUSD === undefined ? null : configInt('BETA_LIMIT_MICROUSD');
    const status = await db.runTransaction(async tx => {
      const [snapshot, total] = await tx.getAll(user, ...(globalLimit === null ? [] : [global]));
      const account = snapshot.data() ?? {};
      const now = Date.now();
      if (!unlimited) {
        const trial = readTrial(account, now);
        if (trial.remainingMs === 0) return 'trial';
        if (!trial.running || account.trialSessionId !== sessionId) return 'session';
      }
      const spent = account.reserved ?? 0;
      const minute = Math.floor(now / 60000);
      const requests = account.minute === minute ? account.requests : 0;
      if (requests >= 30) return 'rate';
      const userSpent = reserveTrial(spent, job.cost, null);
      if (globalLimit !== null) {
        const next = reserve(total.exists ? total.get('reserved') : 0, spent,
          job.cost, globalLimit, null);
        if (!next) return 'global';
        tx.set(global, { reserved: next.globalSpent }, { merge: true });
      }
      tx.set(user, { reserved: userSpent, minute, requests: requests + 1 }, { merge: true });
      return userSpent;
    });
    if (typeof status !== 'number') return reject(status);
    // Reservations stay charged even when a timeout leaves provider billing uncertain.
    let text;
    const streaming = job.prompt !== undefined && req.body.stream === true;
    const send = value => {
      if (res.destroyed) throw new Error('Client disconnected');
      if (!res.headersSent) {
        res.setHeader('Content-Type', 'application/x-ndjson; charset=utf-8');
        res.setHeader('X-Accel-Buffering', 'no');
        res.flushHeaders();
      }
      res.write(JSON.stringify(value) + '\n');
    };
    if (job.prompt !== undefined) {
      const result = await generateAnswer(job.prompt, process.env.REPLICATE_API_TOKEN, fetch,
        streaming ? partial => send({ text: partial, done: false }) : null);
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
    if (streaming && typeof text === 'string' && text) {
      send({ text, unlimited, done: true });
      return res.end();
    }
    if (res.headersSent) {
      send({ error: 'The answer stream did not complete. Resume to try again.', done: true });
      return res.end();
    }
    if (typeof text !== 'string' || (job.prompt !== undefined && !text)) {
      return res.status(502).json({ error: 'AI provider returned no completed answer' });
    }
    return res.json({ text, unlimited });
  } catch {
    if (res.headersSent) {
      if (!res.destroyed) res.end(JSON.stringify({ error: 'The answer stream was interrupted. Resume to try again.', done: true }) + '\n');
      return;
    }
    return res.status(503).json({ error: 'Managed usage is unavailable' });
  }
}

