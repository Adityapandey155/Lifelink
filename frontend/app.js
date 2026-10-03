// ---------------- Global state ----------------
const state = { token: localStorage.getItem("ll_token") || null, user: null, ws: null, notifications: [] };
const BLOOD_GROUPS = ["A+","A-","B+","B-","AB+","AB-","O+","O-"];

// ---------------- API helper ----------------
async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data = null;
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error((data && (data.detail || JSON.stringify(data))) || "Request failed");
  return data;
}

function toast(msg, type = "info") {
  const root = document.getElementById("toast-root");
  const div = document.createElement("div");
  div.className = `toast ${type}`;
  const icon = type === "error" ? "⚠️" : type === "success" ? "✅" : "🔔";
  div.innerHTML = `<div class="flex gap-2 items-start"><span>${icon}</span><span>${msg}</span></div>`;
  root.appendChild(div);
  setTimeout(() => { div.style.opacity = "0"; div.style.transform = "translateX(120%)"; div.style.transition = "all .3s"; setTimeout(() => div.remove(), 300); }, 4200);
}

function priorityBadge(p) {
  const cls = p === "CRITICAL" ? "badge-critical" : p === "URGENT" ? "badge-urgent" : "badge-normal";
  return `<span class="badge ${cls}"><span class="badge-dot"></span>${p}</span>`;
}

// ---------------- Modal ----------------
function openModal(html) {
  document.getElementById("modal-root").innerHTML = `
    <div class="modal-overlay" id="modal-overlay"><div class="modal-box">${html}</div></div>`;
  document.getElementById("modal-overlay").addEventListener("click", (e) => { if (e.target.id === "modal-overlay") closeModal(); });
}
function closeModal() { document.getElementById("modal-root").innerHTML = ""; }

// ---------------- WebSocket ----------------
function connectWS() {
  if (!state.token) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  state.ws = new WebSocket(`${proto}://${location.host}/ws?token=${state.token}`);
  state.ws.onmessage = (evt) => handleWSEvent(JSON.parse(evt.data));
  state.ws.onclose = () => setTimeout(connectWS, 3000);
}

function handleWSEvent(data) {
  if (data.type === "new_request") {
    notifyBrowser("🚨 LifeLink Emergency", `${data.units_required} unit(s) of ${data.blood_group} blood needed ~${data.distance_km} km away. Priority: ${data.priority}`);
    toast(`New ${data.priority} request: <b>${data.units_required} unit(s) of ${data.blood_group}</b> needed ~${data.distance_km}km away
      <div style="margin-top:8px"><button onclick="location.hash='#/request/${data.request_id}'" class="btn btn-primary btn-sm">Respond →</button></div>`, "error");
  } else if (data.type === "donation_response") {
    toast(`A donor responded! (${data.donor_blood_group}, ~${data.distance_km}km)`, "success");
    notifyBrowser("LifeLink", "A compatible donor responded to your request!");
  } else if (data.type === "matches_updated") { toast("Request status updated", "info"); }
  else if (data.type === "escalation") { toast("⚠️ " + data.message, "error"); }
  else if (data.type === "response_confirmed") { toast(data.message, "success"); }
  else if (data.type === "response_status_update") { toast("Your donation status changed to: " + data.status, "info"); }
  if (location.hash.startsWith("#/dashboard") || location.hash.startsWith("#/request/")) render();
}

function notifyBrowser(title, body) {
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") new Notification(title, { body });
  else if (Notification.permission !== "denied") Notification.requestPermission().then((p) => { if (p === "granted") new Notification(title, { body }); });
}

// ---------------- Geolocation ----------------
function getLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject("Geolocation not supported");
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      (err) => reject(err.message)
    );
  });
}

