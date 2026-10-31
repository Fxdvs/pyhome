// The launcher's page. It only draws: everything that touches the computer is a call to the
// Python backend (launcher/api.py). Every call goes through `backend`, so a different shell
// later (Tauri, a browser) changes this object only.
"use strict";

const backend = {
  call(name, ...args) {
    return window.pywebview.api[name](...args);
  },
};

// how often the selected app's output and every app's state are asked for, in milliseconds
const OUTPUT_MS = 250;
const APPS_MS = 1000;
// lines kept per app in the page, the same as the backend keeps
const LIMIT = 5000;

const STATE = { running: "beží", stopped: "zastavený", exited: "chyba" };

let apps = [];
let selected = "server";
// per app: {lines: [html], last: the newest line number the page has}
const consoles = {};

const $ = (id) => document.getElementById(id);

function esc(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

// ANSI colors to the theme's classes; any other escape code is dropped

const ANSI_COLORS = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"];
const ESCAPE = /\x1b\[([0-9;?]*)([A-Za-z])|\x1b\][^\x07]*\x07|\x1b./g;

function ansiToHtml(text) {
  let html = "";
  let color = null;
  let bold = false;
  let last = 0;
  const flush = (part) => {
    if (!part) return;
    const classes = [color && `ansi-${color}`, bold && "ansi-bold"].filter(Boolean);
    html += classes.length ? `<span class="${classes.join(" ")}">${esc(part)}</span>` : esc(part);
  };
  text = text.replace(/\r/g, "");
  for (const match of text.matchAll(ESCAPE)) {
    flush(text.slice(last, match.index));
    last = match.index + match[0].length;
    if (match[2] !== "m") continue;
    for (const code of (match[1] || "0").split(";").map(Number)) {
      if (code === 0) { color = null; bold = false; }
      else if (code === 1) bold = true;
      else if (code === 22) bold = false;
      else if (code === 39) color = null;
      else if (code >= 30 && code <= 37) color = ANSI_COLORS[code - 30];
      else if (code === 90) color = "gray";
      else if (code >= 91 && code <= 97) color = ANSI_COLORS[code - 90];
    }
  }
  flush(text.slice(last));
  return html;
}

// the clear command prints a clear screen code (or a form feed on windows)
function clearsScreen(text) {
  return text.includes("\x1b[2J") || text.includes("\f");
}

// small helpers

function plural(n, one, few, many) {
  return n === 1 ? one : n >= 2 && n <= 4 ? few : many;
}

function uptime(seconds) {
  if (seconds == null) return "";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 1) return "práve spustené";
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours} h ${minutes % 60} min` : `${minutes} min`;
}

function stateLabel(status) {
  if (status.state === "exited") return `chyba (kód ${status.code})`;
  return STATE[status.state];
}

function current() {
  return apps.find((app) => app.key === selected) || apps[0];
}

// the sidebar and the header

function renderApps() {
  const list = $("apps");
  let html = "";
  let group = "";
  for (const app of apps) {
    const name = app.kind === "server" ? "Server" : "Klienti";
    if (name !== group) {
      group = name;
      html += `<div class="px-2 pb-1 pt-2.5 text-[11px] font-semibold text-faint">${group}</div>`;
    }
    const active = app.key === selected ? "bg-accent-soft" : "hover:bg-white/5";
    const problem = app.error || app.note;
    html += `<div class="flex items-center gap-2 rounded-lg pl-2 ${active}" data-key="${esc(app.key)}">
      <input type="checkbox" class="accent-accent" aria-label="Spúšťať ${esc(app.name)}" ${app.checked ? "checked" : ""} ${app.error ? "disabled" : ""}>
      <button type="button" class="grid min-w-0 flex-1 grid-cols-[10px_minmax(0,1fr)_auto] items-center gap-2.5 py-2 pr-2.5 text-left">
        <span class="dot dot-${app.status.state}"></span>
        <span class="min-w-0">
          <span class="block truncate font-semibold">${esc(app.name)}</span>
          <span class="block truncate text-[11.5px] ${problem ? "text-warn" : "text-muted"}">${esc(app.error || app.note || app.sub)}</span>
        </span>
        <span class="text-[11px] text-muted">${esc(stateLabel(app.status))}</span>
      </button>
    </div>`;
  }
  list.innerHTML = html;
}

function renderHeader() {
  const app = current();
  if (!app) return;
  const running = app.status.state === "running";
  $("title").textContent = app.name;
  $("meta").textContent = [app.meta, running ? uptime(app.status.uptime) : ""].filter(Boolean).join(" · ");
  $("chips").innerHTML = app.chips
    .map((chip) => `<span class="rounded-full border border-edge-soft bg-hi px-2.5 py-0.5 text-[11px] text-muted">${esc(chip)}</span>`)
    .join("");
  $("toggle").textContent = running ? "Zastaviť" : "Spustiť";
  $("toggle").disabled = Boolean(app.error);
  $("edit").disabled = app.error === "invalid JSON";
  $("command").disabled = !running;
  $("command").placeholder = running ? "príkaz, napríklad do kuch turn_on alebo help" : "aplikácia nebeží";

  const server = apps.find((a) => a.kind === "server");
  const chip = $("serverChip");
  const on = server.status.state === "running";
  chip.textContent = `Server ${server.name} ${on ? "beží" : stateLabel(server.status)} · ${server.chips.join(" · ")}`;
  chip.className = on
    ? "rounded-full border border-ok/25 bg-ok/12 px-2.5 py-0.5 text-[11px] text-ok"
    : "rounded-full border border-edge-soft bg-hi px-2.5 py-0.5 text-[11px] text-muted";
}

async function refreshApps() {
  const answer = await backend.call("apps");
  apps = answer.apps;
  if (!apps.some((app) => app.key === selected)) selected = answer.selected;
  renderApps();
  renderHeader();
}

// the console

function consoleOf(key) {
  if (!consoles[key]) consoles[key] = { lines: [], last: 0 };
  return consoles[key];
}

function renderConsole() {
  const view = $("console");
  const lines = consoleOf(selected).lines;
  view.innerHTML = lines.length
    ? lines.join("")
    : `<div class="text-faint">Zatiaľ žiadny výstup. Spusti aplikáciu tlačidlom Spustiť.</div>`;
  view.scrollTop = view.scrollHeight;
}

async function pollOutput() {
  const key = selected;
  const store = consoleOf(key);
  const answer = await backend.call("output", key, store.last);
  if (key !== selected || !answer.lines.length) return;
  const view = $("console");
  const atBottom = view.scrollHeight - view.scrollTop - view.clientHeight < 40;
  for (const [number, text] of answer.lines) {
    // two polls in flight at once (a send and the timer) bring the same lines twice
    if (number <= store.last) continue;
    if (clearsScreen(text)) store.lines = [];
    else store.lines.push(`<div class="whitespace-pre-wrap break-words">${ansiToHtml(text) || "&nbsp;"}</div>`);
    store.last = number;
  }
  if (store.lines.length > LIMIT) store.lines.splice(0, store.lines.length - LIMIT);
  view.innerHTML = store.lines.join("");
  if (atBottom) view.scrollTop = view.scrollHeight;
}

// a question with two answers, resolved true or false

function ask(text, yes) {
  return new Promise((resolve) => {
    $("dialogText").textContent = text;
    $("dialogYes").textContent = yes;
    $("dialog").hidden = false;
    $("dialogYes").focus();
    const done = (answer) => {
      $("dialog").hidden = true;
      $("dialogYes").onclick = $("dialogNo").onclick = null;
      resolve(answer);
    };
    $("dialogYes").onclick = () => done(true);
    $("dialogNo").onclick = () => done(false);
  });
}

// called by the backend when the window is closed while apps run
async function askClose() {
  const running = (await backend.call("running")).length;
  const text = `${plural(running, "Beží", "Bežia", "Beží")} ${running} ${plural(running, "aplikácia", "aplikácie", "aplikácií")}. Zastaviť ${plural(running, "ju", "ich", "ich")} a zavrieť okno?`;
  if (await ask(text, "Zastaviť a zavrieť")) await backend.call("quit");
}
window.askClose = askClose;

// form helpers

function showErrors(form, errors) {
  for (const small of form.parentElement.querySelectorAll("[data-error]")) {
    const field = small.dataset.error;
    small.textContent = errors[field] || "";
    const input = form.elements[field];
    if (input && input.setAttribute) input.setAttribute("aria-invalid", errors[field] ? "true" : "false");
  }
}

function closeSheets() {
  $("clientSheet").hidden = true;
  $("serverSheet").hidden = true;
}

// the client sheet

let clientKey = null;
let clientDevice = "";
let idTouched = false;
let serverHere = {};
// what Find servers found, and the one picked from it (null: the address was typed)
let foundServers = [];
let picked = null;

function renderDevices(devices) {
  const options = [...devices, ""];
  $("devices").innerHTML = options
    .map((device) => {
      const on = device === clientDevice;
      return `<button type="button" role="radio" aria-checked="${on}" data-device="${esc(device)}"
        class="flex-1 rounded-[7px] px-2 py-1.5 ${on ? "bg-white/15 font-semibold text-fg shadow-sm" : "text-muted"}">${esc(device || "žiadne")}</button>`;
    })
    .join("");
  $("devices").onclick = (event) => {
    const button = event.target.closest("[data-device]");
    if (!button) return;
    clientDevice = button.dataset.device;
    renderDevices(devices);
  };
}

function updateClientHints() {
  const form = $("clientForm");
  const remote = picked && !picked.here;
  const useToken = form.elements.use_server_token;
  if (remote) {
    // the token here belongs to the server in this checkout, not to that one
    useToken.disabled = true;
    useToken.checked = false;
    $("tokenHint").textContent = picked.token_required
      ? "server je na inom počítači, jeho token zadaj nižšie"
      : "server je na inom počítači a token nepožaduje";
  } else {
    useToken.disabled = !serverHere.token;
    if (!serverHere.token) useToken.checked = false;
    $("tokenHint").textContent = serverHere.token ? "" : "server na tomto počítači nemá token";
  }
  $("tokenField").hidden = useToken.checked;

  const tls = form.elements.tls;
  if (picked && !picked.tls) {
    tls.checked = false;
    tls.disabled = true;
    $("tlsHint").textContent = "tento server nemá TLS";
  } else if (remote) {
    tls.disabled = false;
    $("tlsHint").textContent = "ca.crt sa stiahne zo servera a overí podľa odtlačku vyššie";
  } else {
    $("tlsHint").textContent = serverHere.tls ? "" : "server ešte nemá certifikáty, vytvor ich v nastaveniach servera";
    tls.disabled = !serverHere.tls && !tls.checked;
  }
  updateClientFile();
}

function renderServers() {
  $("servers").innerHTML = foundServers
    .map((server, index) => {
      const on = server === picked;
      const facts = [server.here ? "na tomto počítači" : "v sieti", server.tls ? "TLS" : "bez TLS",
        server.token_required ? "token" : "bez tokenu"];
      return `<button type="button" data-server="${index}" aria-pressed="${on}"
        class="grid gap-0.5 rounded-[10px] border px-3 py-2 text-left text-[12.5px] ${on ? "border-accent/60 bg-accent-soft" : "border-edge-soft bg-hi hover:border-accent/40"}">
        <span class="font-semibold">${esc(server.name)} · ${esc(server.host)}:${server.port}</span>
        <span class="text-muted">${facts.join(" · ")}</span>
        ${server.tls ? `<code class="break-all font-mono text-[11px] text-muted">SHA-256 ${esc(server.fingerprint)}</code>` : ""}
      </button>`;
    })
    .join("");
}

async function findServers() {
  const button = $("findServers");
  button.disabled = true;
  $("findState").textContent = "Hľadám…";
  try {
    foundServers = await backend.call("find_servers");
  } finally {
    button.disabled = false;
  }
  const n = foundServers.length;
  $("findState").textContent = n
    ? `${plural(n, "Odpovedal", "Odpovedali", "Odpovedalo")} ${n} ${plural(n, "server", "servery", "serverov")}. Vyber ${plural(n, "ho", "jeden", "jeden")} a porovnaj odtlačok s tým, čo vypísal server.`
    : "Žiadny server neodpovedal. Beží? Firewall musí pustiť UDP port 50002.";
  if (picked && !foundServers.includes(picked)) picked = null;
  renderServers();
}

function pickServer(index) {
  const form = $("clientForm");
  picked = foundServers[index];
  form.elements.host.value = picked.host;
  form.elements.port.value = String(picked.port);
  if (picked.tls) form.elements.tls.checked = true;
  renderServers();
  updateClientHints();
}

// typing an address of its own drops the picked server
function serverTyped() {
  const form = $("clientForm");
  if (picked && (form.elements.host.value.trim() !== picked.host || form.elements.port.value.trim() !== String(picked.port))) {
    picked = null;
    renderServers();
    updateClientHints();
  }
}

function updateClientFile() {
  const id = $("clientForm").elements.id.value.trim() || "…";
  $("clientFile").innerHTML = clientKey
    ? `Upravuje <code class="font-mono text-[11.5px] text-fg">client/data/${esc(clientKey)}</code>.`
    : `Vytvorí <code class="font-mono text-[11.5px] text-fg">client/data/${esc(id)}.json</code>.`;
}

async function openClient(key = null) {
  closeSheets();
  const answer = await backend.call("client_form", key);
  const form = $("clientForm");
  clientKey = key;
  serverHere = answer.server;
  clientDevice = answer.fields.device;
  idTouched = Boolean(key);
  for (const name of ["name", "id", "host", "port", "token"]) form.elements[name].value = answer.fields[name];
  form.elements.use_server_token.checked = answer.fields.use_server_token;
  form.elements.tls.checked = answer.fields.tls;
  foundServers = [];
  picked = null;
  renderServers();
  $("findState").textContent = "";
  $("clientTitle").textContent = key ? "Upraviť klienta" : "Nový klient";
  $("clientSave").textContent = key ? "Uložiť" : "Vytvoriť a spustiť";
  renderDevices(answer.devices);
  showErrors(form, {});
  updateClientHints();
  $("clientSheet").hidden = false;
  form.elements.name.focus();
}

async function saveClient(event) {
  event.preventDefault();
  const form = $("clientForm");
  const fields = {
    name: form.elements.name.value,
    id: form.elements.id.value.trim(),
    device: clientDevice,
    host: form.elements.host.value,
    port: form.elements.port.value,
    use_server_token: form.elements.use_server_token.checked,
    token: form.elements.token.value,
    tls: form.elements.tls.checked,
    server: picked,
  };
  const answer = await backend.call("save_client", fields, clientKey);
  showErrors(form, answer.errors);
  if (!answer.ok) return;
  const wasNew = !clientKey;
  closeSheets();
  selected = answer.key;
  await refreshApps();
  renderConsole();
  if (wasNew) await backend.call("start", answer.key);
  else if (answer.running && (await ask("Klient beží so starým nastavením. Reštartovať ho teraz?", "Reštartovať"))) {
    await backend.call("restart", answer.key);
  }
}

// the server sheet

async function openServer() {
  closeSheets();
  const answer = await backend.call("server_form");
  const form = $("serverForm");
  for (const [name, value] of Object.entries(answer.fields)) form.elements[name].value = value;
  showErrors(form, {});
  renderTls(answer.tls);
  $("certOutput").hidden = true;
  $("serverSheet").hidden = false;
  form.elements.name.focus();
}

function renderTls(on) {
  $("tlsState").textContent = on
    ? "Zapnuté. Opätovné vytvorenie obnoví len certifikát servera. Autorita zostane, klientov netreba meniť."
    : "Vypnuté. Token a všetky správy idú sieťou ako čitateľný text.";
  $("makeCerts").textContent = on ? "Obnoviť certifikát" : "Vytvoriť certifikáty";
}

async function saveServer(event) {
  event.preventDefault();
  const form = $("serverForm");
  const fields = Object.fromEntries(["name", "port", "web_port", "token", "history_days"].map((n) => [n, form.elements[n].value]));
  const answer = await backend.call("save_server", fields);
  showErrors(form, answer.errors);
  if (!answer.ok) return;
  closeSheets();
  await refreshApps();
  if (answer.running && (await ask("Server beží so starým nastavením. Reštartovať ho teraz?", "Reštartovať"))) {
    await backend.call("restart", "server");
  }
}

async function makeCerts() {
  const button = $("makeCerts");
  button.disabled = true;
  button.textContent = "Vytváram…";
  const answer = await backend.call("make_certificates", $("certHosts").value);
  $("certOutput").textContent = answer.output;
  $("certOutput").className = $("certOutput").className.replace(/ ?ring-\S+/g, "") + (answer.ok ? "" : " ring-1 ring-bad");
  $("certOutput").hidden = false;
  button.disabled = false;
  renderTls(answer.ok || (await backend.call("server_form")).tls);
  await refreshApps();
}

// wiring

function select(key) {
  selected = key;
  backend.call("select", key);
  renderApps();
  renderHeader();
  renderConsole();
  pollOutput();
}

function wire() {
  $("apps").addEventListener("click", (event) => {
    const row = event.target.closest("[data-key]");
    if (!row) return;
    if (event.target.matches("input[type=checkbox]")) {
      backend.call("check", row.dataset.key, event.target.checked);
      return;
    }
    if (event.target.closest("button")) select(row.dataset.key);
  });
  $("toggle").addEventListener("click", async () => {
    const app = current();
    await backend.call(app.status.state === "running" ? "stop" : "start", app.key);
    refreshApps();
  });
  $("edit").addEventListener("click", () => (current().kind === "server" ? openServer() : openClient(current().key)));
  $("newClient").addEventListener("click", () => openClient());
  $("serverSettings").addEventListener("click", openServer);
  $("runChecked").addEventListener("click", async () => {
    await backend.call("run_checked");
    refreshApps();
  });
  $("stopAll").addEventListener("click", async () => {
    await backend.call("stop_all");
    refreshApps();
  });
  $("prompt").addEventListener("submit", async (event) => {
    event.preventDefault();
    const line = $("command").value.trim();
    if (!line) return;
    $("command").value = "";
    await backend.call("send", selected, line);
    pollOutput();
  });
  for (const button of document.querySelectorAll("[data-close]")) button.addEventListener("click", closeSheets);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && $("dialog").hidden) closeSheets();
  });

  const clientForm = $("clientForm");
  clientForm.addEventListener("submit", saveClient);
  clientForm.elements.name.addEventListener("input", async () => {
    if (idTouched) return;
    clientForm.elements.id.value = await backend.call("suggest_id", clientForm.elements.name.value);
    updateClientFile();
  });
  clientForm.elements.id.addEventListener("input", () => {
    idTouched = clientForm.elements.id.value !== "";
    updateClientFile();
  });
  clientForm.elements.use_server_token.addEventListener("change", updateClientHints);
  clientForm.elements.host.addEventListener("input", serverTyped);
  clientForm.elements.port.addEventListener("input", serverTyped);
  $("findServers").addEventListener("click", findServers);
  $("servers").addEventListener("click", (event) => {
    const card = event.target.closest("[data-server]");
    if (card) pickServer(Number(card.dataset.server));
  });

  $("serverForm").addEventListener("submit", saveServer);
  $("generateToken").addEventListener("click", async () => {
    $("serverForm").elements.token.value = await backend.call("generate_token");
  });
  $("makeCerts").addEventListener("click", makeCerts);
}

// polls that never overlap themselves: a slow answer delays the next ask instead of piling up
function every(ms, task) {
  const run = async () => {
    try {
      await task();
    } catch (error) {
      console.error(error);
    }
    setTimeout(run, ms);
  };
  run();
}

async function start() {
  wire();
  await refreshApps();
  selected = (await backend.call("apps")).selected;
  renderApps();
  renderHeader();
  renderConsole();
  every(OUTPUT_MS, pollOutput);
  every(APPS_MS, refreshApps);
}

// pywebview injects its api after the page loads and says so with this event
if (window.pywebview && window.pywebview.api) start();
else window.addEventListener("pywebviewready", start, { once: true });
