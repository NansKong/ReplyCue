// Parse complete SSE frames across arbitrary UTF-8 and network chunk boundaries.
export async function consumeOutput(response, onUpdate) {
  if (!response.ok || !response.body) throw new Error('Stream unavailable');
  const decoder = new TextDecoder();
  let pending = '', output = '', done = false;
  for await (const chunk of response.body) {
    pending = (pending + decoder.decode(chunk, { stream: true })).replace(/\r\n/g, '\n');
    let boundary;
    while ((boundary = pending.indexOf('\n\n')) !== -1) {
      const frame = pending.slice(0, boundary);
      pending = pending.slice(boundary + 2);
      let event = '';
      const data = [];
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
      }
      if (event === 'error') throw new Error('Provider stream failed');
      if (event === 'output') {
        output += data.join('\n');
        if (output.length > 100000) throw new Error('Output too large');
        await onUpdate(output);
      }
      if (event === 'done') done = true;
    }
    if (pending.length > 262144) throw new Error('Invalid stream frame');
    if (done) return;
  }
  throw new Error('Provider stream ended early');
}
