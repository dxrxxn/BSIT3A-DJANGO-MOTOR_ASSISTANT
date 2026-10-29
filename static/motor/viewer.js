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
  clearHighlight();
  root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  prepareModelMaterials(root);
  const info = groundAndNormalize(root);
  modelInfo = Object.assign(info, inspectModel(root));
  currentModel = root;
  scene.add(root);
  buildPartAvailability();
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
/* Mesh names below are the exact node names in motorcycle.glb.  A component
   is available only when at least one of its meshes exists in the loaded GLB;
   nothing is positioned by guesswork or anatomical offset. */
const PART_DEFS = {
  overview: {
    key: 'overview',
    title: 'Motorcycle Overview (Exterior)',
    badge: 'EXTERIOR VIEW',
    desc: 'Complete vehicle exterior contained in the model. Drag to orbit, scroll to zoom, or select an available component below.',
    relPos: new THREE.Vector3(1, 0.55, 1).normalize(),
    distFactor: 1.35,
    fov: 40,
    meshNames: [],
  },
  engine: {
    key: 'engine',
    title: 'Engine Case & Transmission Cover',
    badge: 'EXTERIOR ENGINE PARTS',
    desc: 'The GLB contains the engine transmission case and outer engine cover. Internal parts such as the piston, valves, clutch plates and oil pump are not modelled.',
    relPos: new THREE.Vector3(0.55, 0.2, 0.75).normalize(),
    distFactor: 0.44,
    fov: 32,
    meshNames: ['engine_transmission_case', 'engine_cover'],
    limitation: 'Only the outer engine case and cover are present. This view cannot confirm internal engine condition.',
  },
  exhaust: {
    key: 'exhaust',
    title: 'Exhaust Pipe & Muffler',
    badge: 'EXHAUST SYSTEM',
    desc: 'Exhaust pipe, muffler body and exhaust tip as modelled. Header flange, internal baffles and mounting hardware are not separately modelled.',
    relPos: new THREE.Vector3(0.8, -0.1, -0.55).normalize(),
    distFactor: 0.46,
    fov: 34,
    meshNames: ['exhaust_pipe', 'exhaust_muffler', 'exhaust_tip'],
    limitation: 'The model shows external exhaust geometry only. It cannot show blockages, leaks or internal baffle condition.',
  },
  brakes: {
    key: 'brakes',
    title: 'Front Brake Disc & Hub',
    badge: 'BRAKE COMPONENT',
    desc: 'Front brake disc and disc hub as modelled. The caliper, pads, master cylinder, brake hose and fluid are not present in this GLB.',
    relPos: new THREE.Vector3(0.55, 0.1, 0.85).normalize(),
    distFactor: 0.4,
    fov: 32,
    meshNames: ['front_brake_disc', 'front_disc_hub'],
    limitation: 'Brake safety cannot be confirmed from a 3D mesh. Inspect pad thickness, disc condition, lever feel and fluid level physically, or have a qualified technician check them.',
  },
  wheels: {
    key: 'wheels',
    title: 'Front & Rear Wheels',
    badge: 'WHEELS & AXLES',
    desc: 'Tires, rims, spokes and axles are modelled at both ends. Tire pressure, tread depth and bearing condition are not represented.',
    relPos: new THREE.Vector3(0.15, 0.15, 0.95).normalize(),
    distFactor: 0.72,
    fov: 36,
    meshNames: ['front_tire', 'front_rim', 'front_spoke', 'front_axle', 'rear_tire', 'rear_rim', 'rear_spoke', 'rear_axle'],
    limitation: 'A 3D tire cannot show pressure, tread wear, cracks or bearing play. Check those physically.',
  },
  bodywork: {
    key: 'bodywork',
    title: 'Fairings, Panels & Body Trim',
    badge: 'BODYWORK',
    desc: 'Front fairing, side panels, fenders, floorboard, seat and tail trim as modelled. Fasteners, clips and hidden brackets are not modelled.',
    relPos: new THREE.Vector3(0.5, 0.25, 0.85).normalize(),
    distFactor: 1.0,
    fov: 38,
    meshNames: ['front_fairing_main', 'front_fairing_center', 'front_side_fairing', 'silver_fairing_accent', 'rear_side_panel', 'side_panel_accent', 'tail_fairing', 'front_fender', 'rear_mudguard', 'floorboard', 'footboard_trim', 'seat_base', 'seat_front', 'rear_grab_rail_left', 'rear_grab_rail_right', 'center_badge'],
    limitation: 'The model cannot show cracked clips, missing fasteners or damage hidden behind panels.',
  },
  controls: {
    key: 'controls',
    title: 'Controls, Lights & Suspension',
    badge: 'CONTROLS & CHASSIS',
    desc: 'Handlebar, grips, mirrors, instrument cluster, lights, fork, rear shock, stands and lower frame as modelled. Cables, hydraulics and wiring are not modelled.',
    relPos: new THREE.Vector3(0.6, 0.4, 0.75).normalize(),
    distFactor: 0.8,
    fov: 36,
    meshNames: ['handlebar', 'handle_grip', 'mirror_stem', 'mirror', 'instrument_cluster', 'dashboard_screen', 'headlight_lens', 'indicator_lens', 'tail_light', 'rear_indicator', 'front_fork', 'rear_shock', 'rear_shock_spring', 'center_stand_left', 'center_stand_right', 'side_stand', 'steering_stem', 'lower_frame'],
    limitation: 'Cables, brake lines, wiring and internal suspension parts are not modelled, so their condition cannot be judged here.',
  },
  sprocket: {
    key: 'sprocket',
    title: 'Front Sprocket & Drive',
    badge: 'NOT MODELLED',
    desc: 'This GLB does not contain a front sprocket, chain or rear sprocket.',
    relPos: new THREE.Vector3(-0.75, -0.05, -0.45).normalize(),
    distFactor: 0.36,
    fov: 30,
    meshNames: [],
    unavailableReason: 'Front sprocket, chain and rear sprocket are not present in this GLB.',
  },
  battery: {
    key: 'battery',
    title: 'Battery & Electrical Hub',
    badge: 'NOT MODELLED',
    desc: 'This GLB does not contain a battery, fuse box or electrical harness.',
    relPos: new THREE.Vector3(0.35, 0.55, -0.35).normalize(),
    distFactor: 0.38,
    fov: 32,
    meshNames: [],
    unavailableReason: 'Battery, fuse box and electrical harness are not present in this GLB.',
  },
};

