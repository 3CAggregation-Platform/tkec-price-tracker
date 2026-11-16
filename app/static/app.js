// 家電比價頁面：資料來自 /api/compare、/api/history/{型號}（見 app/web.py）
// 商品名稱等文字一律用 textContent 放進頁面，不用 innerHTML，避免資料裡的 HTML 被執行

const PLATFORMS = [
  { key: "tk3c", label: "燦坤", color: "--c-tk3c" },
  { key: "pchome", label: "PChome", color: "--c-pchome" },
  { key: "yahoo", label: "Yahoo", color: "--c-yahoo" },
];
const CATEGORIES = ["全部", "冰箱", "洗衣機", "電視", "氣炸鍋", "掃地機器人"];

const state = { category: "全部", q: "", sort: "gap", date: "", items: [] };
const $ = (id) => document.getElementById(id);
const money = (n) => (n == null ? "" : "$" + Number(n).toLocaleString("zh-TW"));
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "text") node.textContent = v;
    else if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c);
  return node;
}

function safeUrl(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch {
    return null;
  }
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(res.status === 429 ? "請求太頻繁，請稍後再試" : "讀取資料失敗（" + res.status + "）");
  return res.json();
}

// ===== 列表 =====

function renderCats() {
  const box = $("cats");
  box.replaceChildren(
    ...CATEGORIES.map((c) => {
      const b = el("button", { class: "chip", type: "button", "aria-pressed": String(c === state.category), text: c });
      b.addEventListener("click", () => {
        state.category = c;
        renderCats();
        renderRows();
      });
      return b;
    })
  );
}

function visibleItems() {
  const q = state.q.trim().toLowerCase();
  let items = state.items.filter(
    (it) =>
      (state.category === "全部" || it.category === state.category) &&
      (!q || it.model.toLowerCase().includes(q) || (it.brand || "").toLowerCase().includes(q))
  );
  const cmp = {
    gap: (a, b) => (b.gap_ratio || 0) - (a.gap_ratio || 0) || a.min_price - b.min_price,
    low: (a, b) => a.min_price - b.min_price,
    model: (a, b) => a.model.localeCompare(b.model),
  }[state.sort];
  return items.sort(cmp);
}

function renderRows() {
  const items = visibleItems();
  const rows = items.map((it) => {
    const cells = PLATFORMS.map((p) => {
      const offer = it.prices[p.key];
      if (!offer) return el("td", { class: "num none", text: "—" });
      const isBest = Object.keys(it.prices).length > 1 && offer.price === it.min_price;
      return el("td", { class: "num" }, [el("span", { class: isBest ? "best" : "", text: money(offer.price) })]);
    });
    const platforms = Object.keys(it.prices).length;
    const gapText = platforms > 1 ? (it.gap_ratio * 100).toFixed(0) + "%" : "只有 1 家";
    const tr = el("tr", { tabindex: "0" }, [
      el("td", {}, [el("div", { class: "model", text: it.model }), el("div", { class: "brand", text: it.brand || "" })]),
      el("td", { class: "hide-sm", text: it.category }),
      ...cells,
      el("td", { class: "num" + (platforms > 1 ? " gap" : " none"), text: gapText }),
    ]);
    const open = () => openDetail(it);
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open();
      }
    });
    return tr;
  });
  $("rows").replaceChildren(...rows);
  $("empty").hidden = items.length > 0;
  const multi = items.filter((it) => Object.keys(it.prices).length > 1).length;
  $("meta").textContent = `${state.date} 的價格・${items.length} 個型號（${multi} 個可跨平台比價）`;
}

async function loadCompare() {
  $("meta").textContent = "載入中…";
  try {
    const data = await getJSON("/api/compare?date=" + encodeURIComponent(state.date));
    state.items = data.items;
    renderRows();
  } catch (e) {
    $("meta").textContent = e.message;
  }
}

// ===== 單一型號走勢 =====

let chart;

async function openDetail(item) {
  $("dlg-title").textContent = item.model;
  $("dlg-brand").textContent = [item.brand, item.category].filter(Boolean).join("・");
  $("offers").replaceChildren();
  $("dlg").showModal();

  let data;
  try {
    data = await getJSON("/api/history/" + encodeURIComponent(item.model));
  } catch (e) {
    $("offers").replaceChildren(el("div", { class: "none", text: e.message }));
    return;
  }

  const dates = [...new Set(data.history.map((h) => h.date))].sort();
  const byKey = {};
  for (const h of data.history) (byKey[h.platform] ||= {})[h.date] = h;

  const text = cssVar("--muted");
  const grid = cssVar("--border");
  const datasets = PLATFORMS.filter((p) => byKey[p.key]).map((p) => ({
    label: p.label,
    data: dates.map((d) => byKey[p.key][d]?.price ?? null),
    borderColor: cssVar(p.color),
    backgroundColor: cssVar(p.color),
    borderWidth: 2,
    pointRadius: 3,
    spanGaps: true,
    stepped: "before",
  }));

  if (chart) chart.destroy();
  chart = new Chart($("chart"), {
    type: "line",
    data: { labels: dates.map((d) => d.slice(5).replace("-", "/")), datasets },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: text, usePointStyle: true, boxHeight: 6 } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label} ${money(c.parsed.y)}` } },
      },
      scales: {
        x: { ticks: { color: text }, grid: { display: false } },
        y: { ticks: { color: text, callback: (v) => money(v) }, grid: { color: grid } },
      },
    },
  });

  // 最新一天各平台的賣場
  const offers = PLATFORMS.filter((p) => byKey[p.key]).map((p) => {
    const days = Object.keys(byKey[p.key]).sort();
    const last = byKey[p.key][days[days.length - 1]];
    const url = safeUrl(last.url);
    return el("div", { class: "offer" }, [
      el("div", {}, [el("span", { class: "dot", style: `background:var(${p.color})` }), document.createTextNode(p.label)]),
      el("div", { class: "p", text: money(last.price) }),
      el("div", { class: "n", title: last.name || "", text: `${last.date.slice(5).replace("-", "/")}・${last.name || ""}` }),
      url ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer nofollow", text: "前往賣場 ↗" }) : "",
    ]);
  });
  $("offers").replaceChildren(...offers);
}

// ===== 初始化 =====

async function init() {
  renderCats();
  $("q").addEventListener("input", (e) => {
    state.q = e.target.value;
    renderRows();
  });
  $("sort").addEventListener("change", (e) => {
    state.sort = e.target.value;
    renderRows();
  });
  $("date").addEventListener("change", (e) => {
    state.date = e.target.value;
    loadCompare();
  });
  $("dlg-close").addEventListener("click", () => $("dlg").close());
  $("dlg").addEventListener("click", (e) => {
    if (e.target === $("dlg")) $("dlg").close();
  });

  try {
    const dates = await getJSON("/api/dates");
    if (!dates.length) {
      $("meta").textContent = "目前沒有資料";
      return;
    }
    $("date").replaceChildren(...dates.map((d) => el("option", { value: d, text: d })));
    state.date = dates[0];
    await loadCompare();
  } catch (e) {
    $("meta").textContent = e.message;
  }
}

init();
