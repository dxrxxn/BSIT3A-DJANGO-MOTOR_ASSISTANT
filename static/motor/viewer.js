'use strict';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const CFG = {
  modelUrl: (window.MOTOR_VIEWER && window.MOTOR_VIEWER.modelUrl) || '',
  fitSize: 4,                                   // normalized model size (world units)
  fov: 40,
  defaultDir: new THREE.Vector3(1, 0.55, 1).normalize(),
};

/* DOM */
const viewport        = document.getElementById('mv-viewport');
const canvas          = document.getElementById('mv-canvas');
const statusEl        = document.getElementById('mv-status');
const loadingEl       = document.getElementById('mv-loading');
const loadingTxt      = document.getElementById('mv-loading-text');
const progressBar     = document.getElementById('mv-progress-bar');
const alertEl         = document.getElementById('mv-alert');
const alertMsg        = document.getElementById('mv-alert-msg');
const placeholderLabel= document.getElementById('mv-placeholder-label');
const partHud         = document.getElementById('mv-part-hud');
const hudBadge        = document.getElementById('mv-hud-badge');
const hudTitle        = document.getElementById('mv-hud-title');
const hudDesc         = document.getElementById('mv-hud-desc');
const hudClose        = document.getElementById('mv-hud-close');
const hudOutside      = document.getElementById('mv-hud-outside');
const hudDiagnose     = document.getElementById('mv-hud-diagnose');
const btnTour         = document.getElementById('mv-btn-tour');

/* THREE state */
let renderer, scene, camera, controls;
let currentModel = null;
let modelInfo = null;   // {center, radius, size, meshes, faces, verts}
let resizeObserver = null, rafId = null, disposed = false;
let currentActivePart = 'overview';
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let pointerDownStart = { x: 0, y: 0, time: 0 };

/* ── UI helpers ─────────────────────────────────────────────────────────── */
function setStatus(text, state) {
  statusEl.innerHTML = '<span class="mv-status-dot"></span>' + text;
  statusEl.classList.toggle('is-ok',  state === 'ok');
  statusEl.classList.toggle('is-err', state === 'err');
}
function showLoading(text) { loadingTxt.textContent = text || 'Loading model…'; loadingEl.style.display = 'flex'; }
function setProgress(frac) { progressBar.style.width = Math.round(frac * 100) + '%'; }
function hideLoading() { loadingEl.style.display = 'none'; }
function showAlert(msg) { alertMsg.textContent = msg; alertEl.classList.remove('d-none'); }
document.getElementById('mv-alert-close').addEventListener('click', () => alertEl.classList.add('d-none'));

/* ── Scene ──────────────────────────────────────────────────────────────── */
function initThree() {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0d14);
  scene.fog = new THREE.Fog(0x0b0d14, 18, 42);

  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(9, 64),
    new THREE.ShadowMaterial({ opacity: 0.35 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
  const grid = new THREE.GridHelper(18, 36, 0x232839, 0x161a26);
  grid.material.transparent = true;
  grid.material.opacity = 0.55;
  scene.add(grid);

  scene.add(new THREE.HemisphereLight(0xbfd0ff, 0x30281e, 0.55));
  const key = new THREE.DirectionalLight(0xfff4e0, 2.6);
  key.position.set(5, 8, 4);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.bias = -0.0004;
  key.shadow.camera.left = key.shadow.camera.bottom = -6;
  key.shadow.camera.right = key.shadow.camera.top = 6;
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x8899cc, 0.7);
  fill.position.set(-6, 3, -4);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffd090, 0.5);
  rim.position.set(0, 4, -7);
  scene.add(rim);

  camera = new THREE.PerspectiveCamera(CFG.fov, 1, 0.05, 200);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.screenSpacePanning = false;

  resizeObserver = new ResizeObserver(fitCanvas);
  resizeObserver.observe(viewport);
  fitCanvas();
  loop();
}

