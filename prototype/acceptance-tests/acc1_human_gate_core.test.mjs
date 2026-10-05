import assert from 'node:assert/strict'
import test from 'node:test'
import { healthReady, redactError, sanitizeControl, summarizeMachineEvidence } from '../tests/acc1_human_gate_core.mjs'

test('sanitizer keeps only routing evidence and drops private payload content', () => {
  const event = sanitizeControl(JSON.stringify({
    type: 'transcript.final', session_id: '99', turn_id: 3, event_seq: 8,
    payload: { text: 'PRIVATE SPOKEN SENTENCE', generation: 2, audio: 'PRIVATE AUDIO' },
  }), 'received', 1)
  assert.deepEqual(event, {
    order: 1, direction: 'received', type: 'transcript.final', turn_id: 3, event_seq: 8, generation: 2,
  })
  assert.equal(JSON.stringify(event).includes('PRIVATE'), false)
  assert.equal(sanitizeControl(Buffer.from('binary pcm'), 'sent', 2), null)
})

test('three full turns plus a cancelled turn and resumed completion pass aggregation', () => {
  let order = 0
  const received = []
  const sent = []
  const counts = new Map()
  const add = (collection, type, turnId, direction) => {
    const item = { order: ++order, direction, type, turn_id: turnId, event_seq: order, generation: 1 }
    collection.push(item)
    counts.set(type, (counts.get(type) || 0) + 1)
  }
  for (const turnId of [1, 2]) {
    for (const type of ['transcript.final', 'reply.text.final', 'reply.audio.chunk', 'reply.audio.complete']) add(received, type, turnId, 'received')
    add(sent, 'audio.playback.ended', turnId, 'sent')
  }
  add(sent, 'barge_in.detected', 3, 'sent')
  add(received, 'turn.cancelled', 3, 'received')
  for (const type of ['transcript.final', 'reply.text.final', 'reply.audio.chunk', 'reply.audio.complete']) add(received, type, 4, 'received')
  add(sent, 'audio.playback.ended', 4, 'sent')
  const result = summarizeMachineEvidence(received, sent, counts)
  assert.equal(result.completedTurns.length >= 3, true)
  assert.equal(result.postCancelCompleted, true)
  assert.equal(result.cancelled_count, 1)
})

test('health and error redaction are fail closed', () => {
  assert.equal(healthReady({ status: 'ready', components: { asr: 'ready', tts: 'ready' } }), true)
  assert.equal(healthReady({ status: 'ready', components: { asr: 'loading' } }), false)
  assert.equal(redactError('C:\\Users\\Alice\\private.wav /home/bob/file').includes('Alice'), false)
  assert.equal(redactError('C:\\Users\\Alice\\private.wav /home/bob/file').includes('/home/bob'), false)
})
