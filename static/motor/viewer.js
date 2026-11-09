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
/* Mesh names below are the exact node names in motorcycle.glb. A component
   is available when its meshes exist or when it serves as a physical chassis
   pinpoint location guide with verified spatial coordinates. */
const PART_DEFS = {
  overview: {
    key: 'overview',
    title: 'Motorcycle Overview (Exterior)',
    badge: 'EXTERIOR VIEW',
    location: 'Entire exterior chassis and geometry. Includes frame, body panels, wheels, suspension, exhaust, and controls.',
    desc: 'Complete vehicle exterior. Drag to orbit 360°, scroll to zoom in/out, or select a component below to inspect and locate individual systems.',
    checklist: '• Walk around the motorcycle checking overall symmetry and frame alignment.\n• Look for fluid drips (oil, coolant, brake fluid) on the ground underneath the motorcycle.\n• Check tire condition and ensure side/center stands deploy firmly.',
    relPos: new THREE.Vector3(1, 0.55, 1).normalize(),
    distFactor: 1.35,
    fov: 40,
    meshNames: [],
    limitation: 'This viewer shows exterior 3D geometry only. Internal engine/transmission components, fluid conditions, and electrical circuits require physical inspection.',
  },
  engine: {
    key: 'engine',
    title: 'Engine Case & Transmission Cover',
    badge: 'EXTERIOR ENGINE PARTS',
    location: 'Centered low in the motorcycle frame between the front and rear wheels, positioned directly under the fuel tank and seat.\n• Right side: Clutch casing, oil filler cap, and oil level sight glass or dipstick.\n• Left side: Stator/alternator cover (manual bikes) or the elongated CVT belt transmission casing (automatic scooters like Click 125i).\n• Underside: Oil drain bolt facing downward toward the ground.',
    desc: 'The engine crankcase forms the structural block containing the crankshaft, connecting rods, and oil sump. The outer side covers protect the clutch, stator coils, and timing mechanisms while sealing in pressurized engine oil.',
    checklist: '• Inspect gasket mating seams for wet engine oil weeping or accumulated road grime.\n• Check aluminum casing for impact cracks, gouges, or road rash from falls.\n• Verify engine oil level in the sight glass on a level surface with engine warm (between MIN & MAX lines).\n• Ensure oil drain plug and oil strainer/filter covers are torqued and leak-free.',
    relPos: new THREE.Vector3(0.55, 0.2, 0.75).normalize(),
    distFactor: 0.44,
    fov: 32,
    meshNames: ['engine_transmission_case', 'engine_cover', 'engine_4', 'engine'],
    limitation: 'Only the outer engine case and cover are present. Internal parts such as the piston, valves, clutch plates and oil pump are not modelled and require engine teardown to inspect.',
  },
  exhaust: {
    key: 'exhaust',
    title: 'Exhaust Pipe & Muffler Assembly',
    badge: 'EXHAUST SYSTEM',
    location: 'Runs from the front exhaust port of the engine cylinder head, routes low underneath the crankcase along the right side of the swingarm, and exits at the elevated rear muffler canister.',
    desc: 'The exhaust system channels hot burned combustion gases away from the engine to the rear. It dampens exhaust noise via internal silencer baffles, reduces harmful emissions through the catalytic converter, and mounts the oxygen (O2) sensor for fuel injection control.',
    checklist: '• Check cylinder head exhaust flange for soot deposits or blowing gas (indicates a blown exhaust gasket).\n• Inspect underside of header pipe and collector for road denting, rust perforation, or cracked welds.\n• Ensure muffler mounting hanger bolts and rubber bushings are tight.\n• Check heat shields for loose bolts that cause metallic buzzing at idle.',
    relPos: new THREE.Vector3(0.8, -0.1, -0.55).normalize(),
    distFactor: 0.46,
    fov: 34,
    meshNames: ['exhaust_pipe', 'exhaust_muffler', 'exhaust_tip', 'exhaust_39', 'exhaust_1_40', 'exhaust'],
    limitation: 'The model shows external exhaust geometry only. It cannot show blockages, leaks or internal baffle condition.',
  },
  brakes: {
    key: 'brakes',
    title: 'Front Brake Disc & Hub Assembly',
    badge: 'BRAKE COMPONENT',
    location: 'Mounted directly to the front wheel hub on the front axle, rotating between the hydraulic brake caliper pads on the front fork legs.',
    desc: 'The front brake disc (rotor) is a precision-machined stainless steel rotor. When you squeeze the right handlebar brake lever, hydraulic fluid pushes caliper pistons, clamping friction pads against this rotating disc to bring the motorcycle safely to a halt.',
    checklist: '• Run a finger across the rotor face to check for deep grooves, ridges, or an outer lip (replace if below stamped MIN. TH. limit, typically 3.0mm–3.5mm).\n• Check for dark blue or rainbow heat discoloration, indicating stuck caliper slide pins.\n• Verify brake lever feel: it should be firm and progressive, not spongy (spongy feel indicates air in hydraulic lines).\n• Inspect disc mounting bolts to ensure none are loose.',
    relPos: new THREE.Vector3(0.55, 0.1, 0.85).normalize(),
    distFactor: 0.4,
    fov: 32,
    meshNames: ['front_brake_disc', 'front_disc_hub', 'bikedisc_f_11', 'bikedisc_f_66', 'bikedisc_r_47'],
    limitation: 'Brake safety cannot be confirmed from a 3D mesh. Inspect pad thickness, disc condition, lever feel and fluid level physically, or have a qualified technician check them.',
  },
  wheels: {
    key: 'wheels',
    title: 'Front & Rear Wheels, Tires & Axles',
    badge: 'WHEELS & AXLES',
    location: 'Located at both ends of the motorcycle chassis: the front wheel is secured inside the front fork dropouts; the rear wheel is mounted inside the swingarm and connected to the final drive.',
    desc: 'The rolling chassis assembly consisting of cast aluminum alloy rims (or steel spoked rims), tubeless pneumatic rubber tires, wheel bearings, and high-tensile steel axle shafts that maintain road grip and absorb surface bumps.',
    checklist: '• Tire pressure: Check cold pressure weekly with a tire gauge (typically 28–32 PSI front, 32–36 PSI rear).\n• Tread depth: Inspect tread wear indicator (TWI) bars; replace before tread wears flush with indicators.\n• Sidewall check: Look for cuts, ozone cracking, dry rot, or embedded punctures.\n• Wheel bearings: Lift wheel and push/pull rim side-to-side; any clunking or play means wheel bearings must be replaced.',
    relPos: new THREE.Vector3(0.15, 0.15, 0.95).normalize(),
    distFactor: 0.72,
    fov: 36,
    meshNames: ['front_tire', 'front_rim', 'front_spoke', 'front_axle', 'rear_tire', 'rear_rim', 'rear_spoke', 'rear_axle', 'wheel_lf_16', 'wheel_lr_53', 'wheelmeshbk_f_12', 'wheelmeshbk_r_49', 'front_tyre', 'back_tyre'],
    limitation: 'A 3D tire cannot show pressure, tread wear, cracks or bearing play. Check those physically.',
  },
  bodywork: {
    key: 'bodywork',
    title: 'Fairings, Panels & Protective Body Trim',
    badge: 'BODYWORK',
    location: 'Envelopes the entire motorcycle chassis from the front headlight cowl and side flank panels down to the footboard and rear tail section.',
    desc: 'Aerodynamic ABS plastic fairings, side covers, front fender, floorboard, and tail panels. They streamline air resistance, shield electrical wiring and the fuel tank from weather and road spray, and shape the motorcycle styling.',
    checklist: '• Inspect plastic mounting tabs and push-clip fasteners for fractures or looseness causing vibration buzzes.\n• Ensure front fender has adequate clearance from the tire throughout full fork travel.\n• Check seat latch and release cable to ensure under-seat storage locks securely.\n• Check for panel gaps or misalignment after drops.',
    relPos: new THREE.Vector3(0.5, 0.25, 0.85).normalize(),
    distFactor: 1.0,
    fov: 38,
    meshNames: ['front_fairing_main', 'front_fairing_center', 'front_side_fairing', 'silver_fairing_accent', 'rear_side_panel', 'side_panel_accent', 'tail_fairing', 'front_fender', 'rear_mudguard', 'floorboard', 'footboard_trim', 'seat_base', 'seat_front', 'rear_grab_rail_left', 'rear_grab_rail_right', 'center_badge', 'bodyshell_68', 'bodyshell_58', 'petroltank_5', 'seat_f_1', 'seat_r_3'],
    limitation: 'The model cannot show cracked clips, missing fasteners or damage hidden behind panels.',
  },
  controls: {
    key: 'controls',
    title: 'Controls, Lights & Chassis Suspension',
    badge: 'CONTROLS & CHASSIS',
    location: '• Cockpit: Handlebars, grips, throttle, levers, mirrors, and instrument cluster in front of rider.\n• Front Suspension: Telescopic hydraulic fork legs extending from triple clamp to front axle.\n• Rear Suspension: Shock absorber with coil spring between frame and swingarm.\n• Lighting: Headlight in front cowl, turn signals on sides, and brake light on rear fender.',
    desc: 'The rider control interface, vehicle signaling, and chassis suspension. Includes handlebar grips, throttle tube, levers, switches, headlights, front telescopic forks, and rear shock absorber with preload spring.',
    checklist: '• Throttle free play: Must twist smoothly and snap shut instantly in all handlebar turn positions.\n• Levers: Ensure 10–15mm clutch lever free play and firm brake lever engagement.\n• Fork seals: Wipe inner chrome stanchions clean; pump suspension and inspect for oil ring weeping past rubber seals.\n• Lighting check: Test high/low headlight beam, horn, front/rear turn signals, and brake light activation from both controls.',
    relPos: new THREE.Vector3(0.6, 0.4, 0.75).normalize(),
    distFactor: 0.8,
    fov: 36,
    meshNames: ['handlebar', 'handle_grip', 'mirror_stem', 'mirror', 'instrument_cluster', 'dashboard_screen', 'headlight_lens', 'indicator_lens', 'tail_light', 'rear_indicator', 'front_fork', 'rear_shock', 'rear_shock_spring', 'center_stand_left', 'center_stand_right', 'side_stand', 'steering_stem', 'lower_frame', 'handlebars_120', 'handlebars_10', 'forks_l_17', 'forks_u_34', 'headlight_l_21', 'headlight_r_22', 'brakelight_m_36', 'brakelight_r_37', 'brakelight_l_38', 'headlight', 'taillight'],
    limitation: 'Cables, brake lines, wiring and internal suspension parts are not modelled, so their condition cannot be judged here.',
  },
  sprocket: {
    key: 'sprocket',
    title: 'Front Sprocket & Final Drive Assembly',
    badge: 'FINAL DRIVE · COVER ACCESS',
    location: 'Located on the lower left side of the engine crankcase, directly forward of the swingarm pivot and behind the front sprocket cover (near the gear shift lever on manual motorcycles, or inside the front variator pulley of CVT scooters).',
    desc: 'The countershaft front drive sprocket is a hardened steel gear mounted directly to the engine transmission output shaft. It meshes with the drive chain to transfer engine torque directly to the rear wheel.',
    checklist: '• Access steps: Use an 8mm or 10mm socket to remove the 2–3 sprocket cover bolts on the lower left crankcase.\n• Tooth inspection: Check teeth for sharpness or hooked "shark-fin" curving; worn sprockets cause chain slipping and rapid chain wear.\n• Retaining nut: Verify sprocket lock-washer and nut/circlip are tight and secure.\n• Grime cleaning: Scrape away built-up chain wax, grit, and sand packed inside the sprocket cavity.\n• Chain slack: Verify 20–30mm vertical chain slack midway between sprockets.',
    relPos: new THREE.Vector3(-0.75, -0.05, -0.45).normalize(),
    distFactor: 0.38,
    fov: 30,
    meshNames: ['sprocket', 'chain', 'drive_chain', 'rear_sprocket'],
    isPinpointable: true,
    limitation: 'The front sprocket is enclosed behind the left engine cover. The 3D camera highlights its physical chassis position; follow the access steps above to inspect the teeth physically.',
  },
  battery: {
    key: 'battery',
    title: '12V Battery & Electrical Power Hub',
    badge: 'ELECTRICAL HUB · SEAT / FLOOR ACCESS',
    location: 'Mounted inside a protective chassis battery compartment:\n• Standard / Sport bikes (e.g. Yamaha MT-09): Directly beneath the rider seat.\n• Underbone bikes & scooters (e.g. Honda Click 125i): Beneath the removable floorboard footrest lid or behind the front handlebar cover.',
    desc: 'The 12-volt sealed lead-acid (AGM) or lithium battery supplies electrical power to spin the electric starter motor, power the Engine Control Unit (ECU), run the fuel pump, spark ignition coils, and illuminate lights before the engine alternator starts charging.',
    checklist: '• Access steps: Unlock and lift the rider seat with your ignition key, or use a #2 Phillips screwdriver to remove the 2 floorboard battery cover screws.\n• Terminal check: Inspect battery terminals for white/blue powdery corrosion; clean with baking soda water and wire brush, then apply dielectric grease.\n• Voltage test: Measure DC voltage with a multimeter across terminals (12.5V–12.8V healthy, 12.0V discharged, <11.8V dead cells).\n• Charging test: Run engine at 3,000 RPM; voltage should climb to 13.8V–14.4V, confirming stator/rectifier operation.\n• Main fuse: Check the adjacent 15A/20A/30A main blade fuse for a blown link.',
    relPos: new THREE.Vector3(0.35, 0.55, -0.35).normalize(),
    distFactor: 0.40,
    fov: 32,
    meshNames: ['battery', 'battery_tray', 'ecu', 'fuse_box'],
    isPinpointable: true,
    limitation: 'The battery and wiring harness are enclosed within the vehicle frame. The 3D camera highlights its physical compartment; follow the location steps above to access the terminals physically.',
  },
};

