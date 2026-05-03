import { strict as assert } from 'node:assert';
import test from 'node:test';

import type { EventEnvelope } from '../../../core/realtime/types';
import { reduceLiveCallSystems } from './liveCallSystems.ts';

function buildEvent(options: {
  eventType: 'traffic.call.started' | 'traffic.call.ended';
  callId: string;
  system: string;
}): EventEnvelope {
  return {
    event_id: `event-${options.eventType}-${options.callId}`,
    event_type: options.eventType,
    schema_version: '1.0.0',
    timestamp: '2026-05-02T12:00:00Z',
    source: {
      module: 'emberlog-api',
      instance: 'trunk-recorder',
      system: options.system,
    },
    payload: {
      system: options.system,
      site: 'J',
      call_id: options.callId,
    },
  };
}

test('started and ended events keep live call system membership in sync', () => {
  let liveCalls = new Map<string, string>();

  liveCalls = reduceLiveCallSystems(
    liveCalls,
    buildEvent({ eventType: 'traffic.call.started', callId: 'call-1', system: 'PRWC-G' })
  );
  liveCalls = reduceLiveCallSystems(
    liveCalls,
    buildEvent({ eventType: 'traffic.call.started', callId: 'call-2', system: 'PRWC-G' })
  );
  liveCalls = reduceLiveCallSystems(
    liveCalls,
    buildEvent({ eventType: 'traffic.call.started', callId: 'call-3', system: 'MCSO-WT' })
  );

  assert.equal(liveCalls.size, 3);
  assert.equal(liveCalls.get('call-1'), 'PRWC-G');
  assert.equal(liveCalls.get('call-3'), 'MCSO-WT');

  liveCalls = reduceLiveCallSystems(
    liveCalls,
    buildEvent({ eventType: 'traffic.call.ended', callId: 'call-2', system: 'PRWC-G' })
  );

  assert.equal(liveCalls.size, 2);
  assert.equal(liveCalls.has('call-2'), false);
  assert.equal(liveCalls.get('call-1'), 'PRWC-G');
});

test('invalid payloads do not mutate live call system membership', () => {
  const initial = new Map<string, string>([['call-1', 'PRWC-G']]);
  const next = reduceLiveCallSystems(initial, {
    event_id: 'bad-event',
    event_type: 'traffic.call.started',
    schema_version: '1.0.0',
    timestamp: '2026-05-02T12:00:00Z',
    source: {
      module: 'emberlog-api',
      instance: 'trunk-recorder',
    },
    payload: {
      system: 'PRWC-G',
      call_id: 1234,
    },
  });

  assert.equal(next, initial);
  assert.deepEqual([...next.entries()], [['call-1', 'PRWC-G']]);
});
