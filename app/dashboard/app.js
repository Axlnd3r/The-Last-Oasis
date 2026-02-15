const $ = id => document.getElementById(id);

const GRID = 20;
const CANVAS = 800;
const CELL = CANVAS / GRID; // 40px per cell

// ─── Agent type detection ───
function agentType(name) {
  if (!name) return "unknown";
  const n = name.toLowerCase();
  if (n.includes("dqn")) return "dqn";
  if (n.includes("belief") || n.includes("bandit")) return "belief";
  if (n.includes("trad")) return "trader";
  return "random";
}

const TYPE_INFO = {
  random:  { label: "Random",  color: "#cc6633", dotColor: "#ff8844", body: "#cc6633", cloak: "#884422", eye: "#fff" },
  belief:  { label: "Belief",  color: "#3399cc", dotColor: "#44aaff", body: "#3388bb", cloak: "#225588", eye: "#fff" },
  trader:  { label: "Trader",  color: "#ccaa33", dotColor: "#ffdd44", body: "#ccaa33", cloak: "#887722", eye: "#fff" },
  dqn:     { label: "DQN",     color: "#33cc66", dotColor: "#44ff88", body: "#33bb55", cloak: "#228833", eye: "#ff4444" },
  unknown: { label: "Agent",   color: "#999999", dotColor: "#aaaaaa", body: "#888888", cloak: "#555555", eye: "#fff" },
};

// ─── Zone definitions ───
const ZONES = [
  { name: "The Oasis Heart",  icon: "\uD83C\uDFDD\uFE0F", x: 9,  y: 9,  r: 3, type: "safe",   desc: "Abundant water and resources at the center. The safest zone — but heavily contested.", img: "/assets/Oasisheart.png", imgClick: "/assets/TheOasisHeartAfterClick.png" },
  { name: "Dune Wastes",      icon: "\uD83C\uDFDC\uFE0F", x: 3,  y: 3,  r: 3, type: "danger",  desc: "Wind-swept dunes with almost no resources. Great for traversal, terrible for staying alive.", img: "/assets/Dunewastes.png" },
  { name: "Ancient Ruins",    icon: "\uD83C\uDFDA\uFE0F", x: 16, y: 3,  r: 3, type: "hazard",  desc: "Crumbling structures hide deadly traps. Enter for rewards, leave if you can.", img: "/assets/ancient_ruins.png" },
  { name: "Trading Post",     icon: "\uD83D\uDED2",        x: 15, y: 15, r: 3, type: "safe",    desc: "Neutral ground where agents exchange resources without direct combat.", img: "/assets/tradingpost.png" },
  { name: "Scorched Plains",  icon: "\uD83D\uDD25",        x: 3,  y: 16, r: 3, type: "danger",  desc: "High degradation erodes all who enter. Fast to cross, lethal to camp in.", img: "/assets/scorchedplans.png" },
  { name: "Palm Grove",       icon: "\uD83C\uDF34",        x: 9,  y: 2,  r: 2, type: "safe",    desc: "Sheltered grove with palm shade. Moderate resources and low hazard." },
  { name: "Bone Fields",      icon: "\u2620\uFE0F",        x: 17, y: 10, r: 2, type: "hazard",  desc: "Graveyard of failed agents. Hazard spikes and ruins mark past mistakes.", img: "/assets/bonefields.png" },
];

const agentNames = {};
let currentLayer = "all";
let tradeCount = 0;
let combatCount = 0;
let gridData = null;
let selectedAgent = null;

// ─── Map background image ───
const mapBgImg = new Image();
mapBgImg.src = "/assets/OasisMAP.png";
let mapBgLoaded = false;
mapBgImg.onload = () => { mapBgLoaded = true; if (gridData) drawMap(gridData); };

// ─── Seeded random ───
function tileHash(x, y) {
  let h = (x * 374761393 + y * 668265263) ^ 0x5bd1e995;
  h = ((h >> 13) ^ h) * 0x5bd1e995;
  return ((h >> 15) ^ h) >>> 0;
}
function hashN(h, n) { return ((h >> n) ^ (h * 2654435761)) >>> 0; }
function p(ctx, x, y, w, h, c) { ctx.fillStyle = c; ctx.fillRect(x, y, w, h); }

// ═══════════════════════════════════════
// PIXEL ART AGENT SPRITE DRAWER
// ═══════════════════════════════════════

function drawAgentSprite(canvas, type, alive) {
  const ctx = canvas.getContext("2d");
  const info = TYPE_INFO[type] || TYPE_INFO.unknown;
  const w = canvas.width;   // 20
  const h = canvas.height;  // 24

  ctx.clearRect(0, 0, w, h);
  if (!alive) ctx.globalAlpha = 0.4;

  const px = (x, y, c) => { ctx.fillStyle = c; ctx.fillRect(x, y, 1, 1); };
  const px2 = (x, y, w2, h2, c) => { ctx.fillStyle = c; ctx.fillRect(x, y, w2, h2); };

  // ── Shadow ──
  px2(5, 21, 10, 2, "rgba(0,0,0,0.2)");

  // ── Body (robed figure) ──
  const body = info.body;
  const cloak = info.cloak;
  const skin = "#d4a574";

  // Hood/head
  px2(7, 1, 6, 2, cloak);       // hood top
  px2(6, 3, 8, 3, cloak);       // hood sides
  px2(7, 3, 6, 3, body);        // face area

  // Eyes
  if (type === "dqn") {
    // DQN has glowing red eyes
    px(8, 4, "#ff2222"); px(11, 4, "#ff2222");
    px(8, 5, "#ff6644"); px(11, 5, "#ff6644");
  } else {
    px(8, 4, "#2a1a0a"); px(11, 4, "#2a1a0a");  // eyes
    px(9, 5, "#2a1a0a");                          // mouth
  }

  // Torso
  px2(6, 6, 8, 5, body);         // main robe
  px2(5, 7, 1, 3, cloak);        // left sleeve
  px2(14, 7, 1, 3, cloak);       // right sleeve

  // Robe detail line
  px2(9, 7, 2, 4, cloak);        // center fold

  // Arms
  px2(4, 8, 2, 3, skin);         // left hand
  px2(14, 8, 2, 3, skin);        // right hand

  // Lower robe
  px2(6, 11, 8, 5, body);
  px2(5, 12, 1, 4, body);
  px2(14, 12, 1, 4, body);
  px2(7, 14, 2, 2, cloak);       // robe shadow left
  px2(11, 14, 2, 2, cloak);      // robe shadow right

  // Legs/feet
  px2(7, 16, 2, 3, "#3a2a18");
  px2(11, 16, 2, 3, "#3a2a18");
  px2(6, 19, 3, 2, "#2a1a0a");   // left boot
  px2(11, 19, 3, 2, "#2a1a0a");  // right boot

  // ── Type-specific accessories ──
  if (type === "random") {
    // Wanderer's staff (left hand)
    px2(3, 3, 1, 14, "#8a6a38");
    px2(3, 2, 1, 1, "#cc9944");
    px(2, 1, "#ffcc44");  // staff gem
  } else if (type === "belief") {
    // Crystal orb (right hand)
    px2(15, 6, 3, 3, "#44aaff");
    px(16, 6, "#88ccff");
    px(15, 7, "#2266aa");
    // Headband
    px2(6, 3, 8, 1, "#44aaff");
  } else if (type === "trader") {
    // Coin bag
    px2(14, 9, 4, 3, "#aa8833");
    px2(15, 8, 2, 1, "#aa8833");
    px(15, 9, "#ffdd44");  // coin
    // Hat brim
    px2(5, 1, 10, 1, "#887722");
    px2(7, 0, 6, 1, "#aa9933");
  } else if (type === "dqn") {
    // Neural network symbol on chest
    px(8, 8, "#44ff88"); px(10, 8, "#44ff88"); px(12, 8, "#44ff88");
    px(9, 9, "#44ff88"); px(11, 9, "#44ff88");
    px(10, 10, "#44ff88");
    // Glowing aura
    ctx.shadowColor = "#44ff88";
    ctx.shadowBlur = 3;
    px2(6, 6, 8, 5, "rgba(68,255,136,0.08)");
    ctx.shadowBlur = 0;
  }

  ctx.globalAlpha = 1;
}


// ═══════════════════════════════════════
// MAP RENDERER
// ═══════════════════════════════════════

