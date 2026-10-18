const LANGS = [
  ["zh-CN", "简体中文"], ["zh-TW", "繁體中文"], ["en", "英语"], ["ja", "日语"],
  ["ko", "韩语"], ["ru", "俄语"], ["uk", "乌克兰语"], ["es", "西班牙语"],
  ["fr", "法语"], ["de", "德语"], ["pt", "葡萄牙语"], ["it", "意大利语"],
  ["pl", "波兰语"], ["tr", "土耳其语"], ["ar", "阿拉伯语"], ["th", "泰语"],
  ["vi", "越南语"], ["id", "印尼语"], ["nl", "荷兰语"],
];

const LINKS = {
  bingus: "https://github.com/CowboyBingus/BingusSharedLoader/releases",
  arsenal: "https://github.com/Orbit-Studios/hd2arsenal-release/releases",
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let CFG = null;
let STATUS = null;
let glossary = [];

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function toast(msg, bad) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (bad ? " bad" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.className = "toast"), 3200);
}

async function api(path, opts) {
  const res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts));
  let data = null;
  try { data = await res.json(); } catch (e) { data = { ok: false, error: "HTTP " + res.status }; }
  if (!res.ok && !data.error) data.error = "HTTP " + res.status;
  return data;
}

function fillLangs() {
  const html = LANGS.map(([v, n]) => `<option value="${v}">${n}（${v}）</option>`).join("");
  $("#read-language").innerHTML = html;
  $("#send-language").innerHTML = html;
  $("#test-target").innerHTML = html;
  $("#say-target").innerHTML = html;
}

function applyConfig(cfg) {
  CFG = cfg;
  $("#read-language").value = cfg.read_language || "zh-CN";
  $("#send-language").value = cfg.send_language || "en";
  $("#tag-mode").value = cfg.tag_mode || "source";
  $("#inbound-render").value = cfg.inbound_render || "line";
  $("#inbound").checked = !!cfg.inbound;
  $("#outbound").checked = !!cfg.outbound;
  $("#prefix").value = cfg.prefix || "auto";
  $("#system-names").value = (cfg.system_names || []).join("\n");
  $("#system-prefixes").value = (cfg.system_prefixes || []).join("\n");
  $("#chat-log").checked = !!cfg.chat_log;
  $("#ime-guard").checked = cfg.ime_guard !== false;
  $("#api-base").value = (cfg.api || {}).base_url || "";
  $("#api-model").value = (cfg.api || {}).model || "";
  $("#api-key").value = "";
  $("#api-hint").textContent = (cfg.api || {}).key_set
    ? "已保存 Key：" + ((cfg.api || {}).key_hint || "已设置") + "（留空保存不会覆盖）"
    : "还没有保存 API Key。";
  $("#test-target").value = cfg.read_language || "zh-CN";
  $("#say-target").value = cfg.send_language || "en";
  $("#stat-pair").textContent = (cfg.read_language || "?") + " / " + (cfg.send_language || "?");
}

async function loadConfig() {
  const d = await api("/api/config");
  if (d.ok) applyConfig(d.config);
}

function collectConfig() {
  return {
    read_language: $("#read-language").value,
    send_language: $("#send-language").value,
    tag_mode: $("#tag-mode").value,
    inbound_render: $("#inbound-render").value,
    inbound: $("#inbound").checked,
    outbound: $("#outbound").checked,
    prefix: $("#prefix").value.trim() || "auto",
    system_names: $("#system-names").value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean),
    system_prefixes: $("#system-prefixes").value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean),
    chat_log: $("#chat-log").checked,
    ime_guard: $("#ime-guard").checked,
    api: {
      base_url: $("#api-base").value.trim(),
      model: $("#api-model").value.trim(),
      key: $("#api-key").value.trim(),
    },
  };
}

async function saveConfig() {
  const body = collectConfig();
  const d = await api("/api/config", { method: "POST", body: JSON.stringify({ config: body }) });
  if (d.ok) {
    applyConfig(d.config);
    toast("已保存；游戏内 2 秒内生效，无需重启");
  } else {
    toast(d.error || "保存失败", true);
  }
}

function fmtTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}

function dirBadge(d) {
  return d === "out" ? '<span class="dir out">出站</span>' : '<span class="dir in">入站</span>';
}

function renderRecent(rows) {
  const body = $("#recent-body");
  if (!rows || !rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="muted">暂无记录 —— 先在右边做一次快速测试</td></tr>';
    return;
  }
  body.innerHTML = rows.map((r) => `<tr>
    <td class="mono">${fmtTime(r.ts)}</td>
    <td>${dirBadge(r.direction)}</td>
    <td class="clip">${esc(r.original)}</td>
    <td class="clip">${esc(r.translated || (r.error || ""))}</td>
    <td class="mono">${r.ms || ""}</td>
  </tr>`).join("");
}

async function loadRecent() {
  const d = await api("/api/history?limit=8");
  if (d.ok) renderRecent(d.rows);
}

async function loadStatus() {
  const d = await api("/api/status");
  if (!d.ok) return;
  STATUS = d;
  const svc = $("#pill-service");
  svc.className = "pill on";
  svc.innerHTML = "<i></i>翻译服务";

  const game = $("#pill-game");
  game.className = "pill " + (d.game_running ? "on" : "off");
  game.innerHTML = "<i></i>" + (d.game_running ? "游戏运行中" : "游戏未运行");

  const mod = $("#pill-mod");
  const fresh = d.log_mtime && Date.now() / 1000 - d.log_mtime < 60;
  mod.className = "pill " + (d.mod_installed ? (fresh ? "on" : "") : "off");
  mod.innerHTML = "<i></i>" + (d.mod_installed ? (fresh ? "Mod 已加载" : "Mod 已安装") : "Mod 未安装");

  $("#pill-port").textContent = "127.0.0.1:" + (d.port || "");
  const b = d.branding || {};
  $("#credit").textContent = "by " + (b.author || "XD2233XD") +
    (b.watermark_id ? " · " + b.watermark_id : "") +
    (b.build_id ? " · build " + b.build_id : "");
  $("#stat-today").textContent = d.stats.today;
  $("#stat-ok").textContent = d.stats.today_ok;
  $("#stat-total").textContent = "累计 " + d.stats.total + " 条";
  $("#stat-latency").textContent = d.stats.avg_ms ? d.stats.avg_ms + "ms" : "–";
  renderInstallStatus(d);
}

function renderInstallStatus(d) {
  const rows = [
    ["游戏目录", d.game || "未找到"],
    ["Arsenal", d.arsenal || "未安装"],
    ["Arsenal mods", d.arsenal_mods || "未找到"],
    ["Bingus 加载器", d.bingus ? "已安装" : "未安装"],
    ["本 Mod", d.mod_installed ? "已安装" : "未安装"],
    ["手动槽位", (d.manual && (d.manual.mod ? "mod=patch_1" : "") + (d.manual.loader ? " loader=patch_2" : "")) || "未使用"],
    ["输入法守护", d.ime ? (d.ime.active ? "游戏前台，已切英文模式" : (d.ime.running ? "待机（游戏不在前台）" : "关闭")) : "未知"],
    ["Mod 日志", d.log || ""],
    ["安装包", d.zip_exists ? d.zip : "未构建"],
  ];
  $("#install-status").innerHTML = rows.map(([k, v]) => {
    let badge = "";
    if (k === "Bingus 加载器" || k === "本 Mod") badge = d[k === "Bingus 加载器" ? "bingus" : "mod_installed"] ? ' <span class="badge ok">OK</span>' : ' <span class="badge bad">缺</span>';
    return `<dt>${k}</dt><dd>${esc(v)}${badge}</dd>`;
  }).join("");
}

