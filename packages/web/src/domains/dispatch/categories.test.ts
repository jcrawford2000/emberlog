import { strict as assert } from 'node:assert';
import test from 'node:test';

import { categoryOfIncidentType } from './categories.ts';

test('categorizes exact incident type mappings', () => {
  assert.equal(categoryOfIncidentType('Structure Fire'), 'Fire');
  assert.equal(categoryOfIncidentType('Breathing Problem'), 'EMS');
  assert.equal(categoryOfIncidentType('Traffic Collision'), 'MVC');
  assert.equal(categoryOfIncidentType('Fire Alarm'), 'Alarm');
  assert.equal(categoryOfIncidentType('Public Assist'), 'Service');
});

test('normalizes case and punctuation before exact matching', () => {
  assert.equal(categoryOfIncidentType('  structure-fire  '), 'Fire');
  assert.equal(categoryOfIncidentType('M.V.C.'), 'MVC');
  assert.equal(categoryOfIncidentType('public & assist'), 'Service');
});

test('categorizes common Phoenix-style freeform incident text', () => {
  assert.equal(categoryOfIncidentType('Difficulty breathing'), 'EMS');
  assert.equal(categoryOfIncidentType('Overdose'), 'EMS');
  assert.equal(categoryOfIncidentType('Vehicle rollover'), 'MVC');
  assert.equal(categoryOfIncidentType('Pedestrian struck'), 'MVC');
  assert.equal(categoryOfIncidentType('Smoke investigation'), 'Fire');
  assert.equal(categoryOfIncidentType('Waterflow alarm'), 'Alarm');
  assert.equal(categoryOfIncidentType('Check welfare'), 'Service');
});

test('categorizes 9xx-style dispatch codes as EMS', () => {
  assert.equal(categoryOfIncidentType('962'), 'EMS');
  assert.equal(categoryOfIncidentType('962A'), 'EMS');
});

test('falls back to Other for unknown incident types', () => {
  assert.equal(categoryOfIncidentType('Unknown Dispatch Phrase'), 'Other');
  assert.equal(categoryOfIncidentType(''), 'Other');
});
