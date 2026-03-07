import { strict as assert } from 'node:assert';
import test from 'node:test';

import {
  formatDuration,
  formatFrequencyMhz,
  mergeRecentCallEvent,
  sortRecentCalls,
  toTrafficCallPayload,
  upsertRecentCall,
} from './recentCalls.ts';

test('traffic.call.started adds a row', () => {
  const payload = toTrafficCallPayload({
    system: 'PRWC-J',
    site: '1',
    call_id: '1_1795_1772778389',
    trunkgroup_id: 1795,
    trunkgroup_label: 'K1 PHX Alarm',
    frequency: 769868750,
  });
  assert.ok(payload);

  const updated = upsertRecentCall(new Map(), {
    eventType: 'traffic.call.started',
    payload,
    timestamp: '2026-03-06T05:44:31Z',
    limit: 25,
  });

  assert.equal(updated.size, 1);
  const call = updated.get('1_1795_1772778389');
  assert.ok(call);
  assert.equal(call.system, 'PRWC-J');
  assert.equal(call.trunkgroup_id, 1795);
  assert.equal(call.trunkgroup_label, 'K1 PHX Alarm');
  assert.equal(call.frequency_hz, 769868750);
  assert.equal(call.started_at, '2026-03-06T05:44:31Z');
  assert.equal(call.latest_event_at, '2026-03-06T05:44:31Z');
  assert.equal(call.status, 'live');
});

test('traffic.call.ended updates same row rather than duplicating', () => {
  const startedPayload = toTrafficCallPayload({
    system: 'PRWC-J',
    site: '1',
    call_id: '1_1795_1772778389',
    trunkgroup_id: 1795,
    trunkgroup_label: 'K1 PHX Alarm',
    frequency: 769868750,
  });
  const endedPayload = toTrafficCallPayload({
    system: 'PRWC-J',
    site: '1',
    call_id: '1_1795_1772778389',
    duration_seconds: 20,
  });
  assert.ok(startedPayload);
  assert.ok(endedPayload);

  const withStarted = upsertRecentCall(new Map(), {
    eventType: 'traffic.call.started',
    payload: startedPayload,
    timestamp: '2026-03-06T05:44:31Z',
    limit: 25,
  });
  const withEnded = upsertRecentCall(withStarted, {
    eventType: 'traffic.call.ended',
    payload: endedPayload,
    timestamp: '2026-03-06T05:44:51Z',
    limit: 25,
  });

  assert.equal(withEnded.size, 1);
  const call = withEnded.get('1_1795_1772778389');
  assert.ok(call);
  assert.equal(call.started_at, '2026-03-06T05:44:31Z');
  assert.equal(call.latest_event_at, '2026-03-06T05:44:51Z');
  assert.equal(call.duration_seconds, 20);
  assert.equal(call.status, 'ended');
});

test('rolling list truncates to selected size', () => {
  let calls = new Map();
  for (let index = 0; index < 4; index += 1) {
    const payload = toTrafficCallPayload({
      system: `SYS-${index}`,
      site: '1',
      call_id: `call-${index}`,
    });
    assert.ok(payload);
    calls = upsertRecentCall(calls, {
      eventType: 'traffic.call.started',
      payload,
      timestamp: `2026-03-06T05:44:3${index}Z`,
      limit: 3,
    });
  }

  const sorted = sortRecentCalls(calls.values());
  assert.equal(sorted.length, 3);
  assert.equal(sorted[0].call_id, 'call-3');
  assert.equal(sorted[2].call_id, 'call-1');
});

test('frequency renders in MHz and duration renders live or seconds', () => {
  assert.equal(formatFrequencyMhz(769868750), '769.86875 MHz');
  assert.equal(formatDuration(null, 'live'), 'Live');
  assert.equal(formatDuration(20, 'ended'), '20s');
});

test('ended calls remain visible until trimmed out', () => {
  const payload = toTrafficCallPayload({
    system: 'PRWC-J',
    site: '1',
    call_id: 'call-1',
  });
  assert.ok(payload);
  const ended = mergeRecentCallEvent(undefined, {
    eventType: 'traffic.call.ended',
    payload: {
      ...payload,
      duration_seconds: 10,
    },
    timestamp: '2026-03-06T05:44:41Z',
  });
  assert.equal(ended.status, 'ended');
  assert.equal(ended.duration_seconds, 10);

  const kept = upsertRecentCall(new Map(), {
    eventType: 'traffic.call.ended',
    payload: {
      ...payload,
      duration_seconds: 10,
    },
    timestamp: '2026-03-06T05:44:41Z',
    limit: 1,
  });
  assert.equal(kept.size, 1);
  assert.ok(kept.has('call-1'));
});

test('live calls always sort above ended calls', () => {
  const sorted = sortRecentCalls([
    {
      call_id: 'ended-newest',
      system: 'PRWC-J',
      trunkgroup_id: 2001,
      trunkgroup_label: 'Ended New',
      frequency_hz: 769118750,
      duration_seconds: 12,
      started_at: '2026-03-06T05:45:00Z',
      latest_event_at: '2026-03-06T05:45:12Z',
      status: 'ended',
    },
    {
      call_id: 'live-older',
      system: 'PRWC-J',
      trunkgroup_id: 2002,
      trunkgroup_label: 'Live Old',
      frequency_hz: 769118760,
      duration_seconds: null,
      started_at: '2026-03-06T05:44:00Z',
      latest_event_at: '2026-03-06T05:44:00Z',
      status: 'live',
    },
    {
      call_id: 'live-newer',
      system: 'PRWC-J',
      trunkgroup_id: 2003,
      trunkgroup_label: 'Live New',
      frequency_hz: 769118770,
      duration_seconds: null,
      started_at: '2026-03-06T05:44:30Z',
      latest_event_at: '2026-03-06T05:44:30Z',
      status: 'live',
    },
  ]);

  assert.equal(sorted[0].call_id, 'live-newer');
  assert.equal(sorted[1].call_id, 'live-older');
  assert.equal(sorted[2].call_id, 'ended-newest');
});