async function sendToGame() {
  const text = $("#say-input").value.trim();
  if (!text) return toast("先输入一句话", true);
  const box = $("#say-result");
  box.classList.remove("hidden", "ok", "bad");
  box.textContent = "翻译中…";
  const d = await api("/api/send", {
    method: "POST",
    body: JSON.stringify({
      text,
      target: $("#say-target").value,
      force: $("#say-force").checked,
    }),
  });
  if (!d.ok) {
    box.classList.add("bad");
    box.textContent = "失败：" + (d.error || "未知错误");
    return;
  }
  box.classList.add("ok");
  box.textContent = `已翻译并排队：${d.queued}\n等待游戏取走…`;
  for (let i = 0; i < 32; i++) {
    await new Promise((r) => setTimeout(r, 250));
    const s = await api("/api/send/status");
    if (s.ok && !s.pending) {
      box.textContent = `已交给游戏：${d.queued}\n（日志里应出现 OUTBOX send → MSEND ok）`;
      $("#say-input").value = "";
      loadRecent();
      return;
    }
  }
  box.textContent = `已排队但游戏还没取走：${d.queued}\n确认游戏在前台、没有打开聊天框；mod 会在可发送时取走。`;
}

async function runTest() {
  const text = $("#test-input").value.trim();
  if (!text) return toast("先输入一句话", true);
  const btn = $("#btn-test");
  btn.disabled = true;
  btn.textContent = "翻译中…";
  const d = await api("/api/test", {
    method: "POST",
    body: JSON.stringify({ text, target: $("#test-target").value }),
  });
  btn.disabled = false;
  btn.textContent = "翻译";
  const box = $("#test-result");
  box.classList.remove("hidden", "ok", "bad");
  if (!d.ok) {
    box.classList.add("bad");
    box.textContent = "失败：" + (d.error || "未知错误");
    return;
  }
  const r = d.result || {};
  if (r.skip) {
    box.classList.add("ok");
    box.textContent = `跳过（${r.reason}）· 源语言=${r.lang || "?"} · ${r.ms}ms`;
  } else {
    box.classList.add("ok");
    box.textContent = `${r.content}\n\n源语言 ${r.lang || "?"} · ${r.ms}ms`;
  }
  loadRecent();
}

function renderGlossary() {
  const body = $("#glossary-body");
  if (!glossary.length) {
    body.innerHTML = '<tr><td colspan="3" class="muted">还没有术语。可先加：Stratagem → 战备</td></tr>';
    return;
  }
  body.innerHTML = glossary.map((g, i) => `<tr>
    <td><input data-g="src" data-i="${i}" value="${esc(g.src)}"></td>
    <td><input data-g="dst" data-i="${i}" value="${esc(g.dst)}"></td>
    <td><button class="ghost" data-del="${i}">删除</button></td>
  </tr>`).join("");
}

function bindGlossary() {
  document.addEventListener("input", (e) => {
    const el = e.target;
    if (!el.dataset || !el.dataset.g) return;
    const i = +el.dataset.i;
    if (glossary[i]) glossary[i][el.dataset.g] = el.value;
  });
  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-del]");
    if (!el) return;
    glossary.splice(+el.dataset.del, 1);
    renderGlossary();
  });
}

async function loadGlossary() {
  const d = await api("/api/glossary");
  if (d.ok) { glossary = d.items || []; renderGlossary(); }
}

async function saveGlossary() {
  const d = await api("/api/glossary", {
    method: "POST",
    body: JSON.stringify({ items: glossary.filter((g) => g.src && g.dst) }),
  });
  if (d.ok) { glossary = d.items; renderGlossary(); toast("术语表已保存"); }
  else toast(d.error || "保存失败", true);
}