function fitCanvas() {
  const w = viewport.clientWidth || 800, h = viewport.clientHeight || 520;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function loop() {
  if (disposed) return;
  rafId = requestAnimationFrame(loop);
  controls.update();
  renderer.render(scene, camera);
}

/* ── Model handling ─────────────────────────────────────────────────────── */
function clearModel() {
  if (!currentModel) return;
  currentModel.traverse(o => {
    if (o.isMesh) {
      o.geometry.dispose();
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      mats.forEach(m => { for (const k in m) if (m[k] && m[k].isTexture) m[k].dispose(); m.dispose(); });
    }
  });
  scene.remove(currentModel);
  currentModel = null;
  modelInfo = null;
}

function inspectModel(root) {
  let meshes = 0, faces = 0, verts = 0;
  root.traverse(o => {
    if (o.isMesh) {
      meshes++;
      const g = o.geometry;
      faces += g.index ? g.index.count / 3 : g.attributes.position.count / 3;
      verts += g.attributes.position.count;
    }
  });
  return { meshes, faces: Math.round(faces), verts };
}

function groundAndNormalize(root) {
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const scale = CFG.fitSize / Math.max(size.x, size.y, size.z);
  root.scale.setScalar(scale);
  root.updateMatrixWorld(true);

  const box2 = new THREE.Box3().setFromObject(root);
  const size2 = box2.getSize(new THREE.Vector3());
  const center2 = box2.getCenter(new THREE.Vector3());
  root.position.sub(center2);
  root.position.y += size2.y / 2;      // feet on the ground plane

  const radius = Math.max(size2.x, size2.y, size2.z) / 2;
  return { center: new THREE.Vector3(0, size2.y / 2, 0), radius, size: size2 };
}

function attachModel(root) {
  clearModel();
  root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  const info = groundAndNormalize(root);
  modelInfo = Object.assign(info, inspectModel(root));
  currentModel = root;
  scene.add(root);
  fitCamera();
  setStatus('Model loaded · ' + modelInfo.meshes + ' meshes · ' + modelInfo.faces.toLocaleString() + ' faces', 'ok');
}

function loadModel(url) {
  showLoading('Loading model…');
  setProgress(0);
  alertEl.classList.add('d-none');
  placeholderLabel.classList.add('d-none');
  const loader = new GLTFLoader();
  return new Promise(resolve => {
    loader.load(
      url,
      gltf => { hideLoading(); attachModel(gltf.scene); resolve(true); },
      xhr => {
        if (xhr.total) setProgress(xhr.loaded / xhr.total);
        else showLoading('Loading model… ' + (xhr.loaded / 1024).toFixed(0) + ' KB');
      },
      err => {
        hideLoading();
        console.error('MV: model load failed:', err);
        showAlert(' Could not load "' + url + '". Check that the file exists and is a valid .glb — showing a temporary test object instead.');
        attachModel(buildPlaceholder());
        placeholderLabel.classList.remove('d-none');
        setStatus('Model missing — temporary test object', 'err');
        resolve(false);
      }
    );
  });
}

/* Clearly-labelled temporary stand-in, used only when the GLB is missing. */
function buildPlaceholder() {
  const grp = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color: 0x3a4154, roughness: 0.6, metalness: 0.35, wireframe: true });
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.55, 0.5), mat);
  body.position.y = 0.85;
  const column = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.8, 0.45), mat);
  column.position.set(0.75, 1.45, 0);
  column.rotation.z = -0.35;
  const wheelGeo = new THREE.CylinderGeometry(0.42, 0.42, 0.22, 24);
  const mkWheel = x => {
    const w = new THREE.Mesh(wheelGeo, mat);
    w.rotation.z = Math.PI / 2;
    w.position.set(x, 0.42, 0);
    return w;
  };
  grp.add(body, column, mkWheel(0.95), mkWheel(-0.95));
  return grp;
}