let highlightedMeshes = [];
let meshNameToPart = new Map();
let meshToPart = new Map();

function classifyYamahaMesh(mesh) {
  const name = (mesh.name || '').toLowerCase();
  const mat = mesh.material ? (Array.isArray(mesh.material) ? mesh.material[0] : mesh.material) : null;
  const matName = (mat && mat.name ? mat.name : '').toLowerCase();

  const box = new THREE.Box3().setFromObject(mesh);
  const c = box.getCenter(new THREE.Vector3());

  // 1. Wheels (tyres or rims)
  if (matName.includes('tyre') || matName.includes('tire') || matName.includes('material.018') || matName.includes('material.019') || matName.includes('material_42')) {
    return 'wheels';
  }
  // 2. Brakes (brake discs front & rear)
  if (matName.includes('material.013') || matName.includes('material.014') || name.includes('bikedisc')) {
    return 'brakes';
  }
  // 3. Exhaust (pipes & muffler on the right side)
  if (matName.includes('material.017') || matName.includes('material.012') || (c.z > 0.0 && c.x > 0.08 && c.y < 0.0 && (matName.includes('black') || matName.includes('dinghyblack') || matName.includes('material')))) {
    return 'exhaust';
  }
  // 4. Drive Chain & Sprocket (left side, middle rear)
  if (matName.includes('material.015') || (c.x < -0.05 && c.z > 0.1 && c.y < 0.0)) {
    return 'sprocket';
  }
  // 5. Battery & Electrical (under rider seat)
  if (matName.includes('material.010') || (c.z > 0.15 && c.z < 0.45 && c.y > 0.2 && c.y < 0.4 && (matName.includes('plastic_black') || matName.includes('black')))) {
    return 'battery';
  }
  // 6. Controls (cockpit, handlebars, instrument dials, mirrors, headlight, gold forks)
  if (matName.includes('dials') || matName.includes('speed') || matName.includes('headlight') || matName.includes('glass1') || matName.includes('glass') || matName.includes('material_29') || matName.includes('gold') || c.y > 0.45 || (c.y > 0.15 && c.z < -0.55)) {
    return 'controls';
  }
  // 7. Bodywork (fuel tank, fairings, tail, seat, fenders)
  if (matName.includes('vehicle_generic_smallspecmap_primary') || matName.includes('taillight') || matName.includes('material.009') || matName.includes('material.016') || (c.y > 0.25 && c.z > -0.3)) {
    return 'bodywork';
  }
  // 8. Engine (engine block, cylinder, transmission case, radiator)
  return 'engine';
}