// ---------------- Animated counters ----------------
function animateCounter(el, target, duration = 1200) {
  const start = 0; const startTime = performance.now();
  function tick(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.floor(start + (target - start) * eased).toLocaleString();
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

// ---------------- Nav ----------------
function renderNav() {
  const nav = document.getElementById("nav");
  if (!state.user) {
    nav.innerHTML = `
    <nav class="nav-glass"><div class="nav-inner">
      <a href="#/" class="logo"><span class="drop"></span> LifeLink</a>
      <div class="nav-links">
        <a href="#/login" class="nav-link">Login</a>
        <a href="#/register" class="btn btn-primary btn-sm">Register</a>
      </div>
    </div></nav>`;
    return;
  }
  const unread = state.notifications.filter(n => !n.read).length;
  nav.innerHTML = `
  <nav class="nav-glass"><div class="nav-inner">
    <a href="#/" class="logo"><span class="drop"></span> LifeLink</a>
    <div class="nav-links">
      <a href="#/dashboard" class="nav-link">Dashboard</a>
      <a href="#/requests" class="nav-link">Find Blood</a>
      <a href="#/create-request" class="nav-link">Emergency Blood Need</a>
      <a href="#/my-requests" class="nav-link">My Requests</a>
      <a href="#/my-donations" class="nav-link">My Donations</a>
      <a href="#/notifications" class="nav-link">Notifications${unread ? `<span class="nav-badge">${unread}</span>` : ""}</a>
      <a href="#/profile" class="nav-link">Profile</a>
      ${state.user.role === "admin" ? `<a href="#/admin" class="nav-link" style="color:#ff5c7a">Admin</a>` : ""}
      <button onclick="logout()" class="btn btn-outline btn-sm">Logout</button>
    </div>
  </div></nav>`;
}

function logout() { state.token = null; state.user = null; localStorage.removeItem("ll_token"); if (state.ws) state.ws.close(); location.hash = "#/"; }

// ---------------- Pages ----------------
async function pageLanding() {
  let stats = { active_donors: 0, emergency_requests: 0, requests_fulfilled: 0 };
  try { stats = await api("/api/public/stats"); } catch (e) {}
  setTimeout(() => {
    document.querySelectorAll("[data-count]").forEach(el => animateCounter(el, parseInt(el.dataset.count)));
  }, 100);
  return `
  <div class="hero">
    <h1 class="hero-title">Find Blood.<br/>Find Help. Faster.</h1>
    <p class="hero-sub">LifeLink connects verified emergency blood requests with nearby compatible voluntary donors in real time. It helps hospitals and patients find <b>potential</b> nearby donors faster — it does not guarantee blood availability and never replaces hospitals or blood banks.</p>
    <div class="hero-actions">
      <a href="#/requests" class="btn btn-primary">🩸 FIND BLOOD</a>
      <a href="#/register" class="btn btn-outline">BECOME A DONOR</a>
    </div>
    <div class="hero-stats">
      <div><div class="hero-stat-num" data-count="${stats.active_donors}">0</div><div class="hero-stat-label">Active Donors</div></div>
      <div><div class="hero-stat-num" data-count="${stats.emergency_requests}">0</div><div class="hero-stat-label">Emergency Requests</div></div>
      <div><div class="hero-stat-num" data-count="${stats.requests_fulfilled}">0</div><div class="hero-stat-label">Requests Fulfilled</div></div>
    </div>
    ${stats.includes_demo_data ? `<p class="faint text-xs mt-6">Some statistics include clearly labeled <span class="demo-tag">DEMO DATA</span> for demonstration purposes.</p>` : ""}
  </div>`;
}

function pageRegister() {
  const options = BLOOD_GROUPS.map(b => `<option value="${b}">${b}</option>`).join("");
  return `
  <div class="max-w-md mx-auto glass-card p-8 mt-10">
    <h2 class="section-title">Create your LifeLink account</h2>
    <p class="faint text-xs mb-4">You can register as a donor, or create a personal account to request emergency blood when needed. You're never limited — a registered donor can also request blood for themselves or family.</p>
    <form id="register-form" class="space-y-3">
      <input required name="name" placeholder="Full Name" class="field" />
      <input required type="email" name="email" placeholder="Email" class="field" />
      <input required name="phone" placeholder="Phone Number" class="field" />
      <input required type="password" name="password" placeholder="Password (min 6 chars)" class="field" />
      <input type="date" name="dob" class="field" />
      <input name="city" placeholder="City" class="field" />

      <div class="glass-card p-4">
        <label class="flex items-center gap-2 text-sm font-semibold cursor-pointer">
          <input type="checkbox" id="chk-donor" name="register_as_donor" /> 🩸 Register as a Donor
        </label>
        <div id="donor-fields" class="mt-3 space-y-2" style="display:none">
          <select id="donor-blood-group" name="blood_group" class="field">
            <option value="">Your Blood Group</option>${options}
          </select>
          <p class="faint text-xs">You can toggle "Ready to Donate" any time after registering.</p>
        </div>
      </div>

      <label class="flex items-center gap-2 text-sm muted"><input type="checkbox" name="consent_notifications" checked /> I consent to receive emergency notifications</label>
      <button class="btn btn-primary w-full">Register</button>
    </form>
    <p class="text-sm mt-4 muted">Already have an account? <a href="#/login" class="link-red">Login</a></p>
  </div>`;
}

function wireRegisterEvents() {
  const chkDonor = document.getElementById("chk-donor");
  const donorFields = document.getElementById("donor-fields");
  const bloodSelect = document.getElementById("donor-blood-group");
  if (chkDonor) {
    chkDonor.onchange = () => {
      donorFields.style.display = chkDonor.checked ? "block" : "none";
      bloodSelect.required = chkDonor.checked;
    };
  }
}

function pageLogin() {
  return `
  <div class="max-w-md mx-auto glass-card p-8 mt-10">
    <h2 class="section-title">Login to LifeLink</h2>
    <form id="login-form" class="space-y-3">
      <input required type="email" name="email" placeholder="Email" class="field" />
      <input required type="password" name="password" placeholder="Password" class="field" />
      <button class="btn btn-primary w-full">Login</button>
    </form>
    <p class="text-sm mt-4 muted">New here? <a href="#/register" class="link-red">Register</a></p>
    <p class="faint text-xs mt-4">Admin demo login: admin@lifelink.local / admin123</p>
  </div>`;
}

async function pageDashboard() {
  const d = await api("/api/users/me/dashboard");

  const topActions = `
    <div class="flex flex-wrap gap-3 mb-6">
      <a href="#/requests" class="btn btn-outline">🔍 FIND BLOOD</a>
      <a href="#/create-request" class="btn btn-primary">🚨 EMERGENCY BLOOD NEED</a>
    </div>`;

  let donorBlock;
  if (d.is_donor) {
    donorBlock = `
    <div class="glass-card p-6 mb-6">
      <h3 class="font-bold mb-4">My Donor Status</h3>
      <div class="flex items-center gap-4 flex-wrap">
        <button id="avail-toggle" class="avail-toggle ${d.is_available ? "avail-on" : "avail-off"}">
          ${d.is_available ? `<span class="pulse-ring"></span> READY TO DONATE` : "⚪ NOT AVAILABLE"}
        </button>
        <select id="avail-duration" class="field" style="width:auto">
          <option value="now">Available now</option>
          <option value="1h">Available for 1 hour</option>
          <option value="3h">Available for 3 hours</option>
          <option value="today">Available for today</option>
        </select>
        <button id="enable-location" class="link-red text-sm">📍 Enable / Update Location</button>
      </div>
      <p class="faint text-xs mt-3">Donation eligibility must be confirmed by qualified medical professionals. LifeLink does not determine medical eligibility.</p>
    </div>`;
  } else {
    donorBlock = `
    <div class="glass-card p-6 mb-6 text-center">
      <h3 class="font-bold mb-2">You're not registered as a donor yet</h3>
      <p class="muted text-sm mb-4">Register as a donor so LifeLink can match you with nearby compatible emergency requests.</p>
      <button onclick="becomeDonorPrompt()" class="btn btn-primary">🩸 BECOME A DONOR</button>
    </div>`;
  }

  const cards = d.nearby_requests.map(r => {
    const actionBtn = d.is_available
      ? `<button onclick="donateNowFlow(${r.id})" class="btn btn-primary btn-sm">DONATE NOW</button>`
      : `<button onclick="becomeAvailableAndDonate(${r.id})" class="btn btn-primary btn-sm">I'M AVAILABLE TO HELP</button>`;
    return `
    <div class="request-card ${r.priority.toLowerCase()}">
      <div class="flex justify-between items-center mb-2">
        <span class="font-bold text-lg">${r.blood_group} BLOOD REQUIRED</span>${priorityBadge(r.priority)}
      </div>
      <div class="muted text-sm">~${r.distance_km ?? "?"} km away • ${r.units_required} unit(s) • ${r.hospital_name}</div>
      <div class="mt-3 flex gap-2">
        <a href="#/request/${r.id}" class="btn btn-outline btn-sm">VIEW REQUEST</a>
        ${actionBtn}
      </div>
    </div>`;
  }).join("");

  const nearbySection = d.is_donor ? `
    <h3 class="section-title">Nearby Emergency Requests</h3>
    <div class="grid md:grid-cols-2 gap-4">${cards || `<p class="muted">No nearby compatible requests right now.</p>`}</div>
  ` : `
    <div class="glass-card p-6 text-center">
      <p class="muted text-sm">Register as a donor to see compatible nearby emergency requests here.</p>
    </div>`;

  return `
  <div class="mt-6">
    <h1 class="text-2xl font-bold mb-1">Welcome, ${d.name}</h1>
    <p class="muted mb-4 text-sm">LifeLink helps you find potential nearby donation opportunities faster, and lets you raise an emergency blood need for yourself or family. It does not replace hospital medical decisions.</p>
    ${topActions}

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="stat-card"><div class="stat-label">Blood Group</div><div class="stat-value" style="color:#ff5c7a">${d.blood_group || "—"}</div></div>
      <div class="stat-card"><div class="stat-label">Donor Status</div><div class="stat-value" style="font-size:1rem;color:${d.is_donor ? '#4ade80' : '#9295a3'}">${d.is_donor ? "REGISTERED" : "NOT REGISTERED"}</div></div>
      <div class="stat-card"><div class="stat-label">Nearby Requests</div><div class="stat-value">${d.nearby_requests_count}</div></div>
      <div class="stat-card"><div class="stat-label">Compatible</div><div class="stat-value">${d.compatible_requests_count}</div></div>
      <div class="stat-card"><div class="stat-label">Others Responding</div><div class="stat-value">${d.people_currently_responding}</div></div>
      <div class="stat-card"><div class="stat-label">Your Active Responses</div><div class="stat-value">${d.your_active_responses}</div></div>
    </div>

    ${donorBlock}
    ${nearbySection}
  </div>`;
}

function wireDashboardEvents() {
  const toggle = document.getElementById("avail-toggle");
  if (toggle) {
    toggle.onclick = async () => {
      const isCurrentlyReady = toggle.classList.contains("avail-on");
      try {
        if (!isCurrentlyReady) {
          try { const loc = await getLocation(); await api("/api/users/me/location", { method: "PATCH", body: loc }); }
          catch (e) { toast("Location permission needed to go online: " + e, "error"); return; }
        }
        const duration = document.getElementById("avail-duration").value;
        await api("/api/users/me/availability", { method: "PATCH", body: { is_available: !isCurrentlyReady, duration } });
        await loadMe();                              // ✅ NEW — keep state.user fresh
        toast(!isCurrentlyReady ? "Ready to Donate: YES" : "Ready to Donate: NO", "success");
        render();
      } catch (e) { toast(e.message, "error"); }
    };
  }
  const locBtn = document.getElementById("enable-location");
  if (locBtn) locBtn.onclick = async () => {
    try { const loc = await getLocation(); await api("/api/users/me/location", { method: "PATCH", body: loc }); toast("Location updated", "success"); }
    catch (e) { toast("Could not get location: " + e, "error"); }
  };
}

async function donateNowFlow(requestId) {
  openModal(`
    <h3 class="text-xl font-bold mb-3">🚨 Respond to Emergency Request</h3>
    <p class="mb-3 text-sm muted">You are responding to an emergency blood request. By confirming, your contact information will be shared directly with the person who created this request.</p>
    <p class="font-semibold mb-2 text-sm">Information to be shared:</p>
    <ul class="text-sm mb-4 space-y-1 muted">
      <li>✓ Full Name</li>
      <li>✓ Phone number</li>
      <li>✓ Blood group</li>
      <li>✓ Approximate distance</li>
    </ul>
    <p class="faint text-xs mb-5">Donation eligibility must be confirmed by medical professionals at the point of donation. LifeLink does not make medical decisions.</p>
    <div class="flex justify-end gap-3">
      <button onclick="closeModal()" class="btn btn-outline btn-sm">CANCEL</button>
      <button id="confirm-donate-btn" class="btn btn-primary btn-sm">CONFIRM & DONATE</button>
    </div>
  `);
  document.getElementById("confirm-donate-btn").onclick = async () => {
    try {
      await api(`/api/requests/${requestId}/donate`, { method: "POST", body: { confirm: true } });
      toast("Thank you! Your info has been shared with the requester.", "success");
      closeModal(); render();
    } catch (e) { toast(e.message, "error"); }
  };
}

function becomeDonorPrompt() {
  const options = BLOOD_GROUPS.map(b => `<option value="${b}">${b}</option>`).join("");
  openModal(`
    <h3 class="text-xl font-bold mb-3">🩸 Become a Donor</h3>
    <p class="muted text-sm mb-4">Registering as a donor lets LifeLink match you with nearby compatible emergency requests. You can still create emergency requests for yourself or family regardless.</p>
    <form id="become-donor-form" class="space-y-3">
      <select required name="blood_group" class="field"><option value="">Your Blood Group</option>${options}</select>
      <input type="date" name="dob" class="field" />
      <div class="flex justify-end gap-3 mt-2">
        <button type="button" onclick="closeModal()" class="btn btn-outline btn-sm">CANCEL</button>
        <button class="btn btn-primary btn-sm">REGISTER AS DONOR</button>
      </div>
    </form>
  `);
  document.getElementById("become-donor-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    if (!body.dob) delete body.dob;
    try {
      await api("/api/users/me/become-donor", { method: "PATCH", body });
      await loadMe();
      toast("You're now a registered donor! 🩸", "success");
      closeModal();
      render();
    } catch (err) { toast(err.message, "error"); }
  };
}

async function becomeAvailableAndDonate(requestId) {
  try {
    let loc;
    try {
      loc = await getLocation();
      await api("/api/users/me/location", { method: "PATCH", body: loc });
    } catch (e) { toast("Location permission is required to help: " + e, "error"); return; }
    await api("/api/users/me/availability", { method: "PATCH", body: { is_available: true, duration: "3h" } });
    await loadMe();
    toast("You're marked available! Please confirm to donate.", "success");
    donateNowFlow(requestId);
  } catch (e) { toast(e.message, "error"); }
}

async function pageRequests() {
  const list = await api("/api/requests");
  const items = list.map(r => `
    <div class="request-card ${r.priority.toLowerCase()}">
      <div class="flex justify-between mb-1"><span class="font-bold">${r.blood_group} required</span>${priorityBadge(r.priority)}</div>
      <div class="muted text-sm">${r.hospital_name} ${r.is_verified_request ? '<span style="color:#4ade80">✓ Verified Hospital</span>' : '<span class="faint">(unverified source)</span>'}</div>
      <div class="faint text-sm">${r.distance_km !== null ? `~${r.distance_km} km away` : "distance unknown"} • ${r.units_required} unit(s) • status: ${r.status}</div>
      ${r.is_demo ? '<span class="demo-tag">DEMO DATA</span>' : ""}
      <div class="mt-2"><a href="#/request/${r.id}" class="link-red text-sm">View details →</a></div>
    </div>`).join("") || `<p class="muted">No active emergency requests right now.</p>`;
  return `<h1 class="text-2xl font-bold mb-4 mt-6">Emergency Requests</h1><div class="grid md:grid-cols-2 gap-4">${items}</div>`;
}


function statusBadge(status) {
  const colors = {
    OPEN: "#fbbf24", DONOR_RESPONDED: "#60a5fa", HOSPITAL_CONTACTED: "#a78bfa",
    DONOR_CONFIRMED: "#38bdf8", DONATION_IN_PROGRESS: "#f472b6",
    FULFILLED: "#4ade80", EXPIRED: "#9ca3af", CANCELLED: "#ff5c7a",
  };
  const color = colors[status] || "#9ca3af";
  return `<span style="background:${color}22;color:${color};padding:2px 10px;border-radius:9999px;font-size:11px;font-weight:700;border:1px solid ${color}55">${status.replace(/_/g, " ")}</span>`;
}

async function pageMyRequests() {
  const list = await api("/api/requests/mine");
  const items = list.map(r => `
    <div class="request-card ${r.priority.toLowerCase()}">
      <div class="flex justify-between items-center mb-1">
        <span class="font-bold">${r.blood_group} required</span>
        ${statusBadge(r.status)}
      </div>
      <div class="muted text-sm">${r.hospital_name || "—"}</div>
      <div class="faint text-sm">${r.units_required} unit(s) • Priority: ${r.priority} • Radius: ${r.search_radius_km ?? "?"} km</div>
      <div class="mt-2"><a href="#/request/${r.id}" class="link-red text-sm">View details →</a></div>
    </div>`).join("") || `<p class="muted">You haven't created any emergency requests yet.</p>`;
    
  return `<div class="flex justify-between items-center mb-4 mt-6">
      <h1 class="text-2xl font-bold">My Requests</h1>
      <div class="flex gap-2">
        <button onclick="clearAllMyRequests()" class="btn btn-outline btn-sm" style="color:#ff5c7a;border-color:#ff5c7a">🗑️ Clear All</button>
        <a href="#/create-request" class="btn btn-primary btn-sm">+ New Request</a>
      </div>
    </div>
    <div class="grid md:grid-cols-2 gap-4">${items}</div>`;
}

async function clearAllMyRequests() {
  if (!confirm("Are you sure you want to permanently delete ALL of your emergency requests and their responses? This cannot be undone.")) return;
  try {
    const res = await api("/api/requests/mine/clear", { method: "DELETE" });
    toast(`Deleted ${res.deleted} request(s).`, "success");
    render();
  } catch (e) {
    toast(e.message, "error");
  }
}

async function pageCreateRequest() {
  return `
  <div class="max-w-xl mx-auto glass-card p-8 mt-6">
    <h2 class="section-title mb-1">Create Emergency Blood Request</h2>
    <p class="faint text-xs mb-5">LifeLink coordinates potential donors — it is not a substitute for hospital or blood bank services. Please also contact your hospital/blood bank directly.</p>
    <form id="request-form" class="space-y-3">
      <select required name="blood_group" class="field">
        <option value="">Required Blood Group</option>${BLOOD_GROUPS.map(b => `<option value="${b}">${b}</option>`).join("")}
      </select>
      <input required type="number" min="1" max="20" name="units_required" placeholder="Number of units" class="field" />
      <select required name="priority" class="field">
        <option value="">Emergency Level</option>
        <option value="CRITICAL">🔴 Critical — immediately required</option>
        <option value="URGENT">🟠 Urgent — required soon</option>
        <option value="NORMAL">🟡 Normal — not immediately life-threatening</option>
      </select>
      <input required name="hospital_name" placeholder="Hospital Name" class="field" />
      <input required name="contact_person" placeholder="Contact Person" class="field" />
      <input required name="contact_phone" placeholder="Contact Phone" class="field" />
      <input type="datetime-local" name="required_by" class="field" />
      <textarea name="description" placeholder="Additional note" class="field"></textarea>
      <button type="button" id="use-location" class="link-red text-sm">📍 Use my current location for hospital location</button>
      <div id="loc-status" class="faint text-xs">📍 Detecting your location…</div>
      <button type="submit" id="submit-request-btn" class="btn btn-primary w-full" disabled style="opacity:0.5;cursor:not-allowed">CREATE EMERGENCY REQUEST</button>
    </form>
  </div>`;
}
let _pendingLoc = null;

function wireCreateRequestEvents() {
  const locStatus = document.getElementById("loc-status");
  const submitBtn = document.getElementById("submit-request-btn");

  function lockSubmit() {
    submitBtn.disabled = true;
    submitBtn.style.opacity = "0.5";
    submitBtn.style.cursor = "not-allowed";
  }
  function unlockSubmit() {
    submitBtn.disabled = false;
    submitBtn.style.opacity = "1";
    submitBtn.style.cursor = "pointer";
  }

  async function tryGetLocation() {
    locStatus.innerHTML = `<span style="color:#ffb84d">📍 Detecting your location…</span>`;
    lockSubmit();
    try {
      _pendingLoc = await getLocation();
      locStatus.innerHTML = `<span style="color:#4ade80">✅ Location set: ${_pendingLoc.latitude.toFixed(3)}, ${_pendingLoc.longitude.toFixed(3)}</span>`;
      unlockSubmit();
    } catch (e) {
      _pendingLoc = null;
      locStatus.innerHTML = `<span style="color:#ff5c7a">⚠️ Location access denied or unavailable. Click "Use my current location" and allow access in your browser — donor matching requires a real location, so a request cannot be submitted without it.</span>`;
      lockSubmit();
    }
  }

  // Auto-attempt the moment this page loads
  tryGetLocation();

  document.getElementById("use-location").onclick = tryGetLocation;

  document.getElementById("request-form").onsubmit = async (e) => {
    e.preventDefault();
    if (!_pendingLoc) {
      toast("Please allow location access before creating a request.", "error");
      return;
    }
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    body.units_required = parseInt(body.units_required);
    body.latitude = _pendingLoc.latitude;
    body.longitude = _pendingLoc.longitude;
    if (!body.required_by) delete body.required_by;
    try {
      const res = await api("/api/requests", { method: "POST", body });
      toast(`Request created! ${res.potential_donors} potential donor(s) found and notified.`, "success");
      location.hash = `#/request/${res.id}`;
    } catch (e2) { toast(e2.message, "error"); }
  };
}

async function pageRequestDetail(id) {
  const r = await api(`/api/requests/${id}`);
  let ownerBlock = "";
  if (r.is_owner) {
    const m = await api(`/api/requests/${id}/matches`);
    const responses = await api(`/api/requests/${id}/responses`);
    const respRows = responses.map(resp => `
      <tr><td>${resp.donor_name || "—"}</td><td>${resp.donor_phone || "—"}</td><td>${resp.blood_group}</td>
      <td>${resp.distance_km ?? "?"} km</td><td>${resp.status}</td><td>${renderResponseActions(resp)}</td></tr>`).join("");
    ownerBlock = `
      <div class="glass-card p-6 mt-6">
        <h3 class="font-bold mb-4">Request Coordination (Owner View)</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          <div class="chip"><div class="faint text-xs">Potential Donors Found</div><div class="text-xl font-bold">${m.potential_donors_found}</div></div>
          <div class="chip"><div class="faint text-xs">Available & Compatible</div><div class="text-xl font-bold">${m.available_compatible}</div></div>
          <div class="chip"><div class="faint text-xs">Responses</div><div class="text-xl font-bold">${m.responses_count}</div></div>
          <div class="chip"><div class="faint text-xs">Status</div><div class="text-sm font-bold" style="color:#ff5c7a">${m.status}</div></div>
        </div>
        <button onclick="expandRadius(${id})" class="link-red text-sm mb-4">Expand search radius</button>
        <p class="faint text-xs mb-3">Donor information is shown only for donors who explicitly responded and consented.</p>
        <table class="table-dark"><thead><tr><th>Name</th><th>Phone</th><th>Group</th><th>Dist</th><th>Status</th><th>Action</th></tr></thead>
        <tbody>${respRows || `<tr><td colspan="6" class="faint">No responses yet.</td></tr>`}</tbody></table>
      </div>`;
  }

  let donorAction = "";
  if (!r.is_owner) {
    if (r.compatible_for_me) {
      if (r.my_response_status) {
        donorAction = `<p style="color:#4ade80" class="font-semibold mt-5">You already responded (${r.my_response_status})</p>`;
      } else if (state.user.is_available) {
        donorAction = `<div class="mt-5"><button onclick="donateNowFlow(${r.id})" class="btn btn-primary">DONATE NOW</button></div>`;
      } else {
        donorAction = `<div class="mt-5"><button onclick="becomeAvailableAndDonate(${r.id})" class="btn btn-primary">I'M AVAILABLE TO HELP</button></div>`;
      }
    } else {
      donorAction = `<p class="faint text-sm mt-4">${state.user.is_donor ? "Your blood group is not compatible with this request." : "Register as a donor to help with compatible requests."}
        ${!state.user.is_donor ? `<button onclick="becomeDonorPrompt()" class="link-red" style="background:none;border:none;padding:0;cursor:pointer">Become a donor →</button>` : ""}</p>`;
    }
  }

  return `
  <div class="mt-6">
    <div class="glass-card p-6 request-card ${r.priority.toLowerCase()}">
      <div class="flex justify-between items-center flex-wrap gap-2">
        <h1 class="text-2xl font-bold">🚨 ${r.blood_group} Blood Required</h1>${priorityBadge(r.priority)}
      </div>
      <p class="muted mt-2">${r.hospital_name} ${r.is_verified_request ? '<span style="color:#4ade80;font-weight:600">✓ Verified Hospital</span>' : ""}</p>
      <p class="faint text-sm">${r.distance_km !== null ? `~${r.distance_km} km away` : ""} • ${r.units_required} unit(s) needed • Status: ${r.status}</p>
      ${r.description ? `<p class="mt-3 muted">${r.description}</p>` : ""}
      ${r.is_demo ? '<p class="demo-tag mt-2">DEMO DATA</p>' : ""}
      ${donorAction}
    </div>
    ${ownerBlock}
  </div>`;
}

function renderResponseActions(resp) {
  const next = { RESPONDED: "CONTACTED", CONTACTED: "CONFIRMED", CONFIRMED: "DONATING", DONATING: "FULFILLED" }[resp.status];
  if (!next) return "—";
  return `<button onclick="advanceResponse(${resp.id}, '${next}')" class="link-red text-xs">Mark ${next}</button>`;
}

async function advanceResponse(responseId, status) {
  try { await api(`/api/donations/${responseId}/status`, { method: "PATCH", body: { status } }); toast("Updated to " + status, "success"); render(); }
  catch (e) { toast(e.message, "error"); }
}

async function expandRadius(requestId) {
  try { const res = await api(`/api/requests/${requestId}/expand-radius`, { method: "POST" }); toast(`Radius expanded to ${res.search_radius_km}km, ${res.newly_notified} newly notified`, "success"); render(); }
  catch (e) { toast(e.message, "error"); }
}

async function pageMyDonations() {
  const list = await api("/api/donations/me");
  const rows = list.map(d => `
    <tr><td>${d.blood_group}</td><td>${d.hospital_name}</td><td>${priorityBadge(d.priority)}</td><td>${d.status}</td>
    <td><a href="#/request/${d.request_id}" class="link-red">View</a></td></tr>`).join("");
  return `<h1 class="text-2xl font-bold mb-4 mt-6">My Donation Responses</h1>
    <div class="glass-card p-4"><table class="table-dark"><thead><tr><th>Group</th><th>Hospital</th><th>Priority</th><th>Status</th><th></th></tr></thead>
    <tbody>${rows || `<tr><td colspan="5" class="faint">No donations yet.</td></tr>`}</tbody></table></div>`;
}

async function pageNotifications() {
  const list = await api("/api/notifications/me");
  state.notifications = list;
  const rows = list.map(n => {
    const canRespond = n.type === "emergency_request" && n.request_id;
    return `
    <div class="glass-card p-4 flex justify-between items-center gap-3 ${n.read ? "opacity-50" : ""}">
      <div class="flex-1">
        <div class="font-semibold text-sm">${n.type === "emergency_request" ? "🚨 Emergency Blood Need" : n.type}</div>
        <div class="text-sm muted">${n.message}</div>
      </div>
      <div class="flex flex-col gap-2 items-end">
        ${canRespond ? `<button onclick="location.hash='#/request/${n.request_id}'" class="btn btn-primary btn-sm">Respond →</button>` : ""}
        ${!n.read ? `<button onclick="markRead(${n.id})" class="link-red text-xs">Mark read</button>` : ""}
      </div>
    </div>`;
  }).join("");
  return `<div class="flex justify-between items-center mb-4 mt-6"><h1 class="text-2xl font-bold">Notifications</h1>
    <button onclick="markAllRead()" class="link-red text-sm">Mark all read</button></div>
    <div class="space-y-2">${rows || `<p class="muted">No notifications yet.</p>`}</div>`;
}

async function markRead(id) { await api(`/api/notifications/${id}/read`, { method: "PATCH" }); render(); }
async function markAllRead() { await api(`/api/notifications/read-all`, { method: "PATCH" }); render(); }

async function pageProfile() {
  const u = state.user;
  return `
  <div class="max-w-md mx-auto glass-card p-8 mt-6">
    <h2 class="section-title">My Profile</h2>
    <form id="profile-form" class="space-y-3">
      <input name="name" value="${u.name}" class="field" placeholder="Name" />
      <input name="phone" value="${u.phone}" class="field" placeholder="Phone" />
      <input name="city" value="${u.city || ""}" class="field" placeholder="City" />
      <label class="flex items-center gap-2 text-sm mt-2 muted cursor-pointer">
        <input type="checkbox" name="consent_notifications" ${u.consent_notifications ? "checked" : ""} /> 
        Receive emergency notifications
      </label>
      <div class="mt-4">
        <button class="btn btn-primary w-full">Save Changes</button>
      </div>
    </form>
  </div>`;
}

function wireProfileEvents() {
  const pf = document.getElementById("profile-form");
  if (pf) {
    pf.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      body.consent_notifications = fd.get("consent_notifications") === "on";
      try { await api("/api/users/me", { method: "PATCH", body }); toast("Profile updated", "success"); await loadMe(); render(); }
      catch (err) { toast(err.message, "error"); }
    };
  }
}

async function pageMap() {
  const list = await api("/api/requests");
  setTimeout(() => {
    const map = L.map("map").setView([20.5937, 78.9629], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: '© OpenStreetMap' }).addTo(map);
    list.forEach(r => {
      if (r.approx_latitude) {
        const marker = L.circleMarker([r.approx_latitude, r.approx_longitude], {
          radius: 10, color: r.priority === "CRITICAL" ? "#ef1744" : r.priority === "URGENT" ? "#f59e0b" : "#eab308",
          fillOpacity: 0.6,
        }).addTo(map);
        marker.bindPopup(`<b>${r.blood_group} needed</b><br/>${r.priority}<br/>📍 Approximate location only`);
      }
    });
    if (list.length) map.setView([list[0].approx_latitude, list[0].approx_longitude], 11);
  }, 50);
  return `<h1 class="text-2xl font-bold mb-4 mt-6">Emergency Request Map</h1>
    <p class="muted text-sm mb-3">For privacy, exact donor and requester locations are never shown. Markers represent approximate emergency areas only.</p>
    <div id="map" class="w-full h-[500px] rounded-2xl" style="border:1px solid var(--border)"></div>`;
}