let highlightedMeshes = [];
let meshNameToPart = new Map();

function prepareModelMaterials(root) {
  root.traverse(o => {
    if (!o.isMesh) return;
    const source = Array.isArray(o.material) ? o.material : [o.material];
    const cloned = source.map(material => (material ? material.clone() : material));
    o.material = Array.isArray(o.material) ? cloned : cloned[0];
  });
}

function buildPartAvailability() {
  const byName = new Map();
  if (currentModel) {
    currentModel.traverse(o => {
      if (!o.isMesh || !o.name) return;
      const key = o.name.toLowerCase();
      if (!byName.has(key)) byName.set(key, []);
      byName.get(key).push(o);
    });
  }

  meshNameToPart = new Map();
  Object.values(PART_DEFS).forEach(def => {
    if (def.key === 'overview') {
      def.available = true;
      def.meshes = [];
      return;
    }
    def.meshes = [];
    (def.meshNames || []).forEach(name => {
      const lower = name.toLowerCase();
      meshNameToPart.set(lower, def.key);
      (byName.get(lower) || []).forEach(mesh => def.meshes.push(mesh));
    });
    def.available = def.meshes.length > 0;
    if (!def.available && !def.unavailableReason) {
      def.unavailableReason = 'The required mesh is not present in this GLB.';
    }
  });

  document.querySelectorAll('.mv-part-btn[data-part]').forEach(btn => {
    const def = PART_DEFS[btn.dataset.part];
    if (!def) return;
    if (def.available === false) {
      btn.disabled = true;
      btn.classList.add('is-unavailable');
      btn.title = def.title + ' — ' + def.unavailableReason;
      btn.setAttribute('aria-disabled', 'true');
    } else {
      btn.disabled = false;
      btn.classList.remove('is-unavailable');
      btn.title = def.title;
      btn.removeAttribute('aria-disabled');
    }
  });

  const coverageEl = document.getElementById('mv-coverage-text');
  if (coverageEl) {
    const available = Object.values(PART_DEFS)
      .filter(def => def.key !== 'overview' && def.available)
      .map(def => def.title);
    const missing = Object.values(PART_DEFS)
      .filter(def => def.key !== 'overview' && !def.available)
      .map(def => def.title);
    coverageEl.textContent = 'Modelled: ' + (available.join(', ') || 'exterior only')
      + (missing.length ? ' · Not modelled: ' + missing.join(', ') : '');
  }
}

