const modelUrl = 'https://api.replicate.com/v1/models/google/gemini-3-flash/predictions';
const outputLimit = 2048;

export function answerReserve(value) {
  const configured = Number(value);
  if (!Number.isSafeInteger(configured) || configured <= 0) {
    throw new Error('Invalid answer reservation');
  }
  // The gateway accepts at most 32,000 bytes of prompt text. At the published
  // Gemini 3 Flash rates this floor covers a conservative input token bound,
  // the full output allowance (including thinking), and framing overhead.
  return Math.max(configured, 25_000);
}

export async function generateAnswer(prompt, token, fetcher = fetch) {
  const signal = AbortSignal.timeout(15000);
  const headers = { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' };
  async function prediction(url, options = {}) {
    const response = await fetcher(url, { ...options, signal, redirect: 'error' });
    if (response.status === 429) return { status: 'rate_limited' };
    if (!response.ok) return { status: 'failed' };
    return response.json();
  }
  let result = await prediction(modelUrl, {
    method: 'POST',
    headers: { ...headers, Prefer: 'wait=10', 'Cancel-After': '14s' },
    body: JSON.stringify({
      input: { prompt, thinking_level: 'low', max_output_tokens: outputLimit },
    }),
  });
  while (['starting', 'processing'].includes(result.status) && !signal.aborted) {
    if (typeof result.id !== 'string' || !/^[a-z0-9-]+$/i.test(result.id)) return {};
    await new Promise(resolve => setTimeout(resolve, 300));
    result = await prediction('https://api.replicate.com/v1/predictions/' + result.id, { headers });
  }
  if (result.status === 'rate_limited') return { rateLimited: true };
  if (result.status !== 'succeeded') return {};
  const output = result.output;
  const text = typeof output === 'string' ? output
    : Array.isArray(output) && output.every(part => typeof part === 'string') ? output.join('') : '';
  return { text: text.trim() };
}