/* ── Camera ─────────────────────────────────────────────────────────────── */
function fitCamera(dir) {
  if (!modelInfo) return;
  const d = dir || CFG.defaultDir;
  const dist = framingDistance();
  controls.target.copy(modelInfo.center);
  camera.position.copy(modelInfo.center).addScaledVector(d, dist);
  camera.near = Math.max(modelInfo.radius / 100, 0.01);
  camera.far = modelInfo.radius * 60;
  camera.updateProjectionMatrix();
  controls.minDistance = modelInfo.radius * 0.45;
  controls.maxDistance = modelInfo.radius * 7;
  controls.maxPolarAngle = Math.PI * 0.52;
  controls.update();
}

function framingDistance() {
  return modelInfo.radius / Math.tan(THREE.MathUtils.degToRad(CFG.fov / 2)) * 1.35;
}

/* ── Camera presets + cinematic intro (anime.js) ────────────────────────── */
const PRESETS = {
  front: new THREE.Vector3(0, 0.22, 1),
  rear:  new THREE.Vector3(0, 0.22, -1),
  left:  new THREE.Vector3(-1, 0.22, 0),
  right: new THREE.Vector3(1, 0.22, 0),
  top:   new THREE.Vector3(0, 1, 0.18),
  iso:   CFG.defaultDir.clone(),
};
// In Anime.js v3, suspendWhenDocumentHidden defaults to true, which freezes tweens
// if automated test runners or headless browsers report the tab as hidden.
if (typeof anime !== 'undefined' && 'suspendWhenDocumentHidden' in anime) {
  anime.suspendWhenDocumentHidden = false;
}

let camTween = null;

function cancelCameraTween() {
  if (camTween) { camTween.pause(); camTween = null; }
}

function snapCamera(toPos, toTarget) {
  cancelCameraTween();
  camera.position.copy(toPos);
  controls.target.copy(toTarget);
  controls.update();
}

/* Tween the camera+target through a plain params object so the single rAF
   render loop stays in charge — anime writes state, OrbitControls renders. */
function tweenCamera(toPos, toTarget, duration, easing) {
  if (typeof anime === 'undefined') { snapCamera(toPos, toTarget); return; }
  cancelCameraTween();
  const state = {
    px: camera.position.x, py: camera.position.y, pz: camera.position.z,
    tx: controls.target.x, ty: controls.target.y, tz: controls.target.z,
  };
  camTween = anime({
    targets: state,
    px: toPos.x, py: toPos.y, pz: toPos.z,
    tx: toTarget.x, ty: toTarget.y, tz: toTarget.z,
    duration: duration || 900,
    easing: easing || 'easeInOutCubic',
    update: () => {
      camera.position.set(state.px, state.py, state.pz);
      controls.target.set(state.tx, state.ty, state.tz);
    },
    complete: () => { camTween = null; },
  });
}

function markActivePreset(name) {
  document.querySelectorAll('.mv-preset[data-preset]').forEach(btn =>
    btn.classList.toggle('active', btn.dataset.preset === name));
}

function applyPreset(name) {
  if (!modelInfo || !PRESETS[name]) return;
  const d = PRESETS[name].clone().normalize();
  tweenCamera(
    modelInfo.center.clone().addScaledVector(d, framingDistance()),
    modelInfo.center.clone(),
    900
  );
  markActivePreset(name);
}