function drawMap(data) {
  const canvas = $("mapCanvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, CANVAS, CANVAS);

  if (!data || !data.tiles) return;

  const tileLookup = {};
  for (const t of data.tiles) tileLookup[`${t.x},${t.y}`] = t;

  function getTile(x, y) {
    const key = `${Math.max(0,Math.min(GRID-1,x))},${Math.max(0,Math.min(GRID-1,y))}`;
    return tileLookup[key] || { degradation: 0, hazard: 0, resource: 50 };
  }

  if (currentLayer !== "all") {
    drawHeatmap(ctx, data.tiles);
  } else {
    drawWorldView(ctx, getTile);
  }

  updateAgentDots(data.agents || []);
}

// ─── WORLD VIEW RENDERER ───
function drawWorldView(ctx, getTile) {
  // Draw the background map image if loaded
  if (mapBgLoaded) {
    ctx.drawImage(mapBgImg, 0, 0, CANVAS, CANVAS);

    // Overlay tile-state effects on top of the image
    for (let gy = 0; gy < GRID; gy++) {
      for (let gx = 0; gx < GRID; gx++) {
        const tile = getTile(gx, gy);
        const px = gx * CELL;
        const py = gy * CELL;
        const deg = tile.degradation || 0;
        const haz = tile.hazard || 0;
        const res = tile.resource || 0;

        // Degradation overlay (darkens tile)
        if (deg > 0.05) {
          ctx.fillStyle = `rgba(60,20,0,${Math.min(0.5, deg * 0.55)})`;
          ctx.fillRect(px, py, CELL, CELL);
        }

        // Hazard overlay (red tint)
        if (haz > 0.1) {
          ctx.fillStyle = `rgba(180,30,10,${Math.min(0.45, haz * 0.5)})`;
          ctx.fillRect(px, py, CELL, CELL);
        }

        // Resource glow (green shimmer on resource-rich tiles)
        if (res > 60) {
          ctx.fillStyle = `rgba(74,222,128,${Math.min(0.15, (res - 60) / 400)})`;
          ctx.fillRect(px, py, CELL, CELL);
        }
      }
    }
  } else {
    // Fallback: procedural rendering if image not loaded
    drawWorldViewFallback(ctx, getTile);
  }
}

// Fallback procedural world view
function drawWorldViewFallback(ctx, getTile) {
  const center = GRID / 2;
  for (let gy = 0; gy < GRID; gy++) {
    for (let gx = 0; gx < GRID; gx++) {
      const tile = getTile(gx, gy);
      const px = gx * CELL;
      const py = gy * CELL;
      const deg = tile.degradation || 0;
      const haz = tile.hazard || 0;
      const res = tile.resource || 0;
      const h = tileHash(gx, gy);

      const dx = (gx - center + 0.5) / GRID;
      const dy = (gy - center + 0.5) / GRID;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const noise = ((h % 1000) / 1000 - 0.5) * 0.08;

      const waterR = 0.12 + noise;
      const shoreR = 0.18 + noise;
      const greenR = 0.28 + noise;

      if (dist < waterR) {
        const depth = 1 - dist / waterR;
        ctx.fillStyle = `rgb(${Math.round(30 + 20 * depth)},${Math.round(100 + 60 * depth)},${Math.round(150 + 50 * depth)})`;
        ctx.fillRect(px, py, CELL, CELL);
      } else if (dist < shoreR) {
        const t = (dist - waterR) / (shoreR - waterR);
        ctx.fillStyle = `rgb(${Math.round(140 + 60 * t)},${Math.round(155 + 35 * t)},${Math.round(130 - 30 * t)})`;
        ctx.fillRect(px, py, CELL, CELL);
      } else if (dist < greenR && res > 25) {
        const greenness = Math.min(1, res / 70) * (1 - (dist - shoreR) / (greenR - shoreR));
        ctx.fillStyle = `rgb(${Math.round(120 - 50 * greenness + (h % 20))},${Math.round(150 + 50 * greenness + (h % 15))},${Math.round(80 - 20 * greenness + (h % 15))})`;
        ctx.fillRect(px, py, CELL, CELL);
      } else {
        const sandV = h % 5;
        const bases = [[218,196,144],[206,184,132],[196,176,128],[214,192,138],[210,188,148]];
        let [bR, bG, bB] = bases[sandV];
        bR = Math.round(bR - deg * 60);
        bG = Math.round(bG - deg * 65);
        bB = Math.round(bB - deg * 40);
        ctx.fillStyle = `rgb(${bR},${bG},${bB})`;
        ctx.fillRect(px, py, CELL, CELL);
      }

      if (haz > 0.1) {
        ctx.fillStyle = `rgba(120,25,5,${Math.min(0.5, haz * 0.55)})`;
        ctx.fillRect(px, py, CELL, CELL);
      }
    }
  }
}

// ─── HEATMAP RENDERER ───
function drawHeatmap(ctx, tiles) {
  const prop = currentLayer === "degradation" ? "degradation" :
               currentLayer === "hazard" ? "hazard" : "resource";
  const maxVal = prop === "resource" ? 100 : 1;

  for (const t of tiles) {
    const px = t.x * CELL;
    const py = t.y * CELL;
    const raw = t[prop] || 0;
    const v = Math.min(1, raw / maxVal);

    let r, g, b;
    if (prop === "degradation") {
      r = Math.round(30 + 200 * v);
      g = Math.round(180 - 140 * v);
      b = 30;
    } else if (prop === "hazard") {
      r = Math.round(30 + 220 * v);
      g = Math.round(50 - 30 * v);
      b = Math.round(160 - 130 * v);
    } else {
      r = 20;
      g = Math.round(30 + 200 * v);
      b = Math.round(60 + 120 * v);
    }

    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.fillRect(px, py, CELL, CELL);

    ctx.fillStyle = "rgba(255,255,255,0.75)";
    ctx.font = "bold 9px 'Press Start 2P', monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const display = prop === "resource" ? Math.round(raw) : (raw * 100).toFixed(0);
    ctx.fillText(display, px + CELL / 2, py + CELL / 2);

    ctx.strokeStyle = "rgba(0,0,0,0.2)";
    ctx.lineWidth = 0.5;
    ctx.strokeRect(px + 0.5, py + 0.5, CELL - 1, CELL - 1);
  }
}

// ─── ZONE HOTSPOTS ───
function setupZones() {
  const container = $("zoneHotspots");
  container.innerHTML = "";

  for (const z of ZONES) {
    const hot = document.createElement("div");
    hot.className = "zone-hotspot";
    const xPct = ((z.x + 0.5) / GRID * 100);
    const yPct = ((z.y + 0.5) / GRID * 100);
    hot.style.left = `${xPct - 4}%`;
    hot.style.top = `${yPct - 3}%`;
    hot.style.width = "8%";
    hot.style.height = "6%";

    hot.innerHTML = `
      <div class="zone-marker ${z.type}"></div>
      <div class="zone-label">
        <span class="label-icon">${z.icon}</span>
        <span class="label-name">${z.name.toUpperCase()}</span>
      </div>
    `;

    hot.addEventListener("click", () => openZonePopup(z));
    container.appendChild(hot);
  }
}

// ─── Zone popup ───
function openZonePopup(zone) {
  const imgSrc = zone.imgClick || zone.img;
  if (!imgSrc) {
    // No image — show simple alert
    const agents = (gridData?.agents || []).filter(a => {
      return Math.abs(a.x - zone.x) <= zone.r && Math.abs(a.y - zone.y) <= zone.r && a.alive !== false;
    });
    alert(`${zone.icon} ${zone.name}\n\n${zone.desc}\n\nAgents here: ${agents.length}\nDifficulty: ${zone.type.toUpperCase()}`);
    return;
  }

  const agents = (gridData?.agents || []).filter(a => {
    return Math.abs(a.x - zone.x) <= zone.r && Math.abs(a.y - zone.y) <= zone.r && a.alive !== false;
  });

  $("zonePopupTitle").textContent = `${zone.icon} ${zone.name}`;
  $("zonePopupImg").src = imgSrc;
  $("zonePopupDesc").innerHTML =
    `${zone.desc}<br><br>` +
    `<span style="color:var(--gold)">Agents in zone: ${agents.length}</span> &nbsp; ` +
    `<span style="color:var(--${zone.type === 'safe' ? 'oasis' : zone.type === 'danger' ? 'danger' : 'hazard'})">${zone.type.toUpperCase()}</span>`;

  $("zonePopup").classList.add("active");
  $("zoneOverlay").classList.add("active");
}

function closeZonePopup() {
  $("zonePopup").classList.remove("active");
  $("zoneOverlay").classList.remove("active");
}

// ─── AGENT DOTS (HTML overlay with pixel sprites) ───
function updateAgentDots(agents) {
  const container = $("agentDots");
  container.innerHTML = "";

  for (const a of agents) {
    const name = agentNames[a.agent_id] || "";
    const type = agentType(name);
    const info = TYPE_INFO[type];

    const dot = document.createElement("div");
    dot.className = "agent-dot" + (a.alive === false ? " dead" : "") + (selectedAgent === a.agent_id ? " selected" : "");
    dot.style.left = `${((a.x + 0.5) / GRID) * 100}%`;
    dot.style.top = `${((a.y + 0.5) / GRID) * 100}%`;

    // Create a mini canvas for the pixel sprite
    const spriteCanvas = document.createElement("canvas");
    spriteCanvas.width = 20;
    spriteCanvas.height = 24;
    drawAgentSprite(spriteCanvas, type, a.alive !== false);
    dot.appendChild(spriteCanvas);

    // Name tag on hover
    const tag = document.createElement("div");
    tag.className = "agent-name-tag";
    tag.textContent = `${info.label}: ${name || a.agent_id.slice(0, 6)}`;
    dot.appendChild(tag);

    dot.title = `${name || a.agent_id.slice(0, 8)} [${info.label}] HP:${a.hp}`;
    dot.addEventListener("click", () => {
      selectedAgent = selectedAgent === a.agent_id ? null : a.agent_id;
      if (gridData) drawMap(gridData);
      refreshAgentList();
    });

    container.appendChild(dot);
  }
}

// ─── TOOLTIP ───
const mapCanvas = $("mapCanvas");
const tooltip = $("tooltip");

if (mapCanvas) {
  mapCanvas.addEventListener("mousemove", e => {
    if (!gridData || !gridData.tiles) { tooltip.style.display = "none"; return; }
    const rect = mapCanvas.getBoundingClientRect();
    const scaleX = CANVAS / rect.width;
    const scaleY = CANVAS / rect.height;
    const mx = (e.clientX - rect.left) * scaleX;
    const my = (e.clientY - rect.top) * scaleY;
    const gx = Math.floor(mx / CELL);
    const gy = Math.floor(my / CELL);
    if (gx < 0 || gx >= GRID || gy < 0 || gy >= GRID) { tooltip.style.display = "none"; return; }

    const tile = gridData.tiles.find(t => t.x === gx && t.y === gy);
    if (!tile) { tooltip.style.display = "none"; return; }

    const agent = (gridData.agents || []).find(a => a.x === gx && a.y === gy);
    const zone = ZONES.find(z => Math.abs(gx - z.x) <= z.r && Math.abs(gy - z.y) <= z.r);

    let html = `<span class="tt-coord">[${gx}, ${gy}]</span>`;
    if (zone) html += ` <span class="tt-val">${zone.icon} ${zone.name}</span>`;
    html += `<br><span class="tt-label">Degrad:</span> <span class="tt-val">${(tile.degradation * 100).toFixed(1)}%</span>`;
    html += `<br><span class="tt-label">Resource:</span> <span class="tt-val">${tile.resource}</span>`;
    html += `<br><span class="tt-label">Hazard:</span> <span class="${tile.hazard > 0.3 ? 'tt-danger' : 'tt-val'}">${(tile.hazard * 100).toFixed(1)}%</span>`;

    if (agent) {
      const aname = agentNames[agent.agent_id] || agent.agent_id.slice(0, 8);
      const atype = agentType(aname);
      const tinfo = TYPE_INFO[atype];
      const trust = agent.trust_score != null ? agent.trust_score : 100;
      const trustClass = trust > 70 ? 'tt-val' : trust > 40 ? 'tt-warn' : 'tt-danger';
      html += `<br><br><span class="tt-agent">${tinfo.label}: ${aname}</span>`;
      html += `<br><span class="tt-label">HP:</span> <span class="${agent.hp < 5 ? 'tt-danger' : 'tt-val'}">${agent.hp}/20</span>`;
      html += `<br><span class="tt-label">Trust:</span> <span class="${trustClass}">${trust.toFixed(0)}</span>`;
      if ((agent.betrayals || 0) > 0) html += `<br><span class="tt-danger">Betrayals: ${agent.betrayals}</span>`;
      if (agent.alive === false) html += `<br><span class="tt-danger">DEAD</span>`;
    }

    tooltip.innerHTML = html;
    tooltip.style.display = "block";
    tooltip.style.left = (e.clientX + 14) + "px";
    tooltip.style.top = (e.clientY + 14) + "px";
  });
  mapCanvas.addEventListener("mouseleave", () => { tooltip.style.display = "none"; });
}

// ─── AGENT LIST (sidebar) ───
function refreshAgentList() {
  const list = $("agentList");
  if (!gridData || !gridData.agents) { if (list) list.innerHTML = ""; return; }

  const agents = [...gridData.agents].sort((a, b) => {
    if (a.alive !== false && b.alive === false) return -1;
    if (a.alive === false && b.alive !== false) return 1;
    return (b.score || 0) - (a.score || 0);
  });

  list.innerHTML = "";
  for (const a of agents) {
    const name = agentNames[a.agent_id] || a.agent_id.slice(0, 8);
    const type = agentType(name);
    const info = TYPE_INFO[type];
    const hpRatio = Math.max(0, a.hp / 20);
    const hpColor = hpRatio > 0.5 ? "#4ade80" : hpRatio > 0.25 ? "#ffd866" : "#ff6b6b";

    const card = document.createElement("div");
    card.className = "agent-card" + (selectedAgent === a.agent_id ? " selected" : "");
    if (a.alive === false) card.style.opacity = "0.4";

    // Mini sprite preview in sidebar
    const spriteCanvas = document.createElement("canvas");
    spriteCanvas.width = 20;
    spriteCanvas.height = 24;
    spriteCanvas.style.cssText = "width:16px;height:19px;image-rendering:pixelated;float:left;margin-right:6px;margin-top:2px;";
    drawAgentSprite(spriteCanvas, type, a.alive !== false);

    const trustScore = a.trust_score != null ? a.trust_score : 100;
    const trustColor = trustScore > 90 ? "#4ade80" : trustScore > 70 ? "#ffd866" : trustScore > 40 ? "#ff9966" : "#ff6b6b";
    const betrayalIcon = (a.betrayals || 0) > 0 ? ` ⚠${a.betrayals}` : "";

    card.innerHTML = `
      <div class="agent-name" style="color:${info.color}">${info.label}: ${name}</div>
      <div class="agent-detail">HP: ${a.hp}/20 | Res: ${a.resource || 0} | Score: ${a.score || 0}${a.alive === false ? " | DEAD" : ""}</div>
      <div class="agent-detail" style="font-size:8px;">Trust: <span style="color:${trustColor}">${trustScore.toFixed(0)}</span>${betrayalIcon}</div>
      <div class="agent-hp-bar"><div class="agent-hp-fill" style="width:${hpRatio*100}%;background:${hpColor}"></div></div>
    `;

    // Prepend sprite
    card.insertBefore(spriteCanvas, card.firstChild);

    card.addEventListener("click", () => {
      selectedAgent = selectedAgent === a.agent_id ? null : a.agent_id;
      if (gridData) drawMap(gridData);
      refreshAgentList();
    });

    list.appendChild(card);
  }
}

// ─── DATA FETCHERS ───
async function refreshStatus() {
  try {
    const res = await fetch("/world/status");
    if (!res.ok) return;
    const data = await res.json();
    if ($("tick")) $("tick").textContent = data.tick ?? "-";
    if ($("alive")) $("alive").textContent = data.alive_agents ?? "-";
    if ($("avgDeg")) $("avgDeg").textContent = data.avg_degradation != null ? (data.avg_degradation * 100).toFixed(1) + "%" : "-";
  } catch {}

  // Fetch market data
  try {
    const res = await fetch("/world/market");
    if (!res.ok) return;
    const data = await res.json();
    if ($("marketPrice")) $("marketPrice").textContent = data.market_price != null ? data.market_price.toFixed(2) + "x" : "1.0x";
  } catch {}
}

async function refreshGrid() {
  try {
    const res = await fetch("/world/grid");
    if (!res.ok) return;
    gridData = await res.json();
    if (gridData.agents) {
      for (const a of gridData.agents) {
        if (a.name) agentNames[a.agent_id] = a.name;
      }
    }
    drawMap(gridData);
    refreshAgentList();
  } catch {}
}

async function refreshEvents() {
  try {
    const res = await fetch("/admin/events?limit=100");
    if (!res.ok) return;
    const data = await res.json();
    const items = data.items || [];
    if (!items.length) return;

    for (const ev of items) {
      if (ev.type === "AGENT_ENTERED" && ev.payload) {
        const aid = ev.payload.agent_id || ev.agent_id;
        const name = ev.payload.name;
        if (aid && name) agentNames[aid] = name;
      }
    }

    const feed = $("feed");
    if (!feed) return;
    feed.innerHTML = "";
    let tc = 0, cc = 0;

    const filtered = items.filter(ev =>
      ev.type !== "TICK_RESOLVED" && ev.type !== "TICK_DONE" && ev.type !== "ACTION_SUBMITTED"
    );

    for (const ev of filtered.reverse()) {
      if (ev.type === "TRADE_COMPLETED") tc++;
      if (ev.type === "COMBAT_HIT" || ev.type === "COMBAT_KILL") cc++;

      const div = document.createElement("div");
      const evCls = ev.type.includes("TRADE") ? "ev-trade" :
                    ev.type.includes("DIED") || ev.type.includes("KILL") ? "ev-death" :
                    ev.type.includes("COMBAT") ? "ev-combat" :
                    ev.type.includes("ENTERED") ? "ev-enter" : "";
      div.className = `event ${evCls}`;

      const ts = ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : "";
      const agentName = ev.agent_id ? (agentNames[ev.agent_id] || ev.agent_id.slice(0, 8)) : "";

      let detail = "";
      if (ev.payload) {
        if (ev.type === "AGENT_ENTERED") detail = "joined the oasis";
        else if (ev.type === "AGENT_MOVED") detail = `moved to (${ev.payload.x},${ev.payload.y})`;
        else if (ev.type === "COMBAT_HIT") {
          const tgt = agentNames[ev.payload.target_id] || (ev.payload.target_id || "").slice(0, 8);
          detail = `hit ${tgt} for ${ev.payload.damage} dmg`;
        }
        else if (ev.type === "COMBAT_KILL") {
          const tgt = agentNames[ev.payload.target_id] || (ev.payload.target_id || "").slice(0, 8);
          detail = `killed ${tgt}!`;
        }
        else if (ev.type === "TRADE_COMPLETED") detail = `traded ${ev.payload.amount} res`;
        else if (ev.type === "AGENT_GATHERED") detail = `+${ev.payload.amount} res`;
        else if (ev.type === "AGENT_DAMAGED") detail = `took ${ev.payload.amount} dmg`;
        else if (ev.type === "AGENT_DIED") detail = `died at (${ev.payload.x},${ev.payload.y})`;
        else detail = ev.type;
      }

      div.innerHTML = `
        <div class="event-content"><span class="event-type">${agentName}</span> ${detail}</div>
        <div class="event-time">t=${ev.tick} ${ts}</div>
      `;
      feed.appendChild(div);
    }
    tradeCount += tc;
    combatCount += cc;
    if ($("trades")) $("trades").textContent = tradeCount;
    if ($("combats")) $("combats").textContent = combatCount;
    feed.scrollTop = feed.scrollHeight;
  } catch {}
}

async function refreshDQN() {
  try {
    const res = await fetch("/admin/events?limit=200");
    if (!res.ok) return;
    const data = await res.json();
    const dqnEvents = (data.items || []).filter(e => e.type === "DQN_LOG");
    if (!dqnEvents.length) return;

    const d = dqnEvents[0].payload;
    const eps = d.epsilon != null ? d.epsilon.toFixed(3) : "?";
    const steps = d.step_count || 0;
    const totalR = d.total_reward != null ? d.total_reward.toFixed(1) : "0";
    const epCount = (d.episode_rewards || []).length;
    const mistCount = (d.mistakes || []).length;

    const dqnInfo = $("dqnInfo");
    if (dqnInfo) {
      dqnInfo.innerHTML =
        `Steps: <b>${steps}</b> | Eps: <b>${epCount}</b><br>` +
        `\u03B5: <b>${eps}</b> | Reward: <b>${totalR}</b><br>` +
        `Mistakes: <b>${mistCount}</b>`;
    }

    const mc = $("dqnMistakes");
    if (mc) {
      mc.innerHTML = "";
      for (const m of (d.mistakes || []).slice(-6)) {
        const div = document.createElement("div");
        div.className = "mistake";
        div.innerHTML = `t=${m.tick}: <span class="bad">${m.bad_action}</span> &rarr; <span class="fix">${m.correction}</span>`;
        mc.appendChild(div);
      }
    }

    const rewards = d.episode_rewards || [];
    const losses = d.loss_history || [];
    drawRewardChart(rewards.length >= 2 ? rewards : losses);
  } catch {}
}

function drawRewardChart(rewards) {
  const rc = $("rewardChart");
  if (!rc) return;
  const ctx = rc.getContext("2d");
  const w = rc.width, h = rc.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#0f0a04";
  ctx.fillRect(0, 0, w, h);
  if (!rewards || rewards.length < 2) return;

  const min = Math.min(...rewards);
  const max = Math.max(...rewards);
  const range = max - min || 1;
  const step = w / (rewards.length - 1);

  ctx.strokeStyle = "#ffd866";
  ctx.lineWidth = 2;
  ctx.beginPath();
  rewards.forEach((r, i) => {
    const x = i * step;
    const y = h - ((r - min) / range) * (h - 10) - 5;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = "#ffd866";
  rewards.forEach((r, i) => {
    const x = i * step;
    const y = h - ((r - min) / range) * (h - 10) - 5;
    ctx.fillRect(x - 1, y - 1, 3, 3);
  });
}

// ─── CONTROLS ───
const forceTickBtn = $("forceTick");
if (forceTickBtn) {
  forceTickBtn.addEventListener("click", async () => {
    await fetch("/admin/tick", { method: "POST" });
    await refreshAll();
  });
}

const finalizeBtn = $("finalizeBtn");
if (finalizeBtn) {
  finalizeBtn.addEventListener("click", async () => {
    if (!confirm("Finalize game and RESET world? This will clear all agents and start fresh.")) return;

    // Finalize current game
    const resFinalize = await fetch("/admin/finalize-game", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const dataFinalize = await resFinalize.json();

    // Reset world
    const resReset = await fetch("/admin/reset-world", {
      method: "POST"
    });
    const dataReset = await resReset.json();

    alert(`Game finalized at tick ${dataFinalize.tick}. Survivors: ${dataFinalize.survivors}.\n\nWorld has been reset! Click "Spawn Demo Agents" to start new game.`);
    await refreshAll();
  });
}

// Add Spawn Demo Agents button functionality
async function spawnDemoAgents() {
  const res = await fetch("/admin/spawn-demo-agents?count=5", {
    method: "POST"
  });
  const data = await res.json();
  alert(`Spawned ${data.spawned} demo agents!\n\nAgents will now explore, trade, and fight in the world. Watch the Live Events panel!`);
  await refreshAll();
}

// Auto-spawn demo agents if world is empty (for judges' convenience)
async function checkAndAutoSpawn() {
  try {
    const res = await fetch("/world/status");
    const data = await res.json();

    // If no agents and tick is low (fresh world), auto-spawn
    if (data.alive_agents === 0 && data.tick < 10) {
      console.log("World is empty - auto-spawning demo agents for demo...");
      await spawnDemoAgents();
    }
  } catch (e) {
    console.error("Could not check world status:", e);
  }
}

// Expose spawn function globally so it can be called from console or button
window.spawnDemoAgents = spawnDemoAgents;

// Zone popup close handlers
const zoneClose = $("zonePopupClose");
if (zoneClose) zoneClose.addEventListener("click", closeZonePopup);
const zoneOverlay = $("zoneOverlay");
if (zoneOverlay) zoneOverlay.addEventListener("click", closeZonePopup);

// Layer buttons
document.querySelectorAll(".layer-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    currentLayer = btn.dataset.layer;
    document.querySelectorAll(".layer-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    if (gridData) drawMap(gridData);
  });
});

// ─── MAIN LOOP ───
async function refreshAll() {
  await Promise.all([refreshStatus(), refreshGrid(), refreshEvents(), refreshDQN()]);
}

async function loop() {
  await refreshAll();
  setTimeout(loop, 2000);
}

// Init
setupZones();
checkAndAutoSpawn();  // Auto-spawn agents if world is empty
loop();