// ---------------- Admin ----------------
async function pageAdmin() {
  const stats = await api("/api/admin/stats");
  const hospitals = await api("/api/admin/hospitals");
  const users = await api("/api/admin/users");
  const reqs = await api("/api/admin/requests");
  const reports = await api("/api/admin/reports");

  const statCard = (label, val) => `<div class="stat-card"><div class="stat-label">${label}</div><div class="stat-value">${val ?? "-"}</div></div>`;

  const hospitalRows = hospitals.map(h => `
    <tr><td>${h.name}</td><td>${h.verification_status}</td><td>${h.is_demo ? '<span class="demo-tag">DEMO</span>' : ""}</td>
    <td class="space-x-2">
      <button onclick="modHospital(${h.id},'approve')" class="link-red text-xs" style="color:#4ade80">Approve</button>
      <button onclick="modHospital(${h.id},'reject')" class="link-red text-xs">Reject</button>
      <button onclick="modHospital(${h.id},'suspend')" class="link-red text-xs" style="color:#9295a3">Suspend</button>
    </td></tr>`).join("");

  const userRows = users.map(u => `
    <tr><td>${u.name}</td><td>${u.blood_group}</td><td>${u.is_available ? "🟢" : "⚪"}</td>
    <td>${u.is_blocked ? "Blocked" : "Active"}</td><td>${u.is_demo ? '<span class="demo-tag">DEMO</span>' : ""}</td>
    <td><button onclick="toggleBlock(${u.id}, ${!u.is_blocked})" class="link-red text-xs">${u.is_blocked ? "Unblock" : "Block"}</button></td>
    </tr>`).join("");

  const reqRows = reqs.map(r => `
    <tr><td>${r.blood_group}</td><td>${priorityBadge(r.priority)}</td><td>${r.status}</td>
    <td>${r.is_verified_request ? "✓" : "—"}</td><td>${r.is_demo ? '<span class="demo-tag">DEMO</span>' : ""}</td>
    <td><button onclick="adminCancelReq(${r.id})" class="link-red text-xs">Cancel</button></td></tr>`).join("");

  const reportRows = reports.map(r => `
    <tr><td>${r.reason}</td><td>${r.status}</td>
    <td><button onclick="setReportStatus(${r.id},'ACTIONED')" class="link-red text-xs">Action</button>
    <button onclick="setReportStatus(${r.id},'DISMISSED')" class="link-red text-xs">Dismiss</button></td></tr>`).join("");

  return `
  <h1 class="text-2xl font-bold mb-4 mt-6">Admin Dashboard</h1>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
    ${statCard("Active Donors", stats.active_donors)}
    ${statCard("Requests Today", stats.emergency_requests_today)}
    ${statCard("Fulfilled", stats.requests_fulfilled)}
    ${statCard("Avg Response (min)", stats.average_response_time_minutes)}
    ${statCard("Active Critical", stats.active_critical_requests)}
    ${statCard("Verified Hospitals", stats.verified_hospitals)}
    ${statCard("Open Reports", stats.open_reports)}
    ${statCard("Total Users", stats.total_users)}
  </div>

  <div class="glass-card p-6 mb-6" style="border-color: rgba(234,179,8,0.3)">
    <h3 class="font-bold mb-2">🧪 DEMO MODE</h3>
    <p class="muted text-sm mb-4">Simulate the full emergency workflow without real users. All generated data is clearly labeled DEMO DATA.</p>
    <div class="flex gap-3 flex-wrap">
      <button onclick="seedDemo()" class="btn btn-ghost btn-sm">Seed Demo Donors</button>
      <button onclick="simulateDemo()" class="btn btn-primary btn-sm">Run Full Demo Scenario</button>
    </div>
    <pre id="demo-log" class="text-xs mt-4 p-4 rounded-lg" style="background:rgba(0,0,0,0.35); max-height:220px; overflow:auto; color:#c7c9d1"></pre>
  </div>

  <h3 class="section-title">Hospitals</h3>
  <div class="glass-card p-4 mb-6"><table class="table-dark"><tbody>${hospitalRows}</tbody></table></div>

  <h3 class="section-title">Users</h3>
  <div class="glass-card p-4 mb-6"><table class="table-dark"><tbody>${userRows}</tbody></table></div>

  <h3 class="section-title">Emergency Requests</h3>
  <div class="glass-card p-4 mb-6"><table class="table-dark"><tbody>${reqRows}</tbody></table></div>

  <h3 class="section-title">Reports</h3>
  <div class="glass-card p-4 mb-6"><table class="table-dark"><tbody>${reportRows || `<tr><td class="faint">No reports</td></tr>`}</tbody></table></div>
  `;
}