/* ── Part Definitions & Outside-to-Inside Camera Choreography ───────────── */
const PART_DEFS = {
  overview: {
    key: 'overview',
    title: 'Motorcycle Overview (Exterior)',
    badge: 'EXTERIOR VIEW',
    desc: 'Complete vehicle exterior. Drag to orbit, scroll to zoom, or select a component below to dive inside.',
    relPos: new THREE.Vector3(1, 0.55, 1).normalize(),
    distFactor: 1.35,
    fov: 40,
    offset: new THREE.Vector3(0, 0, 0),
    matchKeywords: [],
  },
  engine: {
    key: 'engine',
    title: 'Engine & Cylinder Block',
    badge: 'INTERNAL CORE',
    desc: 'Core power unit. Primary inspection points: cylinder head gasket, spark plug condition, and crankcase oil seals.',
    relPos: new THREE.Vector3(0.55, 0.2, 0.75).normalize(),
    distFactor: 0.44,
    fov: 32,
    offset: new THREE.Vector3(0, -0.05, 0.05),
    matchKeywords: ['engine', 'cylinder', 'piston', 'motor', 'crankcase', 'clutch'],
  },
  sprocket: {
    key: 'sprocket',
    title: 'Front Sprocket & Drive Assembly',
    badge: 'DRIVETRAIN',
    desc: 'Transfers engine output to drive chain. Check front sprocket tooth wear, oil seal leakage, and chain tension.',
    relPos: new THREE.Vector3(-0.75, -0.05, -0.45).normalize(),
    distFactor: 0.36,
    fov: 30,
    offset: new THREE.Vector3(-0.25, -0.22, -0.3),
    matchKeywords: ['sprocket', 'chain', 'gear', 'transmission', 'drive'],
  },
  battery: {
    key: 'battery',
    title: 'Battery & Electrical Hub',
    badge: 'ELECTRICAL',
    desc: '12V power supply. Check for terminal corrosion, charge retention (12.6V+ resting), and main starter fuse integrity.',
    relPos: new THREE.Vector3(0.35, 0.55, -0.35).normalize(),
    distFactor: 0.38,
    fov: 32,
    offset: new THREE.Vector3(0, 0.18, -0.15),
    matchKeywords: ['battery', 'fuse', 'electr', 'box', 'starter', 'wire'],
  },
  exhaust: {
    key: 'exhaust',
    title: 'Exhaust Header & Muffler',
    badge: 'EXHAUST SYSTEM',
    desc: 'Channels exhaust gases from cylinder. Check header clamp torque, rust perforation, and exhaust smoke characteristics.',
    relPos: new THREE.Vector3(0.8, -0.1, -0.55).normalize(),
    distFactor: 0.46,
    fov: 34,
    offset: new THREE.Vector3(0.3, -0.2, -0.5),
    matchKeywords: ['exhaust', 'muffler', 'pipe', 'silencer', 'header'],
  },
  brakes: {
    key: 'brakes',
    title: 'Hydraulic Disc Brake System',
    badge: 'BRAKE ASSEMBLY',
    desc: 'Front & rear calipers and discs. Inspect brake pad friction thickness (>2mm), disc scoring, and hydraulic lines.',
    relPos: new THREE.Vector3(0.55, 0.1, 0.85).normalize(),
    distFactor: 0.4,
    fov: 32,
    offset: new THREE.Vector3(0, -0.2, 0.75),
    matchKeywords: ['brake', 'caliper', 'disc', 'rotor', 'wheel', 'tire'],
  },
};

function computePartWorldTarget(key) {
  if (!modelInfo) return new THREE.Vector3();
  const def = PART_DEFS[key];
  if (!def || key === 'overview') {
    return modelInfo.center.clone();
  }

  // Attempt to find mesh in currentModel matching keywords
  if (currentModel && def.matchKeywords.length > 0) {
    let matched = null;
    currentModel.traverse(o => {
      if (!matched && o.isMesh && o.name) {
        const lower = o.name.toLowerCase();
        if (def.matchKeywords.some(kw => lower.includes(kw))) {
          matched = o;
        }
      }
    });
    if (matched) {
      const box = new THREE.Box3().setFromObject(matched);
      return box.getCenter(new THREE.Vector3());
    }
  }

  // Proportional motorcycle anatomy offset inside model bounding box
  const target = modelInfo.center.clone();
  target.x += def.offset.x * modelInfo.radius;
  target.y += def.offset.y * modelInfo.radius;
  target.z += def.offset.z * modelInfo.radius;
  return target;
}

