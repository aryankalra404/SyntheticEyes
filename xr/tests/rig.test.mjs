// node --test xr/tests   (no browser, no three.js)
// C2: the direction convention of the wrapper on the bone maths, and the local quaternions.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Rig, qRot, qMul, qInv, bonesLocal, rot3, pivot, QI, qAxis } from '../js/rig.js';

const RIG = JSON.parse(readFileSync(new URL('../assets/rig.json', import.meta.url)));
const rig = new Rig(RIG);
const base = { gaze_dist: 0.7 };

// Where the pupil of side s lands: the rest pupil centre carried by the eye's delta about the
// (head-carried) eye centre. This is what the skinned mesh does for a vertex weighted to the eye.
function pupil(st, s) {
  const restC = s === 'L' ? RIG.eye_rest_L : RIG.eye_rest_R;
  const p = s === 'L' ? RIG.pupil_rest_L : RIG.pupil_rest_R;
  const local = [p[0] - restC[0], p[1] - restC[1], p[2] - restC[2]];
  const r = qRot(st.delta[`eye.${s}`], local);
  return [st.eyeCentre[s][0] + r[0], st.eyeCentre[s][1] + r[1], st.eyeCentre[s][2] + r[2]];
}

test('rest, looking far: both pupils where the scene has them', () => {
  const st = rig.apply({ gaze_dist: 1e4 });      // at 0.7 m the eyes converge about 2.5 deg
  for (const s of ['L', 'R']) {
    const want = s === 'L' ? RIG.pupil_rest_L : RIG.pupil_rest_R;
    const got = pupil(st, s);
    for (let i = 0; i < 3; i++) assert.ok(Math.abs(got[i] - want[i]) < 2e-4, `${s} axis ${i}`);
  }
});

test('gaze yaw +20 moves both pupils to image-right (+X), -20 to image-left', () => {
  const r0 = rig.apply(base);
  for (const [gy, sign] of [[20, 1], [-20, -1]]) {
    const st = rig.apply({ ...base, gaze_yaw: gy });
    for (const s of ['L', 'R']) {
      const dx = pupil(st, s)[0] - pupil(r0, s)[0];
      assert.ok(sign * dx > 0.003, `gy ${gy} side ${s} dx ${dx}`);
      assert.ok(Math.sign(st.eyeYaw[s]) === sign);
    }
  }
});

test('gaze pitch +15 moves both pupils up (+Y), -15 down', () => {
  const r0 = rig.apply(base);
  for (const [gp, sign] of [[15, 1], [-15, -1]]) {
    const st = rig.apply({ ...base, gaze_pitch: gp });
    for (const s of ['L', 'R']) {
      const dy = pupil(st, s)[1] - pupil(r0, s)[1];
      assert.ok(sign * dy > 0.002, `gp ${gp} side ${s} dy ${dy}`);
    }
    // lid follow: up raises lid_up, down raises lid_down, as in rig.py
    if (sign > 0) assert.ok(st.weights['lid_up.L'] > 0.5 && st.weights['lid_down.L'] === 0);
    else assert.ok(st.weights['lid_down.L'] > 0.4 && st.weights['lid_up.L'] === 0);
  }
});

test('head yaw +20 turns the face to image-right, pitch +10 up, roll +10 tips the top right', () => {
  const nose = [RIG.eye_mid[0], RIG.eye_mid[1] - 0.04, RIG.eye_mid[2] + 0.1];
  const crown = [RIG.eye_mid[0], RIG.eye_mid[1] + 0.12, RIG.eye_mid[2] - 0.05];
  const r0 = rig.apply(base).headMap;
  const yawed = rig.apply({ ...base, head_yaw: 20 }).headMap;
  assert.ok(yawed(nose)[0] - r0(nose)[0] > 0.02);
  const pitched = rig.apply({ ...base, head_pitch: 10 }).headMap;
  assert.ok(pitched(nose)[1] - r0(nose)[1] > 0.01);
  const rolled = rig.apply({ ...base, head_roll: 10 }).headMap;
  assert.ok(rolled(crown)[0] - r0(crown)[0] > 0.01);
});

