import test from 'node:test';
import assert from 'node:assert/strict';
import { answerReserve, generateAnswer } from './replicate-answer.js';

test('Gemini gets the original ReplyCue prompt with thinking disabled and bounded output', async () => {
  const prompt = 'Use only résumé evidence.\n\nCONTEXT:\n{"resume":"Python and SQL"}';
  let calls = 0;
  const result = await generateAnswer(prompt, 'fake-token', async (url, options) => {
    calls++;
    assert.equal(url, 'https://api.replicate.com/v1/models/google/gemini-2.5-flash/predictions');
    assert.deepEqual(JSON.parse(options.body).input, {
      prompt, thinking_budget: 0, dynamic_thinking: false, temperature: 0.3, max_output_tokens: 2048,
    });
    assert.equal(options.headers.Prefer, 'wait=10');
    assert.equal(options.headers['Cancel-After'], '14s');
    return Response.json({ status: 'succeeded', output: ['I use Python ', 'and SQL.'] });
  });
  assert.deepEqual(result, { text: 'I use Python and SQL.' });
  assert.equal(calls, 1);
});

test('an unfinished prediction is polled on Replicate and partial output is withheld', async () => {
  let calls = 0;
  const result = await generateAnswer('prompt', 'fake-token', async url => {
    if (++calls === 1) return Response.json({ id: 'sample-1', status: 'processing', output: ['Partial'] });
    assert.equal(url, 'https://api.replicate.com/v1/predictions/sample-1');
    return Response.json({ status: 'canceled', output: ['Partial'] });
  });
  assert.deepEqual(result, {});
  assert.equal(calls, 2);
});

test('an old lower reservation cannot underfund a Gemini answer', () => {
  assert.equal(answerReserve('15000'), 25000);
  assert.equal(answerReserve('30000'), 30000);
  assert.throws(() => answerReserve(undefined));
});

test('streamed updates arrive before authoritative completion, with split UTF-8 and CRLF', async () => {
  let calls = 0;
  const updates = [];
  const result = await generateAnswer('grounded prompt', 'fake-token', async (url, options) => {
    calls++;
    if (calls === 1) {
      assert.equal(JSON.parse(options.body).stream, true);
      assert.equal(options.headers.Prefer, undefined);
      return Response.json({id:'sample-1',status:'processing',urls:{stream:'https://stream-b.svc.ric2.c.replicate.net/example'}});
    }
    if (calls === 2) {
      const bytes = new TextEncoder().encode('event: output\r\ndata: Résumé.\r\n\r\nevent: done\r\ndata: {}\r\n\r\n');
      return new Response(new ReadableStream({
        start(controller) {
          for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
          controller.close();
        },
      }));
    }
    assert.deepEqual(updates, ['Résumé.']);
    return Response.json({status:'succeeded',output:['Résumé.']});
  }, text => updates.push(text));
  assert.equal(result.text, 'Résumé.');
  assert.equal(calls, 3);
});

test('untrusted stream hosts are rejected before sending provider credentials', async () => {
  let calls = 0;
  await assert.rejects(generateAnswer('prompt', 'fake-token', async () => {
    calls++;
    return Response.json({status:'processing',urls:{stream:'https://example.com/steal'}});
  }, () => {}), /Invalid stream URL/);
  assert.equal(calls, 1);
});

test('an interrupted stream cannot turn a partial answer into a completed answer', async () => {
  let calls = 0;
  const result = await generateAnswer('prompt', 'fake-token', async () => {
    if (++calls === 1) return Response.json({id:'example',status:'processing',urls:{stream:'https://stream.replicate.com/example'}});
    if (calls === 2) return new Response('event: output\ndata: Partial\n\n');
    return Response.json({status:'failed',output:['Partial']});
  }, () => {});
  assert.deepEqual(result, {});
  assert.equal(calls, 3);
});

test('stream connection failure polls the same prediction without another paid request', async () => {
  let calls = 0;
  const result = await generateAnswer('prompt', 'fake-token', async (url, options) => {
    calls++;
    if (calls === 1) return Response.json({id:'same-prediction',status:'processing',urls:{stream:'https://stream.replicate.com/example'}});
    if (calls === 2) throw new Error('Connection unavailable');
    assert.equal(url, 'https://api.replicate.com/v1/predictions/same-prediction');
    assert.equal(options.method, undefined);
    return Response.json({status:'succeeded',output:['Complete answer.']});
  }, () => {});
  assert.equal(result.text, 'Complete answer.');
  assert.equal(calls, 3);
});