function clearHighlight() {
  highlightedMeshes.forEach(mesh => {
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    mats.forEach(m => {
      if (!m || !m.emissive || m.__mvBaseEmissive === undefined) return;
      m.emissive.setHex(m.__mvBaseEmissive);
      m.emissiveIntensity = m.__mvBaseIntensity;
    });
  });
  highlightedMeshes = [];
}

function highlightPart(def) {
  clearHighlight();
  if (!def || !def.meshes) return;
  def.meshes.forEach(mesh => {
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    mats.forEach(m => {
      if (!m || !m.emissive) return;
      if (m.__mvBaseEmissive === undefined) {
        m.__mvBaseEmissive = m.emissive.getHex();
        m.__mvBaseIntensity = m.emissiveIntensity;
      }
      m.emissive.setHex(0x4f46e5);
      m.emissiveIntensity = 0.55;
    });
    highlightedMeshes.push(mesh);
  });
}

function computePartWorldTarget(key) {
  if (!modelInfo) return new THREE.Vector3();
  const def = PART_DEFS[key];
  if (!def || key === 'overview') {
    return modelInfo.center.clone();
  }

  if (def.meshes && def.meshes.length) {
    const box = new THREE.Box3();
    def.meshes.forEach(mesh => box.expandByObject(mesh));
    if (!box.isEmpty()) return box.getCenter(new THREE.Vector3());
  }

  // Only reached for an unavailable component; callers guard against that.
  return modelInfo.center.clone();
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
  const limitEl = document.getElementById('mv-hud-limit');
  if (limitEl) {
    limitEl.textContent = def.limitation || '';
    limitEl.classList.toggle('d-none', !def.limitation);
  }
  partHud.classList.remove('d-none');
}

function markActivePart(key) {
  currentActivePart = key;
  document.querySelectorAll('.mv-part-btn[data-part]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.part === key);
  });
  if (btnTour && key !== 'tour') btnTour.classList.remove('active');
}

function updatePartUrl(key) {
  try {
    const url = new URL(window.location.href);
    if (!key || key === 'overview') url.searchParams.delete('part');
    else url.searchParams.set('part', key);
    window.history.replaceState({}, '', url.toString());
  } catch (e) {}
}

function partFromUrl() {
  try {
    const key = new URLSearchParams(window.location.search).get('part');
    if (!key) return null;
    const def = PART_DEFS[key];
    if (!def || key === 'overview' || def.available === false) return null;
    return key;
  } catch (e) {
    return null;
  }
}

function selectPart(key, options) {
  options = options || {};
  const def = PART_DEFS[key];
  if (!def) return false;
  if (key !== 'overview' && def.available === false) {
    setStatus('That component is not present in this model.', 'err');
    return false;
  }
  stopTour();
  const ok = focusPart(key);
  if (ok !== false && options.updateUrl !== false) updatePartUrl(key);
  return ok !== false;
}