function updatePartHud(def) {
  if (!partHud) return;
  if (!def || def.key === 'overview') {
    partHud.classList.add('d-none');
    return;
  }
  hudBadge.textContent = def.badge;
  hudTitle.textContent = def.title;
  hudDesc.textContent = def.desc;
  partHud.classList.remove('d-none');
}

function markActivePart(key) {
  currentActivePart = key;
  document.querySelectorAll('.mv-part-btn[data-part]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.part === key);
  });
  if (btnTour && key !== 'tour') btnTour.classList.remove('active');
}

/* Smooth Outside-to-Inside Camera Flight powered by Anime.js */
function focusPart(partKey, duration) {
  if (!modelInfo || !PART_DEFS[partKey]) return;
  cancelCameraTween();
  markActivePreset(null);
  markActivePart(partKey);

  const def = PART_DEFS[partKey];
  updatePartHud(def);

  const target = computePartWorldTarget(partKey);
  const dist = modelInfo.radius * def.distFactor;
  const destPos = target.clone().addScaledVector(def.relPos, dist);

  if (typeof anime === 'undefined') {
    camera.position.copy(destPos);
    controls.target.copy(target);
    camera.fov = def.fov;
    camera.updateProjectionMatrix();
    controls.update();
    return;
  }

  const state = {
    px: camera.position.x, py: camera.position.y, pz: camera.position.z,
    tx: controls.target.x, ty: controls.target.y, tz: controls.target.z,
    fov: camera.fov,
  };

  camTween = anime({
    targets: state,
    px: destPos.x, py: destPos.y, pz: destPos.z,
    tx: target.x, ty: target.y, tz: target.z,
    fov: def.fov,
    duration: duration || 1100,
    easing: 'easeInOutCubic',
    update: () => {
      camera.position.set(state.px, state.py, state.pz);
      controls.target.set(state.tx, state.ty, state.tz);
      camera.fov = state.fov;
      camera.updateProjectionMatrix();
      controls.update();
    },
    complete: () => {
      camTween = null;
      controls.minDistance = dist * 0.3;
      controls.maxDistance = dist * 4.0;
    },
  });
}

/* Cinematic Tour: moves from Outside overview into key inside parts */
function playCinematicTour() {
  if (!modelInfo) return;
  cancelCameraTween();
  markActivePreset(null);

  if (btnTour) btnTour.classList.add('active');

  const tourSteps = ['overview', 'engine', 'sprocket', 'battery', 'exhaust', 'brakes', 'overview'];
  let stepIndex = 0;

  function runNextStep() {
    if (stepIndex >= tourSteps.length) {
      if (btnTour) btnTour.classList.remove('active');
      markActivePart('overview');
      return;
    }
    const key = tourSteps[stepIndex++];
    focusPart(key, 1200);
    camTween = anime({
      duration: 2500,
      complete: () => {
        runNextStep();
      }
    });
  }

  runNextStep();
}

function resetCamera() {
  if (!modelInfo) return;
  focusPart('overview', 900);
  applyPreset('iso');
  camera.near = Math.max(modelInfo.radius / 100, 0.01);
  camera.far = modelInfo.radius * 60;
  camera.updateProjectionMatrix();
  controls.minDistance = modelInfo.radius * 0.45;
  controls.maxDistance = modelInfo.radius * 7;
  controls.maxPolarAngle = Math.PI * 0.52;
}

