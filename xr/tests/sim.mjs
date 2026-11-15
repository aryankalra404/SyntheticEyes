// Scripted wearers for the gaze tests and the curve dumps. Bust space, metres, degrees.
import { readFileSync } from 'node:fs';
import { Rig } from '../js/rig.js';
import { createGaze, step } from '../js/gaze.js';

export const RIG = JSON.parse(readFileSync(new URL('../assets/rig.json', import.meta.url)));
export const rig = new Rig(RIG);
const M = RIG.eye_mid;
const D2R = Math.PI / 180;
const mj = (u) => { u = Math.min(Math.max(u, 0), 1); return u * u * u * (10 - 15 * u + 6 * u * u); };

/** A wearer at yaw `deg` on a circle of radius r around the eyes, at eye height, facing the bust. */
export function onCircle(deg, r = 0.7, dy = 0) {
  const a = deg * D2R;
  const pos = [M[0] + r * Math.sin(a), M[1] + dy, M[2] + r * Math.cos(a)];
  // facing the bust: forward = -(sin a, 0, cos a); right = forward x up
  return { pos, right: [Math.cos(a), 0, -Math.sin(a)], up: [0, 1, 0] };
}

export const PATHS = {
  // 1. still at 0.7 m for 20 s
  still: { duration: 20, at: () => onCircle(0) },
  // 2. 0.5 m step to the (bust's image-) right in 1 s, at 3 s; then still
  step: {
    duration: 7, stepStart: 3, stepEnd: 4,
    at: (t) => {
      const x = 0.5 * mj((t - 3) / 1);
      return { pos: [M[0] + x, M[1], M[2] + 0.7], right: [1, 0, 0], up: [0, 1, 0] };
    },
  },
  // 3. a slow walk round through 150 deg at 20 deg/s, a wait out of sight, a walk back to 30
  walk: {
    duration: 18,
    at: (t) => {
      let deg;
      if (t < 1) deg = 0;
      else if (t < 8.5) deg = 20 * (t - 1);                  // 0 -> 150 by 8.5 s
      else if (t < 12.5) deg = 150;                          // out of sight 4 s
      else if (t < 15.5) deg = 150 - 40 * (t - 12.5);        // back to 30 at 40 deg/s
      else deg = 30;
      return onCircle(deg);
    },
  },
  // 4. coming to 0.25 m (from 0.7 in 1 s), then still
  near: {
    duration: 8,
    at: (t) => onCircle(0, 0.7 - 0.45 * mj((t - 1) / 1)),
  },
};

/** Run a path; returns one row per frame (channels + time + the eyes' yaw from the rig). */
export function run(name, { seed = 0, hz = 90, eyes = false } = {}) {
  const path = PATHS[name];
  const g = createGaze({ seed, rig, log: true });
  const rows = [];
  const n = Math.round(path.duration * hz);
  for (let i = 1; i <= n; i++) {
    const t = i / hz;
    const v = path.at(t);
    const ch = step(g, v, 1 / hz);
    const row = { ...ch, time: t, viewer: v };
    if (eyes) {
      const st = rig.apply(ch);
      row.eyeYawL = st.eyeYaw.L; row.eyeYawR = st.eyeYaw.R;
    }
    rows.push(row);
  }
  return { rows, log: g.log, g };
}
