// node --test xr/tests   (no browser, no three.js)
// Which raised hand the bust looks at.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHandFollow, stepHandFollow } from '../js/handfollow.js';

const head = { x: 0, y: 1.6, z: 0 };
const raised = (x) => ({ x, y: 1.45, z: -0.4 });      // in front, a little below the eyes
const atSide = { x: 0.25, y: 0.85, z: 0.05 };          // hanging by the hip
const dt = 1 / 72;

test('hands at rest: look at the wearer', () => {
  const st = createHandFollow();
  assert.equal(stepHandFollow(st, { left: atSide, right: atSide }, head, dt), null);
  assert.equal(stepHandFollow(st, {}, head, dt), null);
});

test('a raised hand is followed, and lowering it goes back to the wearer', () => {
  const st = createHandFollow();
  const p = stepHandFollow(st, { right: raised(0.2), left: atSide }, head, dt);
  assert.deepEqual(p, raised(0.2));
  assert.equal(stepHandFollow(st, { right: atSide, left: atSide }, head, dt), null);
});

test('hysteresis: a hand just under the raise line keeps counting once followed', () => {
  const st = createHandFollow();
  const edge = { x: 0.2, y: head.y - 0.40, z: -0.4 };   // between RAISE_UP and RAISE_DOWN
  assert.equal(stepHandFollow(st, { right: edge }, head, dt), null);    // not raised enough to start
  stepHandFollow(st, { right: raised(0.2) }, head, dt);
  assert.deepEqual(stepHandFollow(st, { right: edge }, head, dt), edge); // but enough to stay
});

test('the followed hand stays followed when the other one goes higher', () => {
  const st = createHandFollow();
  stepHandFollow(st, { right: raised(0.2) }, head, dt);
  const high = { x: -0.2, y: 1.7, z: -0.4 };
  assert.deepEqual(stepHandFollow(st, { right: raised(0.2), left: high }, head, dt), raised(0.2));
});

test('of two hands raised together, the higher one wins', () => {
  const st = createHandFollow();
  const high = { x: -0.2, y: 1.7, z: -0.4 };
  assert.deepEqual(stepHandFollow(st, { right: raised(0.2), left: high }, head, dt), high);
});

test('a hand held against the face does not count', () => {
  const st = createHandFollow();
  assert.equal(stepHandFollow(st, { right: { x: 0.05, y: 1.55, z: -0.05 } }, head, dt), null);
});

test('a short tracking dropout holds the last point, a long one lets go', () => {
  const st = createHandFollow();
  stepHandFollow(st, { right: raised(0.2) }, head, dt);
  let p;
  for (let i = 0; i < 10; i++) p = stepHandFollow(st, {}, head, dt);      // 0.14 s
  assert.deepEqual(p, raised(0.2));
  for (let i = 0; i < 30; i++) p = stepHandFollow(st, {}, head, dt);      // past 0.3 s
  assert.equal(p, null);
});