async function modHospital(id, action) { await api(`/api/admin/hospitals/${id}?action=${action}`, { method: "PATCH" }); toast("Updated", "success"); render(); }
async function toggleBlock(id, blocked) { await api(`/api/admin/users/${id}/block?blocked=${blocked}`, { method: "PATCH" }); render(); }
async function adminCancelReq(id) { await api(`/api/admin/requests/${id}/cancel`, { method: "PATCH" }); render(); }
async function setReportStatus(id, status) { await api(`/api/admin/reports/${id}?status=${status}`, { method: "PATCH" }); render(); }
async function seedDemo() { const r = await api("/api/admin/demo/seed-donors", { method: "POST" }); document.getElementById("demo-log").innerText = `Created ${r.created} demo donors [${r.label}]`; render(); }
async function simulateDemo() {
  const r = await api("/api/admin/demo/simulate", { method: "POST" });
  document.getElementById("demo-log").innerText = `[${r.label}] Request #${r.request_id}\n` + r.steps.map(s => "→ " + s).join("\n");
  render();
}

// ---------------- Router ----------------
async function render() {
  renderNav();
  const app = document.getElementById("app");
  const hash = location.hash || "#/";
  app.classList.remove("page-enter"); void app.offsetWidth; // restart animation
  try {
    if (hash === "#/" || hash === "") app.innerHTML = await pageLanding();
    else if (hash === "#/register") { app.innerHTML = pageRegister(); wireRegisterEvents(); }
    else if (hash === "#/login") app.innerHTML = pageLogin();
    else if (!state.token) { location.hash = "#/login"; return; }
    else if (hash === "#/dashboard") { app.innerHTML = await pageDashboard(); wireDashboardEvents(); }
    else if (hash === "#/requests") app.innerHTML = await pageRequests();
    else if (hash === "#/create-request") { app.innerHTML = await pageCreateRequest(); wireCreateRequestEvents(); }
    else if (hash === "#/my-requests") app.innerHTML = await pageMyRequests();
    else if (hash.startsWith("#/request/")) app.innerHTML = await pageRequestDetail(hash.split("/")[2]);
    else if (hash === "#/my-donations") app.innerHTML = await pageMyDonations();
    else if (hash === "#/notifications") app.innerHTML = await pageNotifications();
    else if (hash === "#/profile") { app.innerHTML = await pageProfile(); wireProfileEvents(); }
    else if (hash === "#/admin") { if (state.user.role !== "admin") { toast("Admin only", "error"); location.hash = "#/dashboard"; return; } app.innerHTML = await pageAdmin(); }
    else app.innerHTML = `<p class="muted mt-6">Not found</p>`;
  } catch (e) {
    app.innerHTML = `<p class="mt-6" style="color:#ff5c7a">${e.message}</p>`;
  }
  app.classList.add("page-enter");

  const rf = document.getElementById("register-form");
  if (rf) rf.onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    body.consent_notifications = fd.get("consent_notifications") === "on";
    body.register_as_donor = fd.get("register_as_donor") === "on";
    body.register_as_hospital = fd.get("register_as_hospital") === "on";
    if (!body.dob) delete body.dob;
    if (!body.blood_group) delete body.blood_group;
    if (!body.hospital_name) delete body.hospital_name;
    if (!body.hospital_address) delete body.hospital_address;
    try {
      const res = await api("/api/auth/register", { method: "POST", body });
      loginSuccess(res);
    } catch (err) { toast(err.message, "error"); }
  };

  const lf = document.getElementById("login-form");
  if (lf) lf.onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    try { const res = await api("/api/auth/login", { method: "POST", body }); loginSuccess(res); }
    catch (err) { toast(err.message, "error"); }
  };
}

function loginSuccess(res) {
  state.token = res.access_token; state.user = res.user;
  localStorage.setItem("ll_token", state.token);
  toast(`Welcome, ${res.user.name}!`, "success");
  connectWS();
  location.hash = res.user.role === "admin" ? "#/admin" : "#/dashboard";
  render();
}

async function loadMe() {
  if (!state.token) return;
  try { state.user = await api("/api/auth/me"); connectWS(); }
  catch (e) { state.token = null; localStorage.removeItem("ll_token"); }
}

window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", async () => { await loadMe(); render(); });