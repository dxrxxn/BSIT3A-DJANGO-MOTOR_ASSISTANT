'use strict';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader }    from 'three/addons/loaders/GLTFLoader.js';
import { OBJLoader }     from 'three/addons/loaders/OBJLoader.js';
import { STLLoader }     from 'three/addons/loaders/STLLoader.js';

// URLs injected by Django template
const S = window.STUDIO;

let uploadId = null, filename = null, currentJob = null;
let models = {}, activeModel = 'repaired';

/* DOM */
const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const previewWrap  = document.getElementById('preview-wrap');
const previewImg   = document.getElementById('preview-img');
const btnChange    = document.getElementById('btn-change-image');
const btnStart     = document.getElementById('btn-start');
const progressCard = document.getElementById('progress-card');
const progressBar  = document.getElementById('progress-bar');
const progressLog  = document.getElementById('progress-log');
const viewerWrap   = document.getElementById('viewer-wrap');
const viewerPH     = document.getElementById('viewer-placeholder');
const viewerCanvas = document.getElementById('viewer-canvas');
const viewerStats  = document.getElementById('viewer-stats');
const viewerTB     = document.getElementById('viewer-toolbar');
const viewerTabs   = document.getElementById('viewer-tabs');
const statFaces    = document.getElementById('stat-faces');
const statVerts    = document.getElementById('stat-verts');
const validCard    = document.getElementById('validation-card');
const validOverall = document.getElementById('validation-overall');
const validChecks  = document.getElementById('validation-checks');
const validDims    = document.getElementById('validation-dims');
const dlCard       = document.getElementById('downloads-card');
const dlButtons    = document.getElementById('download-buttons');
const historyList  = document.getElementById('history-list');

/* THREE.JS */
let renderer, scene, camera, controls, currentMesh, shade = 'clay';
const savedMaterials = new Map();