test('eyes hold a world target while the head turns (eyes in world space)', () => {
  const target = [0.1, RIG.eye_mid[1] + 0.05, 0.8];
  for (const hy of [-30, 0, 30]) {
    const st = rig.apply({ ...base, head_yaw: hy, target });
    for (const s of ['L', 'R']) {
      // the eye's forward (+Z at rest) carried by its delta points at the target
      const f = qRot(st.delta[`eye.${s}`], [0, 0, 1]);
      const c = st.eyeCentre[s];
      const t = [target[0] - c[0], target[1] - c[1], target[2] - c[2]];
      const n = Math.hypot(...t);
      const cos = (f[0] * t[0] + f[1] * t[1] + f[2] * t[2]) / n;
      assert.ok(cos > 0.99999, `hy ${hy} ${s} cos ${cos}`);
    }
  }
});

test('vergence: a near target turns the eyes toward each other', () => {
  const near = rig.apply({ target: [RIG.eye_mid[0], RIG.eye_mid[1], RIG.eye_mid[2] + 0.25] });
  assert.ok(near.eyeYaw.L < -5 && near.eyeYaw.R > 5);      // L sits at +X, so it turns to -X
});

test('bonesLocal reproduces delta * restWorld through the hierarchy, for any rest rotations', () => {
  const rnd = (seed) => { let x = seed; return () => ((x = (x * 16807) % 2147483647) / 2147483647); };
  const r = rnd(7);
  const rq = () => { const q = qAxis(...(() => { const v = [r() - .5, r() - .5, r() - .5]; const n = Math.hypot(...v); return v.map((a) => a / n); })(), r() * 6); return q; };
  for (let k = 0; k < 20; k++) {
    const rest = { root: rq(), neck: rq(), head: rq(), 'eye.L': rq(), 'eye.R': rq() };
    const st = rig.apply({ head_yaw: (r() - .5) * 80, head_pitch: (r() - .5) * 30, head_roll: (r() - .5) * 10,
                           gaze_yaw: (r() - .5) * 40, gaze_pitch: (r() - .5) * 30, gaze_dist: 0.5 });
    const loc = bonesLocal(st.delta, rest);
    const world = { root: rest.root };
    world.neck = qMul(world.root, loc.neck);
    world.head = qMul(world.neck, loc.head);
    world['eye.L'] = qMul(world.head, loc['eye.L']);
    world['eye.R'] = qMul(world.head, loc['eye.R']);
    for (const n of ['neck', 'head', 'eye.L', 'eye.R']) {
      const want = qMul(st.delta[n], rest[n]);
      const dot = Math.abs(want.reduce((a, v, i) => a + v * world[n][i], 0));
      assert.ok(dot > 1 - 1e-9, `${n} ${dot}`);
    }
  }
  // and at rest the locals are the rest locals
  const rest = { root: QI, neck: rot3(0.1, 0.2), head: rot3(0.3, 0), 'eye.L': QI, 'eye.R': QI };
  const loc = bonesLocal({ neck: QI, head: QI, 'eye.L': QI, 'eye.R': QI }, rest);
  const exp = qMul(qInv(rest.neck), rest.head);
  assert.ok(Math.abs(loc.head.reduce((a, v, i) => a + v * exp[i], 0)) > 1 - 1e-12);
  void pivot;
});

test('shape keys as rig.py: tent blink, brow dip, squint fades with the blink', () => {
  const w = (ch) => rig.apply({ ...base, ...ch }).weights;
  assert.equal(w({}).pupil, RIG.rest_pupil);
  assert.equal(w({})['lid_open.L'], RIG.rest_lid_open);
  const b33 = w({ blink_L: 1 / 3 });
  assert.ok(Math.abs(b33['blink_33.L'] - 1) < 1e-9 && b33['blink_66.L'] === 0 && b33['blink.L'] === 0);
  const b1 = w({ blink_L: 1, brow_L: 0.3, squint: 0.4 });
  assert.ok(b1['blink.L'] === 1 && b1['blink_66.L'] === 0 && b1['lid_open.L'] === 0);
  assert.ok(Math.abs(b1['brow_up.L'] - (0.3 - RIG.constants.BLINK_BROW_DIP)) < 1e-12);
  assert.equal(b1['squint.L'], 0);
  assert.equal(b1['squint.R'], 0.4);
});
