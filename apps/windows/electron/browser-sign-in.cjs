const { createServer } = require('node:http');
const { randomBytes } = require('node:crypto');

const origin = 'https://reply-cue.vercel.app';

async function browserSignIn(provider, open, connect, signal) {
  if (!['google', 'github'].includes(provider)) throw new Error('Unsupported sign-in provider.');
  const nonce = randomBytes(32).toString('hex');
  const path = '/replycue/' + nonce;
  const server = createServer({ requestTimeout: 10000 });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const host = '127.0.0.1:' + server.address().port;
  return new Promise((resolve, reject) => {
    let used = false;
    const finish = (error, result) => {
      clearTimeout(timer);
      signal.removeEventListener('abort', cancel);
      server.close();
      if (error) reject(error); else resolve(result);
    };
    const cancel = () => finish(new Error('Browser sign-in canceled.'));
    const timer = setTimeout(() => finish(new Error('Browser sign-in expired. Try again.')), 180000);
    signal.addEventListener('abort', cancel, { once: true });
    if (signal.aborted) return cancel();
    server.on('request', async (req, res) => {
      res.setHeader('Cache-Control', 'no-store');
      res.setHeader('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'");
      res.setHeader('Content-Type', 'text/plain; charset=utf-8');
      const validOrigin = req.headers.origin === origin || req.headers.origin === 'null';
      if (used || req.method !== 'POST' || req.url !== path || req.headers.host !== host ||
          !validOrigin || req.headers['content-type']?.split(';')[0] !== 'application/x-www-form-urlencoded') {
        res.writeHead(403).end('Invalid sign-in request.');
        return;
      }
      let body = '';
      try {
        for await (const chunk of req) {
          body += chunk;
          if (body.length > 20000) {
            res.writeHead(413).end('Request too large.');
            return;
          }
        }
        const fields = new URLSearchParams(body);
        const idToken = fields.get('idToken');
        const refreshToken = fields.get('refreshToken');
        if (used || signal.aborted || !idToken || !refreshToken ||
            idToken.length >= 8192 || refreshToken.length >= 8192) {
          res.writeHead(400).end('Invalid or expired session.');
          return;
        }
        used = true;
        const result = await connect({ idToken, refreshToken });
        res.end('Signed in. You can close this tab and return to ReplyCue.');
        finish(null, result);
      } catch {
        res.writeHead(400).end('ReplyCue could not connect the account. Return to the app to try again.');
        finish(new Error('Could not connect your browser sign-in. Verify your email and try again.'));
      }
    });
    const url = new URL('/account/desktop/', origin);
    url.hash = new URLSearchParams({ provider, port: String(server.address().port), nonce }).toString();
    open(url.toString()).catch(() => finish(new Error('Could not open your default browser.')));
  });
}

module.exports = { browserSignIn };
