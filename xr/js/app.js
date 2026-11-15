// The bust page: scene, materials, lights, and (later stages) the rig, the gaze and the XR session.
//
// Frames. "Bust space" is the glTF frame of head.glb: metres, +X image-right (the subject's
// left), +Y up, the face looks along +Z. The bust group (head + plinth) carries that frame into
// the world; everything the rig and the gaze do is computed in bust space.
//
// URL parameters (all optional):
//   view=face|eyes|eye|eyeL     put the camera where tools/render_stills.py and rig_strips.py put
//                          theirs (cam_test_face, cam_test_eye) or at 0.7 m (bust)
//   size=800               render into a fixed square canvas of this many CSS pixels
//   shot=1                 hide the text overlays (for screenshots)
//   pose=1                 debug pose, time frozen; channels from gy gp gd (gaze yaw, pitch in
//                          deg, distance in m, default 1.6 as in tools/rig_strips.py), hy hp hr
//                          (head), blink (or blinkL / blinkR), brow (or browL / browR), widen,
//                          squint, pupil

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { Rig, bonesLocal } from './rig.js';

const Q = new URLSearchParams(location.search);
const num = (k, d) => (Q.has(k) ? parseFloat(Q.get(k)) : d);
const ASSETS = './assets/';
const status = (t) => { const s = document.getElementById('status'); if (s) s.textContent = t; };

// ---- renderer, scene, camera ---------------------------------------------------------------

const stage = document.getElementById('stage');
const fixed = Q.has('size') ? Math.round(num('size', 800)) : 0;
if (fixed) stage.classList.add('fixed');
if (Q.get('shot') === '1') document.body.classList.add('shot');

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true,
                                           preserveDrawingBuffer: Q.get('shot') === '1' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
const TONES = { aces: THREE.ACESFilmicToneMapping, agx: THREE.AgXToneMapping, neutral: THREE.NeutralToneMapping };
// ACES, not AgX: without subsurface scattering AgX left the skin pale and grey next to the
// Cycles still; ACES keeps its warmth and contrast closer.
renderer.toneMapping = TONES[Q.get('tone')] ?? THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = num('exposure', 0.75);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const DARK = new THREE.Color(0x0d0d0f);
scene.background = DARK;
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = num('env', 0.1);

const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 50);
scene.add(camera);

// The bust group: placed in the world by the laptop view or by the XR placement.
const bust = new THREE.Group();
bust.name = 'bust';
scene.add(bust);

// Key light from upper image-left and in front, as in the stills (Blender `key` area light at
// (-0.42, 0.73, 0.63) in bust space), aimed at the eyes. It lives in the bust group, so it
// keeps lighting the face the same way wherever the bust is placed.
const key = new THREE.DirectionalLight(0xfff4ea, num('key', 3.6));
key.position.set(-0.42, 0.73, 0.63);
key.castShadow = true;
key.shadow.mapSize.set(1024, 1024);
key.shadow.camera.left = -0.16; key.shadow.camera.right = 0.16;
key.shadow.camera.top = 0.16; key.shadow.camera.bottom = -0.16;
key.shadow.camera.near = 0.3; key.shadow.camera.far = 1.6;
key.shadow.bias = -0.0004;
key.shadow.normalBias = 0.0015;
key.shadow.radius = 3;
bust.add(key);
bust.add(key.target);
// Rim from behind image-right (Blender `rim` at (0.44, 0.51, -0.73)). Off by default: its
// specular drew a glossy streak down the shadow side of the nose, and in passthrough the room
// is the backdrop anyway. ?rimlight=1 turns it on.
const rim = new THREE.DirectionalLight(0xffffff, num('rimlight', 0));
rim.position.set(0.44, 0.51, -0.73);
bust.add(rim);
bust.add(rim.target);

function resize() {
  const w = fixed || window.innerWidth;
  const h = fixed || window.innerHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  setView();
}
window.addEventListener('resize', resize);

// ---- assets --------------------------------------------------------------------------------

function loadTexture(name, srgb) {
  return new Promise((ok, fail) => {
    new THREE.TextureLoader().load(ASSETS + name, (t) => {
      t.flipY = false;                       // glTF UVs: v already flipped by the exporter
      t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      t.anisotropy = renderer.capabilities.getMaxAnisotropy();
      ok(t);
    }, undefined, fail);
  });
}

async function loadAll() {
  const [gltf, rig, albedo, normal, rough, eyeL, eyeR] = await Promise.all([
    new GLTFLoader().loadAsync(ASSETS + 'head.glb'),
    fetch(ASSETS + 'rig.json').then((r) => r.json()),
    loadTexture('skin_albedo.jpg', true),
    loadTexture('skin_normal.png', false),
    loadTexture('skin_rough.jpg', false),
    loadTexture('eye_L.jpg', true),
    loadTexture('eye_R.jpg', true),
  ]);
  return { gltf, rig, tex: { albedo, normal, rough, eyeL, eyeR } };
}

