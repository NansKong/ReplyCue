import { consumeOutput } from './replicate-stream.js';
const modelUrl = 'https://api.replicate.com/v1/models/google/gemini-2.5-flash/predictions';
const outputLimit = 2048;

export function answerReserve(value) {
  const configured = Number(value);
  if (!Number.isSafeInteger(configured) || configured <= 0) {
    throw new Error('Invalid answer reservation');
  }
  // The gateway accepts at most 32,000 bytes of prompt text. This floor is a conservative reservation for
  // the input text,
  // the full output allowance and framing overhead.
  return Math.max(configured, 25_000);
}

export async function generateAnswer(prompt, token, fetcher = fetch, onUpdate = null, options = {}) {
  const signal = AbortSignal.timeout(options.assessment ? 28000 : 15000);
  const headers = { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' };
  async function prediction(url, options = {}) {
    const response = await fetcher(url, { ...options, signal, redirect: 'error' });
    if (response.status === 429) return { status: 'rate_limited' };
    if (!response.ok) return { status: 'failed' };
    return response.json();
  }
  let result = await prediction(modelUrl, {
    method: 'POST',
    headers: { ...headers, ...(onUpdate ? {} : { Prefer: 'wait=10' }), 'Cancel-After': options.assessment ? '27s' : '14s' },
    body: JSON.stringify({
      ...(onUpdate ? { stream: true } : {}),
      input: { prompt, ...(options.images ? { images: options.images } : {}), thinking_budget: 0, dynamic_thinking: false, temperature: 0.3, max_output_tokens: options.assessment ? 4096 : outputLimit },
    }),
  });
  const streamAbort = new AbortController();
  let streamTask = Promise.resolve();
  if (onUpdate && ['starting', 'processing'].includes(result.status) && result.urls?.stream) {
    const stream = new URL(result.urls.stream);
    const allowed = ['stream.replicate.com', 'streaming.api.replicate.com'];
    const serviceHost = /^stream-[a-z0-9-]+\.svc\.[a-z0-9-]+\.c\.replicate\.net$/.test(stream.hostname);
    if (stream.protocol !== 'https:' || (!allowed.includes(stream.hostname) && !serviceHost) ||
        stream.username || stream.password || stream.port) throw new Error('Invalid stream URL');
    streamTask = (async () => {
      try {
        const response = await fetcher(stream.href, {
          headers: { Authorization: 'Bearer ' + token, Accept: 'text/event-stream' },
          signal: AbortSignal.any([signal, streamAbort.signal]), redirect: 'error',
        });
        await consumeOutput(response, onUpdate);
      } catch {
        // The API poll below recovers the same prediction if streaming fails.
      }
    })();
  }
  try {
    while (['starting', 'processing'].includes(result.status) && !signal.aborted) {
      if (typeof result.id !== 'string' || !/^[a-z0-9-]+$/i.test(result.id)) return {};
      await new Promise(resolve => setTimeout(resolve, 300));
      result = await prediction('https://api.replicate.com/v1/predictions/' + result.id, { headers });
    }
  } finally {
    streamAbort.abort();
    await streamTask;
  }
  if (result.status === 'rate_limited') return { rateLimited: true };
  if (result.status !== 'succeeded') return {};
  const output = result.output;
  const text = typeof output === 'string' ? output
    : Array.isArray(output) && output.every(part => typeof part === 'string') ? output.join('') : '';
  return { text: text.trim() };
}
