import test from 'node:test';
import assert from 'node:assert/strict';
import { answerReserve, generateAnswer } from './replicate-answer.js';

test('Gemini gets the original ReplyCue prompt with bounded low thinking', async () => {
  const prompt = 'Use only résumé evidence.\n\nCONTEXT:\n{"resume":"Python and SQL"}';
  let calls = 0;
  const result = await generateAnswer(prompt, 'fake-token', async (url, options) => {
    calls++;
    assert.equal(url, 'https://api.replicate.com/v1/models/google/gemini-3-flash/predictions');
    assert.deepEqual(JSON.parse(options.body).input, {
      prompt, thinking_level: 'low', max_output_tokens: 2048,
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
