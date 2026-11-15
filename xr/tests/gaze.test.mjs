// node --test xr/tests   The five scripted wearers of docs/BRIEF_M14.md section D, seeds 0 to 7.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RIG, rig, run, PATHS } from './sim.mjs';
import { ENGINE, saccadeDuration, profile } from '../js/gaze.js';

const SEEDS = [0, 1, 2, 3, 4, 5, 6, 7];
const D2R = Math.PI / 180;
const rms = (a) => Math.sqrt(a.reduce((s, x) => s + x * x, 0) / a.length);
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const angleBetween = (a, b) => {
  const c = (a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / (Math.hypot(...a) * Math.hypot(...b));
  return Math.acos(Math.min(1, Math.max(-1, c))) / D2R;
};
function faceError(row) {
  // angle at the head's eye midpoint between where it looks and the nearest of the three points
  const mid = rig.headPose(row).map(rig.eyeMid);
  const v = row.viewer;
  const pts = [sub(v.pos, v.right.map((x) => x * 0.032)), v.pos.map((x, i) => x + v.right[i] * 0.032),
               [v.pos[0], v.pos[1] - 0.07, v.pos[2]]];
  const look = sub(row.target, mid);
  return Math.min(...pts.map((p) => angleBetween(look, sub(p, mid))));
}
const eyeInHead = (r) => Math.hypot(r.eye_yaw, r.eye_pitch);

test('engine numbers match wrapper/gaze/engine.py (via rig.json) and its saccade timing', () => {
  for (const [k, v] of Object.entries(ENGINE)) {
    assert.deepEqual(RIG.gaze_params[k], v, k);
  }
  // saccade_duration() from the Python engine
  const py = { 0.5: 0.021295, 2: 0.023946, 5: 0.029824, 10: 0.041176, 20: 0.068231, 30: 0.098707, 40: 0.130889 };
  for (const [a, d] of Object.entries(py)) assert.ok(Math.abs(saccadeDuration(+a) - d) < 2e-6, `amp ${a}`);
  const prof = { 0.1: 0.022076, 0.3: 0.247625, 0.5: 0.599558, 0.7: 0.882969, 0.9: 0.994435 };
  const k20 = 1 - 0.22 * Math.min(20 / 30, 1);
  for (const [u, f] of Object.entries(prof)) assert.ok(Math.abs(profile(+u, k20) - f) < 2e-6, `u ${u}`);
});

test('1. still at 0.7 m for 20 s', (t) => {
  for (const seed of SEEDS) {
    const { rows, log } = run('still', { seed });
    const yawRms = rms(rows.map((r) => r.head_yaw));
    const blinks = log.blinks.length, sacc = log.saccades.length, glances = log.glances.length;
    const eihMax = Math.max(...rows.map(eyeInHead));
    const msg = `seed ${seed}: head yaw rms ${yawRms.toFixed(2)}, blinks ${blinks}, saccades ${sacc}, glances ${glances}, eye-in-head max ${eihMax.toFixed(1)}`;
    t.diagnostic(msg);
    assert.ok(yawRms < 1.5, msg);
    assert.ok(blinks >= 4 && blinks <= 9, msg);
    assert.ok(sacc >= 10 && sacc <= 30, msg);
    assert.ok(glances >= 1 && glances <= 4, msg);
    assert.ok(eihMax <= 15, msg);
  }
});

test('2. a 0.5 m step to the side in 1 s', (t) => {
  const P = PATHS.step;
  const angle = Math.atan2(0.5, 0.7) / D2R;
  for (const seed of SEEDS) {
    const { rows } = run('step', { seed });
    const at = (t) => rows.findIndex((r) => r.time >= t - 1e-9);
    // on the wearer 0.3 s after the step ends (if a face jump is in flight, where it lands)
    let i = at(P.stepEnd + 0.3);
    while (rows[i].saccade) i++;
    const err = faceError(rows[i]);
    // the eyes start before the head
    const i0 = at(P.stepStart);
    const g0 = rows[i0].gaze_yaw, h0 = rows[i0].head_follow_yaw;
    const eyeStart = rows.slice(i0).find((r) => Math.abs(r.gaze_yaw - g0) > 1).time;
    const headStart = rows.slice(i0).find((r) => Math.abs(r.head_follow_yaw - h0) > 0.5).time;
    // the head's share of the angle 1.5 s after the step
    const share = (rows[at(P.stepEnd + 1.5)].head_follow_yaw - h0) / angle;
    const eihMax = Math.max(...rows.map((r) => Math.abs(r.eye_yaw)));
    const end = rows.filter((r) => r.time > P.duration - 0.5);
    const eihEnd = end.reduce((s, r) => s + Math.abs(r.eye_yaw), 0) / end.length;
    const msg = `seed ${seed}: error ${err.toFixed(2)} deg, eyes ${eyeStart.toFixed(3)} s head ${headStart.toFixed(3)} s, head share ${(share * 100).toFixed(0)} %, eye-in-head max ${eihMax.toFixed(1)} end ${eihEnd.toFixed(1)}`;
    t.diagnostic(msg);
    assert.ok(err < 2, msg);
    assert.ok(headStart > eyeStart, msg);
    assert.ok(share >= 0.65 && share <= 0.85, msg);
    assert.ok(eihMax <= 28, msg);
    assert.ok(eihEnd < 10, msg);
  }
});

test('3. a slow walk through 150 deg: follow, lose, recentre, greet', (t) => {
  for (const seed of SEEDS) {
    const { rows, log } = run('walk', { seed });
    const maxHead = Math.max(...rows.map((r) => r.head_follow_yaw));
    let speed = 0;
    for (let i = 1; i < rows.length; i++) {
      speed = Math.max(speed, Math.abs(rows[i].head_yaw - rows[i - 1].head_yaw) / (rows[i].time - rows[i - 1].time));
    }
    const lost = log.lost.length > 0;
    // back near the centre at some point while the wearer is out of sight (the look-around
    // after it may turn the head again, by the usual rules)
    const away = rows.filter((r) => r.time > log.lost[0].t + 2 && r.time < 12.5);
    const centred = Math.min(...away.map((r) => Math.abs(r.head_follow_yaw)));
    const greet = log.greets[0];
    const msg0 = `seed ${seed}: head max ${maxHead.toFixed(1)}, speed max ${speed.toFixed(0)} deg/s, lost ${lost}, head nearest centre while away ${centred.toFixed(1)}, greets ${log.greets.length}`;
    assert.ok(maxHead >= 55, msg0);
    assert.ok(speed < 80, msg0);
    assert.ok(lost, msg0);
    assert.ok(centred < 5, msg0);
    assert.ok(greet && greet.t > 12.5, msg0);
    const sac = log.saccades.find((s) => Math.abs(s.t - greet.t) < 0.01 && s.kind === 'greet');
    const blink = log.blinks.find((b) => Math.abs(b.t - greet.t) < 0.1);
    const flash = Math.max(...rows.filter((r) => r.time > greet.t && r.time < greet.t + 0.8).map((r) => Math.max(r.brow_L, r.brow_R)));
    const msg = `${msg0}, greet at ${greet.t.toFixed(2)}: saccade ${!!sac}, blink ${!!blink}, brow peak ${flash.toFixed(2)}`;
    t.diagnostic(msg);
    assert.ok(sac, msg);
    assert.ok(blink, msg);
    assert.ok(flash > 0.25, msg);
  }
});

test('4. coming to 0.25 m: the eyes converge as the geometry says (about 14 deg)', (t) => {
  for (const seed of SEEDS) {
    const { rows } = run('near', { seed, eyes: true });
    const settled = rows.filter((r) => r.time > 3 && r.mode === 'face' && !r.saccade
                                 && Math.max(r.blink_L, r.blink_R) < 0.05);
    assert.ok(settled.length > 100, `seed ${seed}: ${settled.length} settled frames`);
    let worst = 0, sum = 0;
    for (const r of settled) {
      const verg = r.eyeYawR - r.eyeYawL;                  // R sits at -X, so it turns to +X
      // geometry: both eyes aimed at the face point the gaze is on, from where the head holds them
      const mid = rig.headPose(r).map(rig.eyeMid);
      const dist = Math.hypot(...sub(r.target, mid));
      const want = 2 * Math.atan(RIG.gaze_params.eye_half_ipd / dist) / D2R;
      worst = Math.max(worst, Math.abs(verg - want));
      sum += verg;
    }
    const mean = sum / settled.length;
    const msg = `seed ${seed}: mean vergence ${mean.toFixed(2)} deg, worst off the geometry ${worst.toFixed(2)} deg`;
    t.diagnostic(msg);
    assert.ok(mean > 12.5 && mean < 15.5, msg);
    assert.ok(worst < 1.0, msg);
  }
});

test('5. deterministic, and 72 Hz agrees with 120 Hz', (t) => {
  for (const seed of SEEDS) {
    const a = run('step', { seed, hz: 90 }).rows, b = run('step', { seed, hz: 90 }).rows;
    assert.deepEqual(a.map((r) => [r.head_yaw, r.gaze_yaw, r.blink_L, r.brow_R, r.pupil]),
                     b.map((r) => [r.head_yaw, r.gaze_yaw, r.blink_L, r.brow_R, r.pupil]));
    for (const name of ['still', 'step', 'walk']) {
      const r72 = run(name, { seed, hz: 72 }).rows, r120 = run(name, { seed, hz: 120 }).rows;
      const dy = [], dp = [];
      for (let k = 1; k * 3 <= r72.length && k * 5 <= r120.length; k++) {   // every 1/24 s
        const x = r72[k * 3 - 1], y = r120[k * 5 - 1];
        dy.push(x.head_yaw - y.head_yaw); dp.push(x.head_pitch - y.head_pitch);
      }
      const msg = `seed ${seed} ${name}: head yaw rms diff ${rms(dy).toFixed(3)}, pitch ${rms(dp).toFixed(3)}`;
      t.diagnostic(msg);
      assert.ok(rms(dy) < 0.5 && rms(dp) < 0.5, msg);
    }
  }
});