function prepareModelMaterials(root) {
  root.traverse(o => {
    if (!o.isMesh) return;
    const source = Array.isArray(o.material) ? o.material : [o.material];
    const cloned = source.map(material => (material ? material.clone() : material));
    o.material = Array.isArray(o.material) ? cloned : cloned[0];
  });
}

function buildPartAvailability() {
  meshNameToPart = new Map();
  meshToPart = new Map();

  // Reset meshes on part definitions
  Object.values(PART_DEFS).forEach(def => {
    def.meshes = [];
    def.available = (def.key === 'overview');
  });

  if (currentModel) {
    const allMeshes = [];
    currentModel.traverse(o => {
      if (o.isMesh) allMeshes.push(o);
    });

    // Check if model has explicitly named procedural parts (like the Honda Click model)
    const hasNamedParts = allMeshes.some(m => {
      const n = (m.name || '').toLowerCase();
      return n.includes('front_tire') || n.includes('engine_cover') || n.includes('front_brake_disc');
    });

    allMeshes.forEach(mesh => {
      const name = (mesh.name || '').toLowerCase();
      let matchedKey = null;

      if (hasNamedParts) {
        // Direct named part lookup
        for (const def of Object.values(PART_DEFS)) {
          if (def.key === 'overview') continue;
          if ((def.meshNames || []).some(mn => mn.toLowerCase() === name)) {
            matchedKey = def.key;
            break;
          }
        }
      } else {
        // Dynamic classification for complex CAD/Sketchfab models (e.g. Yamaha MT-09)
        matchedKey = classifyYamahaMesh(mesh);
      }

      if (matchedKey && PART_DEFS[matchedKey]) {
        PART_DEFS[matchedKey].meshes.push(mesh);
        meshToPart.set(mesh, matchedKey);
        if (mesh.name) meshNameToPart.set(mesh.name.toLowerCase(), matchedKey);
      }
    });

    // Determine availability of each component
    Object.values(PART_DEFS).forEach(def => {
      if (def.key === 'overview') {
        def.available = true;
      } else if (def.isPinpointable) {
        // Physical chassis pinpointable component
        def.available = true;
      } else {
        def.available = def.meshes.length > 0;
      }
    });
  }

  // Update parts toolbar buttons
  document.querySelectorAll('.mv-part-btn[data-part]').forEach(btn => {
    const partKey = btn.dataset.part;
    const def = PART_DEFS[partKey];
    if (!def) return;
    if (def.available === false && !def.isPinpointable) {
      btn.disabled = true;
      btn.classList.add('is-unavailable');
      btn.title = def.title + ' — Not present in this model';
      btn.setAttribute('aria-disabled', 'true');
    } else {
      btn.disabled = false;
      btn.classList.remove('is-unavailable');
      if (def.isPinpointable && (!def.meshes || def.meshes.length === 0)) {
        btn.classList.add('is-unmodelled');
        btn.title = def.title + ' — Physical chassis location pinpoint';
      } else {
        btn.title = def.title + (def.meshes && def.meshes.length ? ' (' + def.meshes.length + ' meshes)' : '');
      }
      btn.removeAttribute('aria-disabled');
    }
  });

  const coverageEl = document.getElementById('mv-coverage-text');
  if (coverageEl) {
    const available = Object.values(PART_DEFS)
      .filter(def => def.key !== 'overview' && def.available)
      .map(def => def.title);
    const missing = Object.values(PART_DEFS)
      .filter(def => def.key !== 'overview' && !def.available && !def.isPinpointable)
      .map(def => def.title);
    coverageEl.textContent = 'Active Components: ' + (available.join(' · ') || 'Overview only')
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

  // Precise chassis target coordinates for components inside/behind covers
  if (key === 'sprocket') {
    // Lower left side, just ahead of swingarm pivot
    return modelInfo.center.clone().add(new THREE.Vector3(-modelInfo.radius * 0.22, -modelInfo.radius * 0.16, -modelInfo.radius * 0.12));
  }
  if (key === 'battery') {
    // Under rider seat, centered
    return modelInfo.center.clone().add(new THREE.Vector3(0.0, modelInfo.radius * 0.18, -modelInfo.radius * 0.18));
  }

  return modelInfo.center.clone();
}

function updatePartHud(def) {
  if (!partHud) return;
  if (!def || def.key === 'overview') {
    partHud.classList.add('d-none');
    return;
  }
  if (hudBadge) hudBadge.textContent = def.badge || 'COMPONENT';
  if (hudTitle) hudTitle.textContent = def.title || '';
  if (hudDesc) hudDesc.textContent = def.desc || '';

  const locEl = document.getElementById('mv-hud-location');
  const locBox = document.getElementById('mv-hud-location-box');
  if (locEl) locEl.textContent = def.location || '';
  if (locBox) locBox.classList.toggle('d-none', !def.location);

  const checkEl = document.getElementById('mv-hud-checklist');
  const checkBox = document.getElementById('mv-hud-checklist-box');
  if (checkEl) checkEl.textContent = def.checklist || '';
  if (checkBox) checkBox.classList.toggle('d-none', !def.checklist);

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
    if (!def || key === 'overview' || (!def.available && !def.isPinpointable)) return null;
    return key;
  } catch (e) {
    return null;
  }
}

