// node xr/tests/dump.mjs <out_dir> [seed]   channels of paths 1 to 3 to JSON, for plot_curves.py,
// plus the per-seed numbers the tests check, printed.
import { writeFileSync, mkdirSync } from 'node:fs';
import { run } from './sim.mjs';

const out = process.argv[2] || 'outputs/tmp/m14/xr';
const seed = +(process.argv[3] || 0);
mkdirSync(out, { recursive: true });
const keep = ['time', 'mode', 'head_yaw', 'head_pitch', 'head_roll', 'head_follow_yaw', 'gaze_yaw',
              'gaze_pitch', 'gaze_dist', 'eye_yaw', 'eye_pitch', 'desired_yaw', 'desired_pitch', 'blink_L',
              'blink_R', 'brow_L', 'brow_R', 'widen', 'squint', 'pupil', 'saccade'];
for (const name of ['still', 'step', 'walk']) {
  const { rows, log } = run(name, { seed, hz: 90 });
  const ch = Object.fromEntries(keep.map((k) => [k, rows.map((r) => (typeof r[k] === 'number' ? +r[k].toFixed(4) : r[k]))]));
  writeFileSync(`${out}/curves_${name}.json`, JSON.stringify({ path: name, seed, hz: 90, channels: ch, log }));
  console.log(`${name}: ${rows.length} frames, ${log.saccades.length} saccades, ${log.blinks.length} blinks, ${log.glances.length} glances, ${log.greets.length} greets`);
}