/* Smooth Outside-to-Inside Camera Flight powered by Anime.js */
function focusPart(partKey, duration) {
  if (!modelInfo || !PART_DEFS[partKey]) return false;
  const def = PART_DEFS[partKey];
  if (partKey !== 'overview' && def.available === false) return false;

  cancelCameraTween();
  markActivePreset(null);
  markActivePart(partKey);
  updatePartHud(def);
  highlightPart(partKey === 'overview' ? null : def);

  const target = computePartWorldTarget(partKey);
  const dist = modelInfo.radius * def.distFactor;
  const destPos = target.clone().addScaledVector(def.relPos, dist);

  if (typeof anime === 'undefined') {
    camera.position.copy(destPos);
    controls.target.copy(target);
    camera.fov = def.fov;
    camera.updateProjectionMatrix();
    controls.update();
    return true;
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
  return true;
}

/* Cinematic Tour: visits only components that actually exist in the GLB. */
let tourTimer = null;
let tourActive = false;

function stopTour() {
  tourActive = false;
  if (tourTimer !== null) {
    clearTimeout(tourTimer);
    tourTimer = null;
  }
  if (btnTour) btnTour.classList.remove('active');
}

function playCinematicTour() {
  if (!modelInfo) return;
  stopTour();
  cancelCameraTween();
  markActivePreset(null);

  const tourSteps = ['overview'].concat(
    Object.keys(PART_DEFS).filter(key => key !== 'overview' && PART_DEFS[key].available)
  ).concat(['overview']);
  let stepIndex = 0;
  tourActive = true;
  if (btnTour) btnTour.classList.add('active');

  function runNextStep() {
    if (!tourActive) return;
    if (stepIndex >= tourSteps.length) {
      stopTour();
      selectPart('overview');
      return;
    }
    const key = tourSteps[stepIndex++];
    focusPart(key, 1000);
    tourTimer = setTimeout(runNextStep, 2200);
  }

  runNextStep();
}

function resetCamera() {
  if (!modelInfo) return;
  selectPart('overview');
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
    stopTour();
    clearHighlight();
    updatePartHud(null);
    markActivePart(null);
    updatePartUrl(null);
    applyPreset(btn.dataset.preset);
  });
});
document.getElementById('mv-btn-intro').addEventListener('click', playIntro);
document.getElementById('mv-btn-reset').addEventListener('click', resetCamera);

// Parts inspection bar listeners
document.querySelectorAll('.mv-part-btn[data-part]').forEach(btn => {
  btn.addEventListener('click', () => selectPart(btn.dataset.part));
});
if (btnTour) btnTour.addEventListener('click', playCinematicTour);
if (hudClose) hudClose.addEventListener('click', () => selectPart('overview'));
if (hudOutside) hudOutside.addEventListener('click', () => selectPart('overview'));

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
        if (obj.name && meshNameToPart.has(obj.name.toLowerCase())) {
          foundPart = meshNameToPart.get(obj.name.toLowerCase());
        }
        obj = obj.parent;
      }
      if (foundPart) {
        selectPart(foundPart);
      } else {
        setStatus('No inspectable component under that point.', '');
        setTimeout(() => {
          if (modelInfo) {
            setStatus('Model loaded · ' + modelInfo.meshes + ' meshes · ' + modelInfo.faces.toLocaleString() + ' faces', 'ok');
          }
        }, 2200);
      }
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
  stopTour();
  cancelCameraTween();
  markActivePreset(null);
});
setStatus('Loading model…');
window.MV = {   // small debug/testing API
  loadModel, fitCamera, dispose, applyPreset, playIntro, focusPart, selectPart, playCinematicTour,
  PART_DEFS,
  get modelInfo() { return modelInfo; },
  get camera() { return camera; },
  get controls() { return controls; },
  get tweenActive() { return !!camTween; },
};

window.addEventListener('popstate', () => {
  const key = partFromUrl();
  selectPart(key || 'overview', { updateUrl: false });
});

loadModel(CFG.modelUrl).then(() => {
  const requestedPart = partFromUrl();
  if (requestedPart) selectPart(requestedPart);
  else playIntro();
});