/* Two-stage flight: wide high approach sweep, then settle into the iso frame. */
function playIntro() {
  if (!modelInfo) return;
  const dist = framingDistance();
  const c = modelInfo.center;
  const start = c.clone().addScaledVector(new THREE.Vector3(1, 1.5, 1).normalize(), dist * 3.2);
  const mid   = c.clone().addScaledVector(new THREE.Vector3(-1, 0.55, 1).normalize(), dist * 1.45);
  const end   = c.clone().addScaledVector(CFG.defaultDir, dist);
  snapCamera(start, c);
  markActivePreset(null);
  markActivePart('overview');
  if (typeof anime === 'undefined') { snapCamera(end, c); markActivePreset('iso'); return; }
  camTween = anime.timeline({ complete: () => { camTween = null; markActivePreset('iso'); } })
    .add({ targets: camera.position, x: mid.x, y: mid.y, z: mid.z, duration: 1500, easing: 'easeOutQuad' })
    .add({ targets: camera.position, x: end.x, y: end.y, z: end.z, duration: 1700, easing: 'easeInOutCubic' });
}

/* ── Controls / lifecycle ───────────────────────────────────────────────── */
document.querySelectorAll('.mv-preset[data-preset]').forEach(btn => {
  btn.addEventListener('click', () => {
    updatePartHud(null);
    markActivePart(null);
    applyPreset(btn.dataset.preset);
  });
});
document.getElementById('mv-btn-intro').addEventListener('click', playIntro);
document.getElementById('mv-btn-reset').addEventListener('click', resetCamera);

// Parts inspection bar listeners
document.querySelectorAll('.mv-part-btn[data-part]').forEach(btn => {
  btn.addEventListener('click', () => focusPart(btn.dataset.part));
});
if (btnTour) btnTour.addEventListener('click', playCinematicTour);
if (hudClose) hudClose.addEventListener('click', () => focusPart('overview'));
if (hudOutside) hudOutside.addEventListener('click', () => focusPart('overview'));

// Canvas raycast click inspection
canvas.addEventListener('pointerdown', e => {
  pointerDownStart = { x: e.clientX, y: e.clientY, time: performance.now() };
});
canvas.addEventListener('pointerup', e => {
  const dx = Math.abs(e.clientX - pointerDownStart.x);
  const dy = Math.abs(e.clientY - pointerDownStart.y);
  const dt = performance.now() - pointerDownStart.time;
  if (dx < 6 && dy < 6 && dt < 450 && currentModel) {
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(currentModel.children, true);
    if (hits.length > 0) {
      let foundPart = null;
      let obj = hits[0].object;
      while (obj && obj !== currentModel && !foundPart) {
        if (obj.name) {
          const name = obj.name.toLowerCase();
          for (const [k, d] of Object.entries(PART_DEFS)) {
            if (d.matchKeywords.some(kw => name.includes(kw))) {
              foundPart = k;
              break;
            }
          }
        }
        obj = obj.parent;
      }
      focusPart(foundPart || 'engine');
    }
  }
});

const btnFull = document.getElementById('mv-btn-full');
btnFull.addEventListener('click', () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else viewport.requestFullscreen && viewport.requestFullscreen();
});
document.addEventListener('fullscreenchange', () => {
  btnFull.querySelector('i').className = document.fullscreenElement ? 'fa-solid fa-compress' : 'fa-solid fa-expand';
  setTimeout(fitCanvas, 60);
});

function dispose() {
  if (disposed) return;
  disposed = true;
  cancelAnimationFrame(rafId);
  if (resizeObserver) resizeObserver.disconnect();
  clearModel();
  renderer.dispose();
}
window.addEventListener('pagehide', dispose);

/* ── Boot ───────────────────────────────────────────────────────────────── */
initThree();
controls.addEventListener('start', () => {
  cancelCameraTween();
  markActivePreset(null);
  if (btnTour) btnTour.classList.remove('active');
});
setStatus('Loading model…');
window.MV = {   // small debug/testing API
  loadModel, fitCamera, dispose, applyPreset, playIntro, focusPart, playCinematicTour,
  PART_DEFS,
  get modelInfo() { return modelInfo; },
  get camera() { return camera; },
  get controls() { return controls; },
  get tweenActive() { return !!camTween; },
};
loadModel(CFG.modelUrl).then(() => playIntro());