function initThree() {
  renderer = new THREE.WebGLRenderer({ canvas: viewerCanvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.1;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x0a0a10);
  const grid = new THREE.GridHelper(20, 40, 0x1a1a24, 0x141420);
  grid.position.y = -2; grid.material.opacity = 0.5; grid.material.transparent = true; scene.add(grid);
  scene.add(new THREE.AmbientLight(0xffffff, 0.5));
  const key = new THREE.DirectionalLight(0xfff8f0, 3.2); key.position.set(4,8,5); key.castShadow = true;
  key.shadow.mapSize.set(2048,2048); key.shadow.bias = -0.0004; scene.add(key);
  const fill = new THREE.DirectionalLight(0x8899cc, 0.9); fill.position.set(-5,2,-4); scene.add(fill);
  const rim  = new THREE.DirectionalLight(0xffd090, 0.6); rim.position.set(1,-2,-6);  scene.add(rim);
  camera = new THREE.PerspectiveCamera(40, 1, 0.01, 300); camera.position.set(0, 1.5, 6);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.06; controls.maxDistance = 80; controls.autoRotateSpeed = 1.2;
  fitCanvas();
  new ResizeObserver(fitCanvas).observe(viewerWrap);
  (function loop(){ requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
}
function fitCanvas() {
  const w = viewerWrap.clientWidth||800, h = viewerWrap.clientHeight||520;
  renderer.setSize(w,h); camera.aspect = w/h; camera.updateProjectionMatrix();
}
function buildMatcap() {
  const sz=256, c=document.createElement('canvas'); c.width=c.height=sz;
  const ctx=c.getContext('2d');
  ctx.fillStyle='#18181c'; ctx.fillRect(0,0,sz,sz);
  const g1=ctx.createRadialGradient(sz*.37,sz*.31,0,sz*.5,sz*.5,sz*.65);
  g1.addColorStop(0,'rgba(218,215,208,1)'); g1.addColorStop(.35,'rgba(155,152,148,1)');
  g1.addColorStop(.7,'rgba(90,88,86,1)'); g1.addColorStop(1,'rgba(16,16,18,1)');
  ctx.fillStyle=g1; ctx.beginPath(); ctx.arc(sz/2,sz/2,sz/2,0,Math.PI*2); ctx.fill();
  const g2=ctx.createRadialGradient(sz*.32,sz*.27,0,sz*.34,sz*.29,sz*.14);
  g2.addColorStop(0,'rgba(255,255,252,.9)'); g2.addColorStop(1,'rgba(0,0,0,0)');
  ctx.fillStyle=g2; ctx.beginPath(); ctx.arc(sz/2,sz/2,sz/2,0,Math.PI*2); ctx.fill();
  const tex=new THREE.CanvasTexture(c); tex.colorSpace=THREE.SRGBColorSpace; return tex;
}
const MATCAP = buildMatcap();

function setShade(mode) {
  shade = mode;
  ['clay','tex','wire'].forEach(m =>
    document.getElementById(`btn-shade-${m}`)?.classList.toggle('active', m===mode||
      (m==='tex'&&mode==='texture')||(m==='wire'&&mode==='wireframe')));
  if (!currentMesh) return;
  currentMesh.traverse(c => {
    if (!c.isMesh) return;
    const orig = savedMaterials.get(c);
    if (mode==='clay') c.material = new THREE.MeshMatcapMaterial({ matcap: MATCAP });
    else if (mode==='wireframe') c.material = new THREE.MeshBasicMaterial({ color:0x6366f1, wireframe:true });
    else if (orig) c.material = Array.isArray(orig)?orig.map(m=>m.clone()):orig.clone();
  });
}

function loadModel(url) {
  return new Promise((resolve, reject) => {
    const ext = url.split('.').pop().toLowerCase();
    const onLoad = object => {
      if (currentMesh) scene.remove(currentMesh);
      let mesh = object;
      if (!(object.isScene||object.isObject3D)) {
        mesh = new THREE.Mesh(object, new THREE.MeshMatcapMaterial({ matcap: MATCAP }));
      }
      const box=new THREE.Box3().setFromObject(mesh);
      const sz=new THREE.Vector3(); box.getSize(sz);
      const sc=3/Math.max(sz.x,sz.y,sz.z); mesh.scale.setScalar(sc);
      const ctr=new THREE.Vector3(); box.getCenter(ctr); mesh.position.sub(ctr.multiplyScalar(sc));
      let f=0,v=0; savedMaterials.clear();
      mesh.traverse(c => {
        if (!c.isMesh) return;
        c.castShadow=c.receiveShadow=true;
        savedMaterials.set(c, Array.isArray(c.material)?c.material.map(m=>m.clone()):c.material.clone());
        const g=c.geometry;
        f+=g.index?g.index.count/3:(g.attributes.position?.count||0)/3;
        v+=g.attributes.position?.count||0;
      });
      scene.add(mesh); currentMesh=mesh; setShade(shade);
      statFaces.textContent=Math.round(f).toLocaleString()+' faces';
      statVerts.textContent=v.toLocaleString()+' verts';
      const box2=new THREE.Box3().setFromObject(mesh);
      const ctr2=new THREE.Vector3(); box2.getCenter(ctr2);
      const sz2=new THREE.Vector3(); box2.getSize(sz2);
      const d=Math.max(sz2.x,sz2.y,sz2.z)*2.5;
      camera.position.set(ctr2.x+d*.3,ctr2.y+sz2.y*.3,ctr2.z+d);
      controls.target.copy(ctr2); controls.update();
      viewerPH.style.display='none'; viewerCanvas.style.display='block';
      viewerStats.classList.remove('d-none'); viewerTB.style.display='flex';
      resolve();
    };
    if (ext==='glb'||ext==='gltf') new GLTFLoader().load(url,g=>onLoad(g.scene),undefined,reject);
    else if (ext==='obj') new OBJLoader().load(url,onLoad,undefined,reject);
    else if (ext==='stl') new STLLoader().load(url,onLoad,undefined,reject);
    else reject(new Error('Unsupported format: '+ext));
  });
}

/* UPLOAD */
function handleFile(file) {
  if (!file) return;
  if (!['image/jpeg','image/png','image/webp'].includes(file.type)) {
    alert('Unsupported type. Use JPG, PNG, or WebP.'); return;
  }
  const reader = new FileReader();
  reader.onload = e => { previewImg.src=e.target.result; dropZone.style.display='none'; previewWrap.classList.remove('d-none'); };
  reader.readAsDataURL(file);

  const fd = new FormData(); fd.append('file', file);
  fetch(S.uploadUrl, {
    method:'POST',
    headers:{'X-CSRFToken': S.csrfToken},
    body: fd,
  }).then(r=>r.json()).then(d => {
    if (d.error) { alert('Upload error: '+d.error); return; }
    uploadId=d.upload_id; filename=d.filename; btnStart.disabled=false;
  }).catch(e=>alert('Upload failed: '+e.message));
}
dropZone.addEventListener('click', ()=>fileInput.click());
fileInput.addEventListener('change', e=>handleFile(e.target.files[0]));
dropZone.addEventListener('dragover', e=>{e.preventDefault();dropZone.classList.add('drag-over');});
dropZone.addEventListener('dragleave', ()=>dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e=>{e.preventDefault();dropZone.classList.remove('drag-over');handleFile(e.dataTransfer.files[0]);});
btnChange.addEventListener('click', ()=>{
  uploadId=null;filename=null;btnStart.disabled=true;
  previewWrap.classList.add('d-none');dropZone.style.display='';
});

/* START JOB */
btnStart.addEventListener('click', async ()=>{
  if (!uploadId) return;
  const fmts=[...document.querySelectorAll('input[name="fmt"]:checked')].map(c=>c.value);
  const body={
    upload_id:uploadId, filename, device:document.getElementById('sel-device').value,
    unit:document.getElementById('sel-unit').value,
    size_x:parseFloat(document.getElementById('dim-x').value)||null,
    size_y:parseFloat(document.getElementById('dim-y').value)||null,
    size_z:parseFloat(document.getElementById('dim-z').value)||null,
    exports:fmts,
  };
  btnStart.disabled=true;
  progressCard.style.display='block';
  progressBar.style.width='0%';
  if(progressLog) progressLog.textContent='';
  validCard.style.display='none'; dlCard.style.display='none';
  viewerTabs.style.display='none'; models={};

  const resp=await fetch(S.startJobUrl,{
    method:'POST',
    headers:{'Content-Type':'application/json','X-CSRFToken':S.csrfToken},
    body:JSON.stringify(body),
  }).then(r=>r.json()).catch(e=>({error:e.message}));

  if (resp.error){alert('Start failed: '+resp.error);btnStart.disabled=false;return;}
  currentJob=resp.job_id;
  startSSE(currentJob);
  loadHistory();
});

/* SSE */
function startSSE(jobId) {
  const src = new EventSource(`${S.streamJobUrl}${jobId}/stream/`);
  src.onmessage = async e => {
    const d=JSON.parse(e.data);
    if (d.msg && progressLog) { progressLog.textContent+=d.msg+'\n'; progressLog.scrollTop=progressLog.scrollHeight; }
    if (d.pct>=0) progressBar.style.width=d.pct+'%';
    if (d.done) { src.close(); await pollJob(jobId); btnStart.disabled=false; loadHistory(); }
  };
  src.onerror=()=>src.close();
}

async function pollJob(jobId) {
  const job=await fetch(`${S.pollJobUrl}${jobId}/`).then(r=>r.json());
  if (job.validation) renderValidation(job.validation);
  if (job.exports&&Object.keys(job.exports).length) renderDownloads(jobId,job.exports);
  const url=job.repaired_url||job.original_url;
  if (url){
    models.repaired=job.repaired_url; models.original=job.original_url;
    if (models.repaired&&models.original&&models.repaired!==models.original) viewerTabs.style.display='flex';
    await loadModel(url).catch(e=>console.error('Viewer:',e));
  }
}

/* VIEWER TOOLBAR */
document.getElementById('btn-shade-clay')?.addEventListener('click',()=>setShade('clay'));
document.getElementById('btn-shade-tex')?.addEventListener('click',()=>setShade('texture'));
document.getElementById('btn-shade-wire')?.addEventListener('click',()=>setShade('wireframe'));
document.getElementById('btn-spin')?.addEventListener('click',e=>{
  controls.autoRotate=!controls.autoRotate; e.currentTarget.classList.toggle('active',controls.autoRotate);
});
document.getElementById('btn-reset-cam')?.addEventListener('click',()=>{
  if(!currentMesh)return;
  const box=new THREE.Box3().setFromObject(currentMesh);
  const ctr=new THREE.Vector3();box.getCenter(ctr);
  const sz=new THREE.Vector3();box.getSize(sz);
  const d=Math.max(sz.x,sz.y,sz.z)*2.5;
  camera.position.set(ctr.x+d*.3,ctr.y+sz.y*.3,ctr.z+d);
  controls.target.copy(ctr);controls.update();
});
document.getElementById('btn-fullscreen')?.addEventListener('click',()=>{
  if(!document.fullscreenElement) viewerWrap.requestFullscreen().catch(()=>{});
  else document.exitFullscreen();
  setTimeout(fitCanvas,120);
});
document.querySelectorAll('.vtab').forEach(btn=>btn.addEventListener('click',async()=>{
  activeModel=btn.dataset.model;
  document.querySelectorAll('.vtab').forEach(b=>b.classList.toggle('active',b===btn));
  const url=models[activeModel];
  if(url) await loadModel(url).catch(e=>console.error(e));
}));

/* VALIDATION */
function renderValidation(v) {
  validCard.style.display='';
  validOverall.className=`overall-badge overall-${v.overall}`;
  validOverall.textContent=v.overall==='PASS'?'✓ PASS — Looks printable':v.overall==='WARN'?'⚠ WARNING — Review before printing':'✗ FAIL — Not print-ready';
  validChecks.innerHTML='';
  for (const check of (v.checks||[])) {
    const row=document.createElement('div'); row.className='check-item';
    row.innerHTML=`<span class="check-dot dot-${check.result}"></span><span class="check-name">${check.name}</span><span class="check-detail">${check.detail}</span>`;
    validChecks.appendChild(row);
  }
  let dims='';
  if(v.bounding_box_mm) dims+=`Bounding box: ${v.bounding_box_mm.map(x=>x.toFixed(1)).join(' × ')} mm<br>`;
  if(v.volume_mm3!=null) dims+=`Volume: ${(v.volume_mm3/1000).toFixed(2)} cm³<br>`;
  if(v.min_wall_thickness_mm!=null) dims+=`Est. min wall: ${v.min_wall_thickness_mm.toFixed(2)} mm`;
  validDims.innerHTML=dims;
}

/* DOWNLOADS */
function renderDownloads(jobId, exports) {
  dlCard.style.display='';
  dlButtons.innerHTML='';
  const icons={stl:'file-code',obj:'file-alt',ply:'file',glb:'cube'};
  const notes={stl:'No texture/color.',obj:'Geometry+UVs.',ply:'Point data.',glb:'Full textured.'};
  for(const [fmt] of Object.entries(exports)){
    const a=document.createElement('a');
    a.href=`${S.downloadUrl}${jobId}/download/${fmt}/`;
    a.className='btn btn-dl mb-1 d-block';
    a.download='';
    a.innerHTML=`<i class="fas fa-${icons[fmt]||'file'}"></i> Download ${fmt.toUpperCase()} <small>${notes[fmt]||''}</small>`;
    dlButtons.appendChild(a);
  }
}

/* HISTORY */
async function loadHistory(){
  const data=await fetch(S.historyUrl).then(r=>r.json()).catch(()=>({jobs:[]}));
  const jobs=data.jobs||[];
  if(!jobs.length){historyList.innerHTML='<p class="text-muted small">No jobs yet.</p>';return;}
  historyList.innerHTML='';
  [...jobs].reverse().slice(0,15).forEach(j=>{
    const item=document.createElement('div');
    item.className='d-flex justify-content-between small py-1 border-bottom';
    item.innerHTML=`<span class="text-truncate me-2">${j.filename||j.job_id}</span><span class="text-${j.status==='completed'?'success':j.status==='failed'?'danger':'warning'}">${j.status}</span>`;
    historyList.appendChild(item);
  });
}
document.getElementById('btn-clear-history')?.addEventListener('click',async()=>{
  await fetch(S.historyUrl,{method:'DELETE',headers:{'X-CSRFToken':S.csrfToken}});
  loadHistory();
});

/* BOOT */
initThree();
loadHistory();
