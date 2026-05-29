/* Shared helpers, icon component, and mock data for the Emberlog web console kit.
   Covers both the Traffic and Dispatch domains. */

/* ---------------------------------------------------------------------------
   Icon — inline SVG owned by React (reads geometry from window.lucide.icons).
   No DOM mutation, so it survives re-renders during filtering. size = 1em default.
--------------------------------------------------------------------------- */
function _pascal(name) { return name.split("-").map((s) => s.charAt(0).toUpperCase() + s.slice(1)).join(""); }
function _camel(attrs) {
  const out = {};
  for (const k in attrs) out[k.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = attrs[k];
  return out;
}
function Icon({ name, size, className, style, strokeWidth = 2 }) {
  const node = (window.lucide && window.lucide.icons) ? window.lucide.icons[_pascal(name)] : null;
  const dim = size == null ? "1em" : size;
  const base = { width: dim, height: dim, flex: "none", ...(style || {}) };
  if (!node) return <svg className={`lucide ${className || ""}`} viewBox="0 0 24 24" style={base} />;
  return (
    <svg className={`lucide ${className || ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" style={base} aria-hidden="true">
      {node.map((c, i) => React.createElement(c[0], { key: i, ..._camel(c[1] || {}) }))}
    </svg>
  );
}

/* ---- time helpers ---- */
const NOW = new Date("2026-05-28T20:53:38Z").getTime();
const secondsAgo = (s) => new Date(NOW - s * 1000).toISOString();
function relAgo(iso) {
  const s = Math.max(0, Math.floor((NOW - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ${m % 60}m ago`;
}
function clock(iso) {
  return new Date(iso).toLocaleTimeString(undefined, { hour12: true, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/* ===========================================================================
   TRAFFIC domain data
=========================================================================== */
function fmtFreq(mhz) { return mhz == null ? "Unknown" : `${mhz.toFixed(5)} MHz`; }
function fmtElapsed(seconds) { const m = Math.floor(seconds / 60); const s = seconds % 60; return `${m}:${String(s).padStart(2, "0")}`; }
function fmtDateTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.valueOf())) return "Unknown";
  const date = d.toLocaleDateString(undefined, { month: "short", day: "2-digit" });
  const time = d.toLocaleTimeString(undefined, { hour12: true, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return `${date}, ${time}`;
}
function statusAccent(status) { return { ok: "#10B981", warn: "#F59E0B", bad: "#F43F5E" }[status] || "#94A3B8"; }

const SYSTEMS = [
  { key: "RWC",   sys_name: "RWC Regional", group: "Phoenix Fire",   sys_num: 1, decode_rate_pct: 97.4, status: "ok",   control_channel_mhz: 851.0625, interval_s: 3.0, sites: 2 },
  { key: "PSPRS", sys_name: "PSPRS West",   group: "Maricopa",       sys_num: 2, decode_rate_pct: 71.2, status: "warn", control_channel_mhz: 853.4875, interval_s: 3.2, sites: 1 },
  { key: "VLY",   sys_name: "Valley Net",   group: "Regional Mutual",sys_num: 3, decode_rate_pct: 99.1, status: "ok",   control_channel_mhz: 770.1500, interval_s: 2.8, sites: 3 },
  { key: "RURAL", sys_name: "Rural Link",   group: "County",         sys_num: 4, decode_rate_pct: 38.5, status: "bad",  control_channel_mhz: null,     interval_s: 6.1, sites: 1 },
  { key: "AIR",   sys_name: "AirOps",       group: "Phoenix Fire",   sys_num: 5, decode_rate_pct: 88.0, status: "ok",   control_channel_mhz: 856.2125, interval_s: 3.1, sites: 1 },
];

const CALLS = [
  { id: "c1", sys_name: "RWC Regional", group: "Phoenix Fire", talkgroup: "Fire Dispatch", talkgroup_id: 52071, description: "Structure fire — 14th St & Camelback", category: "Fire", tag: "Dispatch", freq_mhz: 851.06250, started_at: secondsAgo(187), elapsed_s: 187, encrypted: false, rec_num: 3, src_num: 1042, emergency: false, phase2_tdma: true, tdma_slot: 1, isActive: true, lastSeenAt: secondsAgo(0) },
  { id: "c2", sys_name: "VLY", group: "Regional Mutual", talkgroup: "EMS Tac 2", talkgroup_id: 1207, description: "Medical — chest pain", category: "EMS", tag: "Tac", freq_mhz: 853.48750, started_at: secondsAgo(41), elapsed_s: 41, encrypted: false, rec_num: 7, src_num: 880, emergency: false, phase2_tdma: false, tdma_slot: null, isActive: true, lastSeenAt: secondsAgo(0) },
  { id: "c3", sys_name: "PSPRS West", group: "Maricopa", talkgroup: "PD Special Ops", talkgroup_id: 9920, description: "Encrypted — no audio", category: "Law", tag: "SpecOps", freq_mhz: 770.31250, started_at: secondsAgo(22), elapsed_s: 22, encrypted: true, rec_num: -1, src_num: null, emergency: false, phase2_tdma: false, tdma_slot: null, isActive: true, lastSeenAt: secondsAgo(0) },
  { id: "c4", sys_name: "RWC Regional", group: "Phoenix Fire", talkgroup: "Command 1", talkgroup_id: 52001, description: "IC to dispatch — second alarm", category: "Fire", tag: "Command", freq_mhz: 851.21250, started_at: secondsAgo(420), elapsed_s: 96, encrypted: false, rec_num: 2, src_num: 1042, emergency: true, phase2_tdma: true, tdma_slot: 0, isActive: false, lastSeenAt: secondsAgo(310), endedAt: secondsAgo(310) },
  { id: "c5", sys_name: "AirOps", group: "Phoenix Fire", talkgroup: "Air-to-Ground", talkgroup_id: 4400, description: "Helicopter ops", category: "Fire", tag: "Air", freq_mhz: 856.21250, started_at: secondsAgo(640), elapsed_s: 53, encrypted: false, rec_num: 9, src_num: 311, emergency: false, phase2_tdma: false, tdma_slot: null, isActive: false, lastSeenAt: secondsAgo(560), endedAt: secondsAgo(560) },
  { id: "c6", sys_name: "VLY", group: "Regional Mutual", talkgroup: "Public Works", talkgroup_id: 7711, description: "Road closure coordination", category: "Local Gov", tag: "Ops", freq_mhz: 770.15000, started_at: secondsAgo(905), elapsed_s: 140, encrypted: false, rec_num: 5, src_num: 622, emergency: false, phase2_tdma: false, tdma_slot: null, isActive: false, lastSeenAt: secondsAgo(820), endedAt: secondsAgo(820) },
  { id: "c7", sys_name: "PSPRS West", group: "Maricopa", talkgroup: "Detective Net", talkgroup_id: 9931, description: "Encrypted — no audio", category: "Law", tag: "Detective", freq_mhz: 770.48750, started_at: secondsAgo(1200), elapsed_s: 64, encrypted: true, rec_num: -1, src_num: null, emergency: false, phase2_tdma: false, tdma_slot: null, isActive: false, lastSeenAt: secondsAgo(1120), endedAt: secondsAgo(1120) },
  { id: "c8", sys_name: "RWC Regional", group: "Phoenix Fire", talkgroup: "Fire Tac 4", talkgroup_id: 52044, description: "Overhaul — clear", category: "Fire", tag: "Tac", freq_mhz: 851.33750, started_at: secondsAgo(1530), elapsed_s: 212, encrypted: false, rec_num: 4, src_num: 1042, emergency: false, phase2_tdma: true, tdma_slot: 1, isActive: false, lastSeenAt: secondsAgo(1450), endedAt: secondsAgo(1450) },
];

/* ===========================================================================
   DISPATCH domain data
=========================================================================== */

/* Incident-type → category + color (categorical scale, harmonious on slate) */
const CAT = {
  Fire:    { accent: "#F4523B", tint: "rgba(244,82,59,.16)",  icon: "flame" },
  EMS:     { accent: "#14B8A6", tint: "rgba(20,184,166,.16)", icon: "heart-pulse" },
  MVC:     { accent: "#F59E0B", tint: "rgba(245,158,11,.16)", icon: "car-front" },
  Alarm:   { accent: "#38BDF8", tint: "rgba(56,189,248,.16)", icon: "bell-ring" },
  Service: { accent: "#A78BFA", tint: "rgba(167,139,250,.16)",icon: "wrench" },
  Other:   { accent: "#94A3B8", tint: "rgba(148,163,184,.16)",icon: "circle-help" },
};
const TYPE_CAT = {
  "Structure Fire": "Fire", "Vehicle Fire": "Fire", "Brush Fire": "Fire",
  "Breathing Problem": "EMS", "Ill Person": "EMS", "Unknown Medical": "EMS", "Cardiac Arrest": "EMS",
  "Traffic Collision": "MVC",
  "Alarm": "Alarm",
  "Service Call": "Service",
};
const catOf = (type) => TYPE_CAT[type] || "Other";
const typeStyle = (type) => CAT[catOf(type)] || CAT.Other;
const ALL_TYPES = Object.keys(TYPE_CAT);
const ALL_CATS = ["Fire", "EMS", "MVC", "Alarm", "Service"];

/* Phoenix Regional Dispatch — official agency unit-number blocks.
   Source: City of Phoenix Fire "Fire Departments/Fire Districts" numbering (Rev. 2012),
   phoenix.gov/.../094635.pdf. Agencies exceeding their block append a 4th digit in
   sequence (e.g. Glendale 151–159 → 1510, 1511…), handled by cityOfUnit(). */
const AGENCIES = [
  { name: "Phoenix", min: 1, max: 99 }, { name: "Sun City West", min: 101, max: 109 },
  { name: "El Mirage", min: 121, max: 129 }, { name: "Sun City", min: 131, max: 139 },
  { name: "Daisy Mountain", min: 141, max: 149 }, { name: "Glendale", min: 151, max: 159 },
  { name: "Tolleson", min: 161, max: 169 }, { name: "Avondale", min: 171, max: 179 },
  { name: "Goodyear", min: 181, max: 189 }, { name: "Peoria", min: 191, max: 199 },
  { name: "Mesa", min: 201, max: 229 }, { name: "Sun Lakes", min: 231, max: 239 },
  { name: "Guadalupe", min: 241, max: 249 }, { name: "Gilbert", min: 251, max: 259 },
  { name: "Apache Junction", min: 261, max: 269 }, { name: "Tempe", min: 271, max: 279 },
  { name: "Chandler", min: 281, max: 289 }, { name: "Salt River", min: 291, max: 299 },
  { name: "Surprise", min: 301, max: 319 }, { name: "Buckeye Valley", min: 321, max: 329 },
  { name: "Black Canyon City", min: 331, max: 339 }, { name: "Tonopah", min: 341, max: 349 },
  { name: "Palo Verde", min: 351, max: 359 }, { name: "Luke Air Force Base", min: 361, max: 369 },
  { name: "Harquahala", min: 371, max: 379 }, { name: "Gila Bend", min: 381, max: 389 },
  { name: "Fort McDowell", min: 401, max: 409 }, { name: "Queen Creek", min: 411, max: 419 },
  { name: "Gila River", min: 421, max: 439 }, { name: "Rio Verde", min: 441, max: 449 },
  { name: "Casa Grande", min: 501, max: 515 }, { name: "Stanfield", min: 516, max: 519 },
  { name: "Eloy", min: 521, max: 529 }, { name: "Coolidge", min: 531, max: 539 },
  { name: "Florence", min: 541, max: 549 }, { name: "Queen Valley", min: 551, max: 555 },
  { name: "Thunderbird Farms", min: 556, max: 559 }, { name: "Ak-Chin", min: 561, max: 565 },
  { name: "Arizona City", min: 566, max: 569 }, { name: "Maricopa", min: 571, max: 585 },
  { name: "Regional Fire Rescue", min: 586, max: 589 }, { name: "Western Fire", min: 591, max: 595 },
  { name: "Evergreen Fire", min: 596, max: 599 }, { name: "Scottsdale", min: 601, max: 629 },
  { name: "Superior", min: 631, max: 639 }, { name: "Hayden", min: 641, max: 649 },
  { name: "Kearney", min: 651, max: 659 }, { name: "Mammoth", min: 661, max: 669 },
  { name: "Dudleyville", min: 671, max: 679 }, { name: "San Manuel", min: 681, max: 689 },
  { name: "Oracle", min: 691, max: 699 }, { name: "Buckeye", min: 701, max: 749 },
  { name: "Wickenburg", min: 751, max: 759 }, { name: "Wittman", min: 761, max: 764 },
  { name: "Circle City / Morristown", min: 765, max: 769 }, { name: "Rural/Metro", min: 800, max: 899 },
  { name: "Phoenix Adaptive Response", min: 900, max: 999 },
];
const ALL_CITIES = AGENCIES.map((a) => a.name);
function agencyRange(name) { const a = AGENCIES.find((a) => a.name === name); return a ? `${a.min}–${a.max}` : ""; }
function unitNumber(unit) { const m = String(unit).match(/(\d+)/); return m ? parseInt(m[1], 10) : NaN; }
function cityOfUnit(unit) {
  let n = unitNumber(unit);
  if (Number.isNaN(n)) return "Other";
  while (n > 999) n = Math.floor(n / 10); // unwind 4th+ overflow digit
  const a = AGENCIES.find((a) => n >= a.min && n <= a.max);
  return a ? a.name : "Other";
}
function citiesOfIncident(inc) { return [...new Set(inc.units.map(cityOfUnit))]; }

const at = (s) => secondsAgo(s);
const INCIDENTS = [
  { id: 84, dispatched_at: at(8),    special_call: true,  units: ["Engine 9", "Ladder 11", "BC 2"],     channel: "K-Deck 3", incident_type: "Structure Fire",   address: "1402 E Roosevelt St",      transcript: "Engine 9 Ladder 11 Battalion 2 structure fire 1402 East Roosevelt Street cross of 14th Street working fire", original_text: "engine 9 ladder 11 battalion 2 structure fire 1402 east roosevelt st cross 14th st workin fire", correlation: { system: "RWC Regional", tg: 52001 } },
  { id: 83, dispatched_at: at(64),   special_call: false, units: ["Engine 277", "Rescue 277"],          channel: "K-Deck 5", incident_type: "Traffic Collision", address: "I-10 & Broadway Rd",        transcript: "Engine 277 Rescue 277 vehicle collision Interstate 10 and Broadway Road", original_text: "engine 277 rescue 277 vehicle collision i 10 and broadway rd", correlation: { system: "VLY", tg: 1207 } },
  { id: 82, dispatched_at: at(168),  special_call: false, units: ["Engine 25"],                         channel: "K-Deck 9", incident_type: "Breathing Problem", address: "880 N 3rd St",              transcript: "Engine 25 K-Deck 9 breathing problem 880 North 3rd Street", original_text: "engine 25 k deck 9 breathing problem 880 n 3rd st", correlation: { system: "RWC Regional", tg: 52071 } },
  { id: 81, dispatched_at: at(266),  special_call: false, units: ["Engine 25"],                         channel: "K-Deck 9", incident_type: "Ill Person",       address: "5510 W Wolf St",            transcript: "Engine 25 K-Deck 9 Ill Person 5510 West Wolf Street Engine 25 K-Deck 9", original_text: "Engine 25 K-Deck 9 Ilverson 5510 West Wolf Street Engine 25 K-Deck 9", correlation: { system: "RWC Regional", tg: 52071 } },
  { id: 80, dispatched_at: at(540),  special_call: false, units: ["Engine 211"],                        channel: "K-Deck 1", incident_type: "Alarm",            address: "200 W Main St, Mesa",       transcript: "Engine 211 fire alarm activation 200 West Main Street commercial structure", original_text: "engine 211 fire alarm activation 200 w main st commercial", correlation: { system: "VLY", tg: 4400 } },
  { id: 79, dispatched_at: at(840),  special_call: false, units: ["Engine 609", "Rescue 609"],          channel: "K-Deck 9", incident_type: "Unknown Medical",  address: "7447 E Indian School Rd",   transcript: "Engine 609 Rescue 609 unknown medical 7447 East Indian School Road", original_text: "engine 609 rescue 609 unknown medical 7447 e indian school rd", correlation: { system: "RWC Regional", tg: 52071 } },
  { id: 78, dispatched_at: at(1320), special_call: false, units: ["Engine 155", "Ladder 152"],          channel: "K-Deck 3", incident_type: "Vehicle Fire",     address: "5901 W Northern Ave",       transcript: "Engine 155 Ladder 152 vehicle fire 5901 West Northern Avenue", original_text: "engine 155 ladder 152 vehicle fire 5901 w northern ave", correlation: { system: "RWC Regional", tg: 52044 } },
  { id: 77, dispatched_at: at(1860), special_call: true,  units: ["Engine 5", "Rescue 5", "Ladder 1"],  channel: "K-Deck 9", incident_type: "Cardiac Arrest",   address: "1601 E Van Buren St",       transcript: "Engine 5 Rescue 5 Ladder 1 cardiac arrest 1601 East Van Buren Street CPR in progress", original_text: "engine 5 rescue 5 ladder 1 cardiac arrest 1601 e van buren st cpr in progress", correlation: { system: "RWC Regional", tg: 52071 } },
  { id: 76, dispatched_at: at(2640), special_call: false, units: ["Engine 277", "Ladder 271"],          channel: "K-Deck 5", incident_type: "Traffic Collision", address: "Rural Rd & University Dr",  transcript: "Engine 277 Ladder 271 motor vehicle collision Rural Road and University Drive", original_text: "engine 277 ladder 271 mvc rural rd and university dr", correlation: { system: "VLY", tg: 1207 } },
  { id: 75, dispatched_at: at(3480), special_call: false, units: ["Engine 197", "Ladder 155"],          channel: "K-Deck 7", incident_type: "Brush Fire",       address: "9875 W Happy Valley Rd",    transcript: "Engine 197 Ladder 155 brush fire 9875 West Happy Valley Road mutual aid", original_text: "engine 197 ladder 155 brush fire 9875 w happy valley rd mutual aid", correlation: { system: "AirOps", tg: 4400 } },
  { id: 74, dispatched_at: at(4320), special_call: false, units: ["Engine 18"],                         channel: "A-Deck 2", incident_type: "Service Call",     address: "333 N Central Ave",         transcript: "Engine 18 public assist service call 333 North Central Avenue", original_text: "engine 18 public assist service call 333 n central ave", correlation: { system: "RWC Regional", tg: 52044 } },
  { id: 73, dispatched_at: at(5700), special_call: false, units: ["Rescue 218"],                         channel: "K-Deck 9", incident_type: "Breathing Problem", address: "1320 S Stapley Dr",         transcript: "Rescue 218 breathing problem 1320 South Stapley Drive", original_text: "rescue 218 breathing problem 1320 s stapley dr", correlation: { system: "VLY", tg: 1207 } },
];

const ALL_UNITS = [...new Set(INCIDENTS.flatMap((i) => i.units))].sort((a, b) => unitNumber(a) - unitNumber(b));
const ALL_CHANNELS = [...new Set(INCIDENTS.map((i) => i.channel))].sort();
/* cities that actually appear in current incidents (used to keep the City filter relevant) */
const ACTIVE_CITIES = [...new Set(INCIDENTS.flatMap(citiesOfIncident))].sort((a, b) => ALL_CITIES.indexOf(a) - ALL_CITIES.indexOf(b));

/* ---- audio waveform (deterministic bars; represents audio.segment playback) ---- */
function Waveform({ accent, played = 0.34, bars = 48, height = 40, seed = 7 }) {
  let s = seed * 131 + 7;
  const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  const heights = Array.from({ length: bars }, (_, i) => { const env = Math.sin((i / bars) * Math.PI); return 0.18 + env * (0.35 + rnd() * 0.65); });
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 2, height }}>
      {heights.map((h, i) => (
        <div key={i} style={{ flex: 1, height: `${Math.round(h * 100)}%`, borderRadius: 1, background: i / bars < played ? accent : "rgba(255,255,255,.22)" }} />
      ))}
    </div>
  );
}

/* ---- map placeholder (real tile provider slots in later) ---- */
function MapPin({ accent, address, height = 130 }) {
  return (
    <div style={{ position: "relative", height, borderRadius: 12, overflow: "hidden", border: "1px solid var(--el-line-15)",
      background: "repeating-linear-gradient(0deg,#0c1322 0 23px,#0f1a2e 23px 24px), repeating-linear-gradient(90deg,#0c1322 0 23px,#0f1a2e 23px 24px)", backgroundColor: "#0c1322" }}>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
          <Icon name="map-pin" size={26} style={{ color: accent }} />
          <span style={{ fontSize: 11, color: "rgba(255,255,255,.7)", fontWeight: 600 }}>{address}</span>
        </div>
      </div>
      <span style={{ position: "absolute", top: 7, left: 9, fontSize: 9.5, letterSpacing: ".12em", textTransform: "uppercase", color: "rgba(255,255,255,.4)" }}>Map · placeholder</span>
    </div>
  );
}

Object.assign(window, {
  Icon, NOW, relAgo, clock,
  fmtFreq, fmtElapsed, fmtDateTime, statusAccent, SYSTEMS, CALLS,
  CAT, catOf, typeStyle, TYPE_CAT, ALL_TYPES, ALL_CATS,
  AGENCIES, ALL_CITIES, ACTIVE_CITIES, agencyRange, unitNumber, cityOfUnit, citiesOfIncident,
  INCIDENTS, ALL_UNITS, ALL_CHANNELS, Waveform, MapPin,
});