// ---- materials -----------------------------------------------------------------------------

function makeMaterials(tex) {
  const skin = new THREE.MeshPhysicalMaterial({
    name: 'skin', map: tex.albedo, normalMap: tex.normal,
    normalScale: new THREE.Vector2(num('normal', 1.2), num('normal', 1.2)),
    roughnessMap: tex.rough, roughness: num('rough', 1.0), metalness: 0,
    specularIntensity: num('spec', 0.45), sheen: 0.08, sheenRoughness: 0.4,
    sheenColor: new THREE.Color(0.9, 0.75, 0.7),
  });
  const eye = (map, name) => new THREE.MeshStandardMaterial({ name, map, roughness: 0.55, metalness: 0 });
  // The cornea: a thin clear shell that adds only its reflections (black base colour, additive
  // blending), so the iris shows through untouched and the key light and the environment give
  // the catch light. No transmission, no refraction: both cost too much in a headset.
  const cornea = (name) => new THREE.MeshPhysicalMaterial({
    name, color: 0x000000, roughness: 0.03, metalness: 0, specularIntensity: 1.0,
    ior: 1.376, envMapIntensity: 2.5, transparent: true, blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  return {
    skin,
    'eye_interior.L': eye(tex.eyeL, 'eye_interior.L'),
    'eye_interior.R': eye(tex.eyeR, 'eye_interior.R'),
    'cornea.L': cornea('cornea.L'),
    'cornea.R': cornea('cornea.R'),
    teeth: new THREE.MeshStandardMaterial({ name: 'teeth', color: 0xd8d0c0, roughness: 0.4 }),
    tongue: new THREE.MeshStandardMaterial({ name: 'tongue', color: 0x9a4a48, roughness: 0.5 }),
  };
}

// ---- the bust ------------------------------------------------------------------------------

const H = { meshes: [], rig: null, root: null, eyeHeight: 0.304, eyeZ: 0.0976 };

function buildBust({ gltf, rig, tex }) {
  const mats = makeMaterials(tex);
  const root = gltf.scene;
  root.traverse((o) => {
    if (!o.isSkinnedMesh) return;
    const name = o.material.name;
    o.material = mats[name] || o.material;
    o.castShadow = name === 'skin';
    o.receiveShadow = true;
    o.frustumCulled = false;                // skinned bounds do not follow the bones
    if (name.startsWith('cornea')) o.renderOrder = 2;
    H.meshes.push(o);
  });
  bust.add(root);
  H.root = root;
  H.rig = rig;
  H.eyeHeight = rig.eye_mid[1];
  H.eyeZ = rig.eye_mid[2];

  // Plinth: a plain dark cylinder whose top sits just inside the neck cut, so the cut never
  // shows and the head reads as a bust standing on something.
  const box = new THREE.Box3();
  const neck = [];
  for (const m of H.meshes) {
    if (m.material.name !== 'skin') continue;
    const p = m.geometry.attributes.position;
    for (let i = 0; i < p.count; i++) box.expandByPoint(new THREE.Vector3().fromBufferAttribute(p, i));
  }
  for (const m of H.meshes) {
    if (m.material.name !== 'skin') continue;
    const p = m.geometry.attributes.position;
    for (let i = 0; i < p.count; i++) {
      if (p.getY(i) < box.min.y + 0.03) neck.push([p.getX(i), p.getY(i), p.getZ(i)]);
    }
  }
  let cx = 0, cz = 0, r = 0, topY = -Infinity;
  for (const [x, , z] of neck) { cx += x; cz += z; }
  cx /= neck.length; cz /= neck.length;
  for (const [x, y, z] of neck) { r = Math.max(r, Math.hypot(x - cx, z - cz)); topY = Math.max(topY, y); }
  const height = num('plinth', 0.22);
  const top = box.min.y + 0.012;
  const plinth = new THREE.Mesh(
    new THREE.CylinderGeometry(r * 1.02, r * 1.12, height, 64, 1, false),
    new THREE.MeshStandardMaterial({ color: 0x1b1b1f, roughness: 0.6, metalness: 0.0 }));
  plinth.position.set(cx, top - height / 2, cz);
  plinth.receiveShadow = true;
  plinth.name = 'plinth';
  bust.add(plinth);
  H.plinth = { radius: r, top, bottom: top - height, cx, cz, cutTop: topY };
  key.target.position.set(0, H.eyeHeight, H.eyeZ);
  rim.target.position.set(0, H.eyeHeight, 0);
  setupRig(rig);
}

// ---- the rig -------------------------------------------------------------------------------

// Bone rest rotations in bust space, read from the loaded skeleton once, before any posing;
// rig.js bonesLocal() turns the rig's bust-space deltas into local quaternions from them.
function setupRig(rigJson) {
  H.rigMaths = new Rig(rigJson);
  H.root.updateMatrixWorld(true);
  const rootInv = new THREE.Quaternion();
  H.root.getWorldQuaternion(rootInv).invert();
  const want = { neck: 'neck', head: 'head', 'eye.L': 'eye.L', 'eye.R': 'eye.R' };
  H.bones = {};
  H.root.traverse((o) => {
    if (!o.isBone) return;
    for (const [n, gltfName] of Object.entries(want)) {
      if (o.name === THREE.PropertyBinding.sanitizeNodeName(gltfName)) H.bones[n] = o;
    }
  });
  const q = new THREE.Quaternion();
  const asArr = (x) => [x.x, x.y, x.z, x.w];
  H.restWorld = {};
  for (const [n, b] of Object.entries(H.bones)) {
    H.restWorld[n] = asArr(rootInv.clone().multiply(b.getWorldQuaternion(q)));
  }
  H.restWorld.root = asArr(rootInv.clone().multiply(H.bones.neck.parent.getWorldQuaternion(q)));
  H.morph = H.meshes.map((m) => ({ m, d: m.morphTargetDictionary }));
  applyChannels({});
}

/** Pose the bust from channels (rig.js apply()); returns the rig state. */
function applyChannels(ch) {
  const st = H.rigMaths.apply(ch);
  const loc = bonesLocal(st.delta, H.restWorld);
  for (const [n, b] of Object.entries(H.bones)) b.quaternion.fromArray(loc[n]);
  for (const { m, d } of H.morph) {
    for (const [k, v] of Object.entries(st.weights)) {
      const i = d[k];
      if (i !== undefined) m.morphTargetInfluences[i] = v;
    }
  }
  H.state = st;
  return st;
}

function debugChannels() {
  const blink = num('blink', 0), brow = num('brow', 0);
  return {
    gaze_yaw: num('gy', 0), gaze_pitch: num('gp', 0), gaze_dist: num('gd', 1.6),
    head_yaw: num('hy', 0), head_pitch: num('hp', 0), head_roll: num('hr', 0),
    blink_L: num('blinkL', blink), blink_R: num('blinkR', blink),
    brow_L: num('browL', brow), brow_R: num('browR', brow),
    widen: num('widen', 0), squint: num('squint', 0), pupil: num('pupil', 0),
  };
}

// ---- views ---------------------------------------------------------------------------------

// Still cameras from scene.blend, converted to bust space: (x, y, z) -> (x, z, -y).
const VIEWS = {
  face: { pos: [-0.0001, 0.2662, 0.6676], dir: [0, 0, -1], lens: 126 },   // cam_test_face
  eyes: { pos: [-0.0001, 0.3042, 0.4976], dir: [0, 0, -1], lens: 105 },   // cam_eyes (rig_strips.py)
  eyeL: { pos: [0.0302, 0.3041, 0.2976], dir: [0, 0, -1], lens: 105 },    // the left eye, 20 cm, frontal
  eye: { pos: [-0.0305, 0.3197, 0.2466], dir: [0.405, -0.105, -0.909], lens: 100 }, // cam_test_eye
  video: { pos: [-0.0001, 0.2642, 0.6676], dir: [0, 0, -1], lens: 112 },  // cam_video
};

function setView() {
  const v = VIEWS[Q.get('view')];
  if (v) {
    // Blender sensor fit is horizontal, 36 mm wide.
    const hfov = 2 * Math.atan(18 / v.lens);
    camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(hfov / 2) / camera.aspect));
    camera.position.set(...v.pos);
    const d = new THREE.Vector3(...v.dir).normalize();
    camera.lookAt(camera.position.clone().add(d));
  } else {
    camera.fov = 40;
    camera.position.set(0, H.eyeHeight, H.eyeZ + num('dist', 0.7));
    camera.lookAt(0, H.eyeHeight - 0.02, H.eyeZ);
  }
  camera.updateProjectionMatrix();
}

// ---- loop ----------------------------------------------------------------------------------

const POSE = Q.get('pose') === '1';

function frame() {
  if (POSE) applyChannels(debugChannels());
  renderer.render(scene, camera);
}

async function main() {
  try {
    const assets = await loadAll();
    buildBust(assets);
  } catch (e) {
    status('could not load the head: ' + e.message);
    throw e;
  }
  resize();
  status('');
  renderer.setAnimationLoop(frame);
  window.__xr = { THREE, scene, camera, renderer, bust, H, applyChannels };
  document.body.dataset.ready = '1';
}

main();