async function loadHistory() {
  const dir = $("#history-direction").value;
  const d = await api("/api/history?limit=120" + (dir ? "&direction=" + dir : ""));
  const body = $("#history-body");
  if (!d.ok) return;
  if (!d.rows.length) {
    body.innerHTML = '<tr><td colspan="7" class="muted">暂无记录</td></tr>';
    return;
  }
  body.innerHTML = d.rows.map((r) => `<tr>
    <td class="mono">${fmtTime(r.ts)}</td>
    <td>${dirBadge(r.direction)}</td>
    <td class="clip">${esc(r.name)}</td>
    <td class="mono">${esc(r.src_lang)}</td>
    <td class="clip" title="${esc(r.original)}">${esc(r.original)}</td>
    <td class="clip" title="${esc(r.translated)}">${esc(r.translated || r.error || "")}</td>
    <td class="mono">${r.ms || ""}</td>
  </tr>`).join("");
}

async function loadLogs() {
  const src = $("#log-source").value;
  const d = await api("/api/logs?source=" + src + "&tail=300");
  $("#log-view").textContent = d.ok ? (d.text || "（空）") : (d.error || "读取失败");
}

async function prepareInstall() {
  const d = await api("/api/install/prepare", { method: "POST", body: "{}" });
  if (d.ok) toast("已复制到：" + d.staged);
  else toast(d.error || "准备失败", true);
}

async function manualInstall(action) {
  const box = $("#install-output");
  box.classList.remove("hidden");
  box.textContent = "执行中…";
  const d = await api("/api/install/manual", { method: "POST", body: JSON.stringify({ action }) });
  box.textContent = d.output || d.error || "";
  toast(d.ok ? (action === "install" ? "部署完成，启动游戏后看日志" : "已卸载") : "失败：" + (d.error || "见输出"), !d.ok);
  loadStatus();
}

async function openTarget(what) {
  const d = await api("/api/install/open", { method: "POST", body: JSON.stringify({ what }) });
  if (!d.ok) toast(d.detail || d.error || "打不开", true);
}

function switchTab(name) {
  $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + name));
  if (name === "history") loadHistory();
  if (name === "logs") loadLogs();
  if (name === "install") loadStatus();
  if (name === "glossary") loadGlossary();
}

function init() {
  fillLangs();
  bindGlossary();

  $$(".tabs button").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
  $("#btn-save").addEventListener("click", saveConfig);
  $("#btn-reload").addEventListener("click", loadConfig);
  $("#btn-test").addEventListener("click", runTest);
  $("#btn-say").addEventListener("click", sendToGame);
  $("#say-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) sendToGame();
  });
  $("#test-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) runTest();
  });
  $("#btn-glossary-add").addEventListener("click", () => {
    const src = $("#glossary-src").value.trim();
    const dst = $("#glossary-dst").value.trim();
    if (!src || !dst) return toast("术语和译名都要填", true);
    glossary.push({ src, dst });
    $("#glossary-src").value = "";
    $("#glossary-dst").value = "";
    renderGlossary();
  });
  $("#btn-glossary-save").addEventListener("click", saveGlossary);
  $("#btn-history-refresh").addEventListener("click", loadHistory);
  $("#history-direction").addEventListener("change", loadHistory);
  $("#btn-log-refresh").addEventListener("click", loadLogs);
  $("#log-source").addEventListener("change", loadLogs);
  $("#btn-prepare").addEventListener("click", prepareInstall);
  $("#btn-manual-install").addEventListener("click", () => manualInstall("install"));
  $("#btn-manual-uninstall").addEventListener("click", () => manualInstall("uninstall"));
  $$("[data-open]").forEach((b) => b.addEventListener("click", () => openTarget(b.dataset.open)));
  $("#btn-open-bingus").addEventListener("click", () => window.open(LINKS.bingus, "_blank"));
  $("#btn-open-arsenal").addEventListener("click", () => window.open(LINKS.arsenal, "_blank"));
  $("#btn-borderless").addEventListener("click", async () => {
    const d = await api("/api/window/borderless", { method: "POST", body: "{}" });
    toast(d.detail || (d.ok ? "已修改" : "失败"), !d.ok);
  });

  loadConfig().then(loadStatus).then(loadRecent);
  setInterval(loadStatus, 3000);
  setInterval(() => { if ($("#tab-overview").classList.contains("active")) loadRecent(); }, 5000);
}

document.addEventListener("DOMContentLoaded", init);