function selectPart(key, options) {
  options = options || {};
  const def = PART_DEFS[key];
  if (!def) return false;
  if (key !== 'overview' && !def.available && !def.isPinpointable) {
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
  if (partKey !== 'overview' && def.available === false && !def.isPinpointable) return false;

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

const btnPinpoint = document.getElementById('mv-hud-pinpoint');
if (btnPinpoint) {
  btnPinpoint.addEventListener('click', () => {
    const key = currentActivePart || 'overview';
    const def = PART_DEFS[key];
    if (window.JarvisWidget && typeof window.JarvisWidget.pinpointPart === 'function') {
      window.JarvisWidget.pinpointPart(def);
    }
  });
}

const btnAskJarvis = document.getElementById('mv-hud-ask-jarvis');
if (btnAskJarvis) {
  btnAskJarvis.addEventListener('click', () => {
    const key = currentActivePart || 'overview';
    const def = PART_DEFS[key];
    const prompt = def && key !== 'overview'
      ? `How do I inspect and troubleshoot the ${def.title}?`
      : 'What should I inspect first on this motorcycle?';
    if (window.JarvisWidget && typeof window.JarvisWidget.openWithQuery === 'function') {
      window.JarvisWidget.openWithQuery(prompt);
    } else if (window.JarvisWidget && typeof window.JarvisWidget.open === 'function') {
      window.JarvisWidget.open();
    }
  });
}

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
      const hitObj = hits[0].object;
      if (meshToPart.has(hitObj)) {
        foundPart = meshToPart.get(hitObj);
      } else {
        let obj = hitObj;
        while (obj && obj !== currentModel && !foundPart) {
          if (obj.name && meshNameToPart.has(obj.name.toLowerCase())) {
            foundPart = meshNameToPart.get(obj.name.toLowerCase());
          }
          obj = obj.parent;
        }
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

const modelSelect = document.getElementById('mv-model-select');
if (modelSelect) {
  modelSelect.addEventListener('change', () => {
    const opt = modelSelect.selectedOptions[0];
    const url = opt ? opt.dataset.url : null;
    if (url) {
      loadModel(url).then(() => {
        playIntro();
      });
    }
  });
}

loadModel(CFG.modelUrl).then(() => {
  const requestedPart = partFromUrl();
  if (requestedPart) selectPart(requestedPart);
  else playIntro();
});
