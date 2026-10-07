export function sanitizeControl(payload, direction, order) {
  if (typeof payload !== 'string') return null
  let value
  try { value = JSON.parse(payload) } catch { return null }
  if (!value || typeof value.type !== 'string') return null
  return {
    order,
    direction,
    type: value.type,
    turn_id: Number.isInteger(value.turn_id) ? value.turn_id : null,
    event_seq: Number.isInteger(value.event_seq) ? value.event_seq : null,
    generation: Number.isInteger(value.payload?.generation)
      ? value.payload.generation
      : Number.isInteger(value.generation) ? value.generation : null,
  }
}

function turnsFor(type, collection) {
  return new Set(collection.filter((item) => item.type === type && item.turn_id !== null).map((item) => item.turn_id))
}

function intersect(...sets) {
  const [first, ...rest] = sets
  return [...first].filter((value) => rest.every((set) => set.has(value)))
}

export function summarizeMachineEvidence(received, sentControls, eventCounts) {
  const transcripts = turnsFor('transcript.final', received)
  const replies = turnsFor('reply.text.final', received)
  const audio = turnsFor('reply.audio.chunk', received)
  const audioComplete = turnsFor('reply.audio.complete', received)
  const playbackEnded = turnsFor('audio.playback.ended', sentControls)
  const completedTurns = intersect(transcripts, replies, audio, audioComplete, playbackEnded)
  const cancelOrders = received.filter((item) => item.type === 'turn.cancelled').map((item) => item.order)
  const lastCancelOrder = cancelOrders.length ? Math.max(...cancelOrders) : null
  const postCancelCompleted = lastCancelOrder !== null && completedTurns.some((turnId) => {
    const ended = sentControls.find((item) => item.type === 'audio.playback.ended' && item.turn_id === turnId)
    return ended && ended.order > lastCancelOrder
  })
  return {
    transcripts: transcripts.size,
    replies: replies.size,
    audio_turns: audio.size,
    completedTurns,
    barge_in_count: eventCounts.get('barge_in.detected') || 0,
    cancelled_count: eventCounts.get('turn.cancelled') || 0,
    postCancelCompleted,
    error_count: eventCounts.get('error') || 0,
  }
}

export function healthReady(health) {
  const values = Object.values(health?.components || {})
  return health?.status === 'ready' && values.length > 0 && values.every((status) => status === 'ready')
}

export function perceptionPass(perception) {
  const scoreKeys = [
    'lip_sync_score',
    'mouth_naturalness_score',
    'speaking_clarity_score',
    'idle_naturalness_score',
  ]
  const scoresValid = scoreKeys.every((key) => Number.isInteger(perception?.[key])
    && perception[key] >= 1
    && perception[key] <= 5)
  return scoresValid
    && perception?.mouth_motion_observed === true
    && perception?.transition_continuity_observed === true
    && perception?.idle_naturalness_score >= 4
    && perception?.idle_continues_after_stop === true
}

export function redactError(value) {
  return String(value)
    .replace(/[A-Za-z]:\\Users\\[^\\\s]+/gi, '%USERPROFILE%')
    .replace(/\/home\/[^/\s]+/g, '$HOME')
}
