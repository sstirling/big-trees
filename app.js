// Big Trees of the Northeast — multi-state render + filter + modal.
// State data lives in data/{nj,pa}/trees.json. Photos under photos/{nj,pa}/{id}/.

// Feature flag — which state tabs are visible in the live build.
// PA is gated off pending permission from the Pennsylvania Forestry Association
// (see OUTREACH-PA.md). All PA code, data, and photos remain in the repo;
// re-enable by adding "pa" back to this set.
const PUBLIC_STATES = new Set(["nj"]);

const STATE_META = {
  nj: {
    code: "NJ",
    label: "New Jersey",
    possessive: "New Jersey's",
    kicker: "A field guide to New Jersey's registry",
    sub: "Every champion, heritage, and signature tree on the NJ DEP Big and Heritage Trees registry — with photos and how to find the ones you can visit.",
    sourceName: "NJ DEP Big and Heritage Trees Program",
    sourceUrl: "https://dep.nj.gov/parksandforests/conservation/big-heritage-trees/",
    rawRecordUrl: id => `https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/ArcGIS/rest/services/NJDEP_Big_and_Heritage_Trees_in_New_Jersey/FeatureServer/19/${id}`,
    detailUrl: null,
    statuses: [
      "National Champion", "Champion", "Co-Champion",
      "Heritage Champion", "Heritage", "Signature",
      "Emeritus", "Trail Tree",
    ],
    methodologyData: `
      <p>Every record comes directly from the New Jersey Department of Environmental Protection's <a href="https://dep.nj.gov/parksandforests/conservation/big-heritage-trees/" target="_blank" rel="noopener">Big and Heritage Trees Program</a>, accessed through their <a href="https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/ArcGIS/rest/services/NJDEP_Big_and_Heritage_Trees_in_New_Jersey/FeatureServer/19" target="_blank" rel="noopener">public ArcGIS FeatureServer</a>. The state registry of champion and heritage trees is nominated and measured by foresters and volunteers under a national scoring system.</p>
    `,
    methodologyStatusTerms: [
      ["National Champion", "The biggest of its species in the United States."],
      ["Champion", "The biggest of its species in New Jersey."],
      ["Co-Champion", "Tied within 5 points of the state Champion."],
      ["Heritage / Heritage Champion", "Significant for cultural or historical reasons."],
      ["Signature", "Notable specimen that doesn't top its species ranking."],
      ["Emeritus", "Once a champion; displaced by a larger tree or no longer standing. <strong>Excluded from the overall rankings on this page.</strong>"],
      ["Trail Tree", "Believed shaped by Indigenous people as a wayfinding marker."],
    ],
    methodologyPrivacy: `
      <p>Many of these trees stand on private property. We only show a street-level address and precise map pin when the owner gave NJ DEP permission to list the tree publicly (the <code>PermissionToList</code> field). When permission is absent or unknown, the address is hidden and the map is suppressed.</p>
      <p>If you visit a tree, be respectful — most are on someone's lawn. Stay on public sidewalks unless you have explicit permission.</p>
    `,
  },
  pa: {
    code: "PA",
    label: "Pennsylvania",
    possessive: "Pennsylvania's",
    kicker: "A field guide to Pennsylvania's registry",
    sub: "Every national champion, state champion, and Penn Charter tree on Pennsylvania's Big Trees registry — with photos and how to find the ones you can visit.",
    sourceName: "Pennsylvania Big Trees",
    sourceUrl: "https://www.pabigtrees.com/tree-listings",
    rawRecordUrl: id => `https://www.pabigtrees.com/tree-listings/${id}`,
    detailUrl: id => `https://www.pabigtrees.com/tree-listings/${id}`,
    creditCallout: {
      headline: "This data exists because of volunteers.",
      body: "The Pennsylvania Big Trees program is run by the <a href=\"https://paforestry.org/pa-big-trees\" target=\"_blank\" rel=\"noopener\">Pennsylvania Forestry Association</a>, a 501(c)(3) non-profit that has identified, measured, and protected the state's biggest trees for more than 50 years.",
      ctaHomeUrl: "https://www.pabigtrees.com/tree-listings",
      ctaHomeLabel: "Browse the official PA Big Trees registry",
      ctaDonateUrl: "https://buy.stripe.com/8wM14jbI5arWgH65kl",
      ctaDonateLabel: "Donate to the PA Forestry Association",
    },
    statuses: ["National Champion", "Champion", "Co-Champion", "Penn Charter", "Listed", "Retired"],
    methodologyData: `
      <p>Every record comes from <a href="https://www.pabigtrees.com/tree-listings" target="_blank" rel="noopener">Pennsylvania Big Trees</a>, a program of the <a href="https://paforestry.org/" target="_blank" rel="noopener">Pennsylvania Forestry Association</a> (PFA) — a 501(c)(3) non-profit founded in 1886. The program is volunteer-led and has documented the state's largest trees for more than 50 years.</p>
      <p>Data flows through PFA's <a href="https://www.pabigtrees.com/trees" target="_blank" rel="noopener">public JSON API</a>. Photos are submitted by volunteer nominators and measurement crews; rights belong to the original photographers and to the PA Big Trees program. We mirror them here for ranking and discovery, with attribution.</p>
      <p><strong>If you find this page useful, please consider <a href="https://buy.stripe.com/8wM14jbI5arWgH65kl" target="_blank" rel="noopener">donating to the Pennsylvania Forestry Association</a> — they fund the program that makes this data possible.</strong></p>
    `,
    methodologyStatusTerms: [
      ["National Champion", "The biggest of its species in the United States. Flagged directly in the PA registry."],
      ["Champion", "The biggest of its species in Pennsylvania (derived from per-species scoring on this page)."],
      ["Co-Champion", "Tied within 5 points of the state Champion."],
      ["Penn Charter", "Owner has signed the Penn Charter pledge committing to protect the tree. A heritage-style designation unique to PA."],
      ["Listed", "Registered specimen that doesn't top its species ranking and has no special status flag."],
      ["Retired", "Marked retired in the PA registry — typically because the tree is no longer standing or has lost its title. <strong>Excluded from the overall rankings on this page.</strong>"],
    ],
    methodologyPrivacy: `
      <p>Pennsylvania's program doesn't expose per-tree permission flags the way NJ does. The addresses you see here are the ones the program publishes in its own public registry. Many of these trees are on private property.</p>
      <p>If you visit a tree, be respectful. Stay on public sidewalks or rights-of-way unless you have explicit permission from the property owner.</p>
    `,
  },
};

const STATES = {
  nj: { trees: null, generatedAt: null, loaded: false, error: null, trips: null, tripsLoaded: false },
  pa: { trees: null, generatedAt: null, loaded: false, error: null, trips: null, tripsLoaded: false },
};

const TRIP_REGION_ORDER = ["Northwest", "North", "Central", "South", "Shore"];

let activeState = "nj";
const ui = {
  filters: { status: "", county: "", search: "", photosOnly: false },
  // Each state remembers its filter selections so switching back restores them.
  filtersByState: { nj: null, pa: null },
  tripRegion: "",  // currently selected trip-region filter (NJ only)
};
const tripMaps = {};  // {tripId: L.Map} so we can dispose on tab switch

const STATUS_SLUG = {
  "National Champion": "national-champion",
  "Champion": "champion",
  "Co-Champion": "co-champion",
  "Heritage Champion": "heritage-champion",
  "Heritage": "heritage",
  "Signature": "signature",
  "Emeritus": "emeritus",
  "Trail Tree": "trail-tree",
  "Penn Charter": "penn-charter",
  "Listed": "listed",
  "Retired": "retired",
};

const fmt = new Intl.NumberFormat("en-US");

// ---------- Helpers ----------
function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
}

function formatDateShort(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function statusSlug(status) { return STATUS_SLUG[status] || "champion"; }

function nonCertPhotos(tree) {
  return (tree.photos || []).filter(p => !p.is_certificate);
}

function primaryPhoto(tree) {
  const ps = nonCertPhotos(tree);
  return ps.length ? ps[0] : null;
}

function photoUrl(tree, photo, kind = "main") {
  const ps = nonCertPhotos(tree);
  const idx = ps.indexOf(photo) + 1;
  if (!idx) return null;
  const stateDir = tree.state === "PA" ? "pa" : "nj";
  const suffix = kind === "thumb" ? "-thumb" : "";
  return `photos/${stateDir}/${tree.id}/${idx}${suffix}.jpg`;
}

function fullLocation(tree) {
  const parts = [];
  if (tree.municipality) parts.push(tree.municipality);
  if (tree.county) parts.push(tree.county + " County");
  return parts.join(", ");
}

function directionsUrl(tree) {
  if (tree.is_public_location && tree.display_address) {
    const stateAbbr = tree.state || "NJ";
    const zip = tree.zipcode || "";
    const muni = tree.municipality ? `, ${tree.municipality}` : "";
    const q = encodeURIComponent(`${tree.display_address}${muni}, ${stateAbbr} ${zip}`.trim());
    return `https://www.google.com/maps/search/?api=1&query=${q}`;
  }
  if (tree.display_lat != null && tree.display_lng != null) {
    return `https://www.google.com/maps/search/?api=1&query=${tree.display_lat},${tree.display_lng}`;
  }
  return null;
}

function altText(tree, idx = 0) {
  if (tree.alt_text) {
    return `${tree.alt_text}${idx > 0 ? ` (photo ${idx + 1})` : ""}`;
  }
  return `Photo of a ${tree.common_name}`;
}

function formatStatus(status) { return (status || "").replace(/_/g, " "); }

// ---------- Data loading ----------
async function loadState(state) {
  if (STATES[state].loaded || STATES[state].trees) return STATES[state];
  const r = await fetch(`data/${state}/trees.json`);
  if (!r.ok) {
    STATES[state].error = `Failed to load ${state} data: ${r.status}`;
    throw new Error(STATES[state].error);
  }
  const payload = await r.json();
  STATES[state].trees = payload.trees;
  STATES[state].generatedAt = payload.generated_at;
  STATES[state].loaded = true;
  return STATES[state];
}

function currentTrees() { return STATES[activeState].trees || []; }

// ---------- Hero / static copy ----------
function applyStateCopy(state) {
  const meta = STATE_META[state];
  const s = STATES[state];
  document.getElementById("hero-kicker").textContent = meta.kicker;
  document.getElementById("hero-count").textContent = fmt.format(s.trees ? s.trees.length : 0);
  document.getElementById("hero-lede").textContent = `of ${meta.possessive} biggest trees, ranked by size.`;
  document.getElementById("hero-sub").textContent = meta.sub;
  const sourceLink = document.getElementById("hero-source-link");
  sourceLink.href = meta.sourceUrl;
  sourceLink.textContent = meta.sourceName;
  const dateStr = formatDate(s.generatedAt);
  document.querySelectorAll("#updated-at, .updated-at").forEach(el => el.textContent = dateStr);
  const treesCount = s.trees ? s.trees.length : 0;
  document.getElementById("all-count").textContent = fmt.format(treesCount);
  document.getElementById("top10-title").textContent = `The 10 biggest trees in ${meta.label}`;

  // Methodology blocks
  document.getElementById("methodology-data").innerHTML = `<h3>The data</h3>${meta.methodologyData}`;
  document.getElementById("methodology-status").innerHTML =
    `<h3>Status terms</h3><dl class="terms">${meta.methodologyStatusTerms.map(([dt, dd]) =>
      `<dt>${escapeHtml(dt)}</dt><dd>${dd}</dd>`).join("")}</dl>`;
  document.getElementById("methodology-privacy").innerHTML = `<h3>Privacy & access</h3>${meta.methodologyPrivacy}`;

  // Credit callout (only states that have one — currently PA only).
  const cc = document.getElementById("credit-callout");
  if (meta.creditCallout) {
    const c = meta.creditCallout;
    cc.innerHTML = `
      <p class="credit-callout__headline">${escapeHtml(c.headline)}</p>
      <p class="credit-callout__body">${c.body}</p>
      <div class="credit-callout__ctas">
        <a class="credit-callout__cta" href="${c.ctaHomeUrl}" target="_blank" rel="noopener">${escapeHtml(c.ctaHomeLabel)} ↗</a>
        <a class="credit-callout__cta credit-callout__cta--donate" href="${c.ctaDonateUrl}" target="_blank" rel="noopener">${escapeHtml(c.ctaDonateLabel)} ↗</a>
      </div>
    `;
    cc.hidden = false;
  } else {
    cc.hidden = true;
    cc.innerHTML = "";
  }
}

function renderStatusChips(state) {
  const container = document.getElementById("status-chips");
  const meta = STATE_META[state];
  // Only show chips for statuses that actually appear in the data.
  const present = new Set((STATES[state].trees || []).map(t => t.status));
  const buttons = ['<button type="button" class="chip is-active" data-status="">All statuses</button>'];
  for (const status of meta.statuses) {
    if (!present.has(status)) continue;
    const slug = statusSlug(status);
    buttons.push(`<button type="button" class="chip chip--${slug}" data-status="${escapeHtml(status)}">${escapeHtml(status)}</button>`);
  }
  container.innerHTML = buttons.join("");
  container.querySelectorAll(".chip[data-status]").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".chip").forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      ui.filters.status = btn.dataset.status;
      applyFilters();
    });
  });
}

function renderCountyOptions(state) {
  const sel = document.getElementById("county-filter");
  const counties = [...new Set((STATES[state].trees || []).map(t => t.county).filter(Boolean))].sort();
  sel.innerHTML = `<option value="">All counties</option>` +
    counties.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
}

// ---------- Top 10 ----------
function renderTop10() {
  const list = document.getElementById("top10-list");
  const top = currentTrees().filter(t => t.rank_overall).slice(0, 10);
  list.innerHTML = top.map(renderTopCard).join("");
  list.querySelectorAll(".top-card").forEach(el => {
    el.addEventListener("click", () => openModal(el.dataset.id));
  });
}

function renderTopCard(tree) {
  const photo = primaryPhoto(tree);
  const photoBlock = photo
    ? `<img src="${photoUrl(tree, photo, "main")}" loading="lazy" alt="${escapeHtml(altText(tree))}">`
    : `<div class="card__media--empty" aria-hidden="true"></div>`;
  const where = tree.is_public_location && tree.display_address
    ? `<p class="top-card__where"><strong>Find it:</strong> ${escapeHtml(tree.display_address)}${tree.municipality ? `, ${escapeHtml(tree.municipality)}` : ""}, ${escapeHtml(tree.state || "")} ${escapeHtml(tree.zipcode || "")}</p>`
    : `<p class="top-card__where"><strong>Where:</strong> ${escapeHtml(fullLocation(tree) || tree.county || "Unknown")} <em>(location withheld)</em></p>`;
  const botanical = tree.botanical_name && tree.botanical_name.toLowerCase() !== tree.common_name.toLowerCase()
    ? `<p class="top-card__botanical">${escapeHtml(tree.botanical_name)}</p>`
    : "";
  return `
    <li>
      <button class="top-card" type="button" data-id="${escapeHtml(tree.id)}" aria-label="View ${escapeHtml(tree.common_name)} ranked #${tree.rank_overall}">
        <div class="top-card__media">
          ${photoBlock}
          <span class="top-card__rank">
            <span class="top-card__rank-label">No.</span>${tree.rank_overall}
          </span>
        </div>
        <div class="top-card__body">
          <span class="badge badge--${statusSlug(tree.status)}">${escapeHtml(formatStatus(tree.status))}</span>
          <h3 class="top-card__species">${escapeHtml(tree.common_name)}</h3>
          ${botanical}
          <dl class="top-card__stats">
            <div class="top-card__stat"><dt>Score</dt><dd>${fmt.format(tree.score || 0)}<small>pts</small></dd></div>
            <div class="top-card__stat"><dt>Around</dt><dd>${escapeHtml(tree.circumference_eng || (tree.circumference_in ? tree.circumference_in + ' in.' : '—'))}</dd></div>
            <div class="top-card__stat"><dt>Tall</dt><dd>${tree.height_ft ?? "—"}<small>ft</small></dd></div>
            <div class="top-card__stat"><dt>Crown</dt><dd>${tree.crown_avg_ft ?? "—"}<small>ft</small></dd></div>
          </dl>
          ${where}
        </div>
      </button>
    </li>
  `;
}

// ---------- Grid ----------
function applyFilters() {
  const { status, county, search, photosOnly } = ui.filters;
  const q = search.trim().toLowerCase();
  const filtered = currentTrees().filter(t => {
    if (status && t.status !== status) return false;
    if (county && t.county !== county) return false;
    if (photosOnly && nonCertPhotos(t).length === 0) return false;
    if (q) {
      const hay = `${t.common_name} ${t.botanical_name} ${t.local_name || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  renderGrid(filtered);
}

function renderGrid(filtered) {
  const grid = document.getElementById("grid");
  const empty = document.getElementById("grid-empty");
  const count = document.getElementById("filter-count");
  count.textContent = `${fmt.format(filtered.length)} ${filtered.length === 1 ? "tree" : "trees"}`;
  if (filtered.length === 0) {
    grid.innerHTML = "";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  grid.innerHTML = filtered.map(renderCard).join("");
  grid.querySelectorAll(".card").forEach(el => {
    el.addEventListener("click", () => openModal(el.dataset.id));
  });
}

function renderCard(tree) {
  const photo = primaryPhoto(tree);
  const media = photo
    ? `<div class="card__media"><img src="${photoUrl(tree, photo, "thumb")}" loading="lazy" alt="${escapeHtml(altText(tree))}"></div>`
    : `<div class="card__media card__media--empty" aria-hidden="true"></div>`;
  const rank = tree.rank_overall
    ? `<span class="card__rank">#${tree.rank_overall}</span>`
    : (tree.status === "Emeritus" || tree.status === "Retired"
        ? `<span class="card__rank card__rank--unranked">unranked</span>`
        : "");
  return `
    <button class="card" type="button" data-id="${escapeHtml(tree.id)}" role="listitem" aria-label="${escapeHtml(tree.common_name)}, ranked #${tree.rank_overall || "unranked"}">
      <div class="card__media-wrap" style="position: relative;">
        ${media}${rank}
      </div>
      <div class="card__body">
        <span class="badge badge--${statusSlug(tree.status)}">${escapeHtml(formatStatus(tree.status))}</span>
        <h3 class="card__species">${escapeHtml(tree.common_name)}</h3>
        <div class="card__meta">
          <span>${escapeHtml(tree.county || "")} ${tree.county ? "County" : ""}</span>
          <span class="card__points">${fmt.format(tree.score || 0)}<small>pts</small></span>
        </div>
      </div>
    </button>
  `;
}

// ---------- Modal ----------
let modalMap = null;
let modalPhotoIdx = 0;
let modalTree = null;

function openModal(treeId) {
  const tree = currentTrees().find(t => String(t.id) === String(treeId));
  if (!tree) return;
  modalTree = tree;
  modalPhotoIdx = 0;
  const modal = document.getElementById("modal");
  const body = document.getElementById("modal-body");
  body.innerHTML = renderDetail(tree);
  attachDetailHandlers(tree);
  modal.hidden = false;
  document.body.style.overflow = "hidden";
  if (tree.display_lat != null && tree.display_lng != null && typeof L !== "undefined") {
    setTimeout(() => mountMap(tree), 50);
  }
  // Reflect in URL hash for shareability without nuking scroll.
  if (history.replaceState) {
    history.replaceState(null, "", `${location.pathname}${location.search}#tree-${tree.id}`);
  }
}

function closeModal() {
  const modal = document.getElementById("modal");
  modal.hidden = true;
  document.body.style.overflow = "";
  if (modalMap) { modalMap.remove(); modalMap = null; }
  modalTree = null;
  if (history.replaceState) {
    history.replaceState(null, "", `${location.pathname}${location.search}`);
  }
}

function renderDetail(tree) {
  const photos = nonCertPhotos(tree);
  const heroPhoto = photos[0];
  const heroBlock = heroPhoto
    ? `<img src="${photoUrl(tree, heroPhoto, "main")}" alt="${escapeHtml(altText(tree, 0))}" id="detail-img">`
    : `<div class="card__media--empty" style="position:absolute;inset:0;"></div>`;

  const nav = photos.length > 1 ? `
    <div class="detail__nav">
      <button type="button" data-prev aria-label="Previous photo"><svg viewBox="0 0 24 24"><path d="M15 5 L8 12 L15 19" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
      <button type="button" data-next aria-label="Next photo"><svg viewBox="0 0 24 24"><path d="M9 5 L16 12 L9 19" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
    </div>
    <div class="detail__dots">${photos.map((_, i) => `<span class="${i === 0 ? "is-active" : ""}"></span>`).join("")}</div>
  ` : "";

  let rank = "";
  if (tree.rank_overall) {
    rank = `<span class="detail__rank"><span class="detail__rank-label">No.</span><span class="detail__rank-num">${tree.rank_overall}</span></span>`;
  } else if (tree.status === "Emeritus" || tree.status === "Retired") {
    rank = `<span class="detail__rank detail__rank--unranked"><span class="detail__rank-label">Former</span><span class="detail__rank-num">champion</span></span>`;
  }

  const localBlock = tree.local_name
    ? `<p class="detail__local">Known locally as “${escapeHtml(tree.local_name)}”</p>`
    : "";

  const botanical = tree.botanical_name && tree.botanical_name.toLowerCase() !== tree.common_name.toLowerCase()
    ? `<p class="detail__botanical">${escapeHtml(tree.botanical_name)}</p>`
    : "";

  // PA supplementary flag chips. We surface Penn Charter here as a chip when
  // the tree already has a higher-priority status (e.g. Champion), so the
  // owner's pledge is still visible.
  let flagChips = "";
  if (tree.state === "PA") {
    const chips = [];
    if (tree.pa_penn_charter && tree.status !== "Penn Charter") {
      chips.push(`<span class="flag-chip flag-chip--penn-charter">Penn Charter tree</span>`);
    }
    if (tree.pa_tallest_in_species) chips.push(`<span class="flag-chip flag-chip--tallest">Tallest of species in PA</span>`);
    if (tree.pa_multistemmed) chips.push(`<span class="flag-chip flag-chip--multistemmed">Multi-stemmed</span>`);
    if (chips.length) flagChips = `<div class="detail__flags">${chips.join("")}</div>`;
  }

  const noticeStatus = tree.status === "Emeritus" ? "Emeritus" : (tree.status === "Retired" ? "Retired" : null);
  const retiredNotice = noticeStatus ? `
    <p class="detail__notice detail__notice--emeritus">
      <strong>${noticeStatus} status:</strong> this tree was once the state champion of its species but has been displaced by a larger one — or is no longer standing. ${noticeStatus === "Emeritus" ? "NJ DEP" : "The PA Big Trees program"} keeps ${noticeStatus} trees on the registry for historical recognition. Because of that uncertainty, ${noticeStatus} trees aren't included in the overall rankings on this page. Call the property owner or the registry before making a trip.
    </p>
  ` : "";

  const locationBlock = renderLocation(tree);
  const accessBlock = tree.state === "PA" ? renderAboutPA(tree) : renderPermissionsNJ(tree);

  const meta = STATE_META[tree.state === "PA" ? "pa" : "nj"];
  const detailUrl = meta.detailUrl ? meta.detailUrl(tree.id) : (meta.rawRecordUrl ? meta.rawRecordUrl(tree.id) : null);
  // On PA trees, surface a prominent attribution + outbound link near the top
  // of the modal — not just buried in the footer. PA's program is volunteer-
  // run and deserves visible credit.
  const paAttribution = tree.state === "PA" && detailUrl ? `
    <a class="detail__attribution" href="${detailUrl}" target="_blank" rel="noopener">
      <span class="detail__attribution__label">From Pennsylvania Big Trees</span>
      <span class="detail__attribution__cta">View the full record on pabigtrees.com ↗</span>
    </a>
  ` : "";

  return `
    <h2 id="modal-title" class="sr-only">${escapeHtml(tree.common_name)}${tree.rank_overall ? `, ranked #${tree.rank_overall}` : ""}</h2>
    <div class="detail__hero">
      ${heroBlock}
      ${rank}
      ${nav}
    </div>
    <div class="detail__head">
      <span class="badge badge--${statusSlug(tree.status)}">${escapeHtml(formatStatus(tree.status))}</span>
      <h2 class="detail__title">${escapeHtml(tree.common_name)}</h2>
      ${botanical}
      ${flagChips}
      ${localBlock}
      ${paAttribution}
      ${retiredNotice}
    </div>
    <dl class="detail__stats">
      <div class="detail__stat"><dt>Score</dt><dd>${fmt.format(tree.score || 0)}<small>pts</small></dd></div>
      <div class="detail__stat"><dt>Around</dt><dd>${escapeHtml(tree.circumference_eng || (tree.circumference_in ? tree.circumference_in + ' in.' : '—'))}</dd></div>
      <div class="detail__stat"><dt>Tall</dt><dd>${tree.height_ft ?? "—"}<small>ft</small></dd></div>
      <div class="detail__stat"><dt>Crown</dt><dd>${tree.crown_avg_ft ?? "—"}<small>ft avg</small></dd></div>
      ${tree.dbh_in ? `<div class="detail__stat"><dt>DBH</dt><dd>${tree.dbh_in}<small>in</small></dd></div>` : ""}
      ${tree.ranking_in_species ? `<div class="detail__stat"><dt>Rank in species</dt><dd>#${tree.ranking_in_species}</dd></div>` : ""}
    </dl>
    ${locationBlock}
    ${accessBlock}
    <p class="detail__source">
      Source: <a href="${meta.sourceUrl}" target="_blank" rel="noopener">${escapeHtml(meta.sourceName)}</a> ·
      Record ${escapeHtml(tree.id)}
      ${detailUrl ? ` · <a href="${detailUrl}" target="_blank" rel="noopener">View raw record</a>` : ""}
    </p>
  `;
}

function renderLocation(tree) {
  const dir = directionsUrl(tree);
  const hasMap = tree.display_lat != null && tree.display_lng != null;
  let addr;
  if (tree.is_public_location && tree.display_address) {
    // NJ records split address into street / muni / zip — compose them.
    // PA records jam everything into t_address, so don't append anything.
    if (tree.state === "PA") {
      addr = `<p class="detail__address"><strong>${escapeHtml(tree.display_address)}</strong></p>`;
    } else {
      const stateAbbr = tree.state || "";
      const zip = tree.zipcode ? ` ${tree.zipcode}` : "";
      const muni = tree.municipality ? `${escapeHtml(tree.municipality)}, ` : "";
      addr = `<p class="detail__address"><strong>${escapeHtml(tree.display_address)}</strong><br>${muni}${escapeHtml(stateAbbr)}${zip}</p>`;
    }
  } else if (tree.municipality || tree.county) {
    addr = `<p class="detail__address"><strong>${escapeHtml(tree.municipality || "")}${tree.municipality && tree.county ? ", " : ""}${escapeHtml(tree.county || "")} County</strong></p>
            <p class="detail__notice">Exact location not published — this tree is on private property and the owner did not grant permission to list the address publicly.</p>`;
  } else {
    addr = `<p class="detail__address">Location unknown.</p>`;
  }
  const dirLink = dir
    ? `<a class="detail__directions" href="${dir}" target="_blank" rel="noopener">Get directions ↗</a>`
    : "";
  const map = hasMap
    ? `<div class="detail__map" id="detail-map" aria-label="Map showing tree location"></div>`
    : "";
  return `
    <section class="detail__location">
      <h3>How to find it</h3>
      ${addr}
      ${dirLink}
      ${map}
    </section>
  `;
}

function renderPermissionsNJ(tree) {
  // NJ has explicit per-tree permission fields. PA does not.
  const rows = [
    { ok: tree.permission_to_list, yes: "Owner gave permission to list this tree publicly.", no: "Public listing permission not on file." },
    { ok: tree.permission_to_photograph, yes: "Owner allowed NJ DEP foresters to photograph the tree.", no: "Photography permission not on file." },
    { ok: tree.permission_to_measure, yes: "Owner allowed certified foresters to measure the tree.", no: "Measurement permission not on file." },
    { ok: tree.certificate, yes: "Tree owner received an NJ DEP big-tree certificate.", no: "No NJ DEP certificate has been issued." },
  ];
  return `
    <section class="detail__permissions">
      <h3>What the registry says about access</h3>
      <ul class="perms">
        ${rows.map(r => `
          <li class="perms__row ${r.ok ? "perms__row--yes" : "perms__row--no"}">
            <span class="perms__icon" aria-hidden="true">${r.ok ? "✓" : "✗"}</span>
            <span class="perms__text">${escapeHtml(r.ok ? r.yes : r.no)}</span>
          </li>
        `).join("")}
      </ul>
      <p class="perms__note">
        These permissions were granted by the property owner <em>to NJ DEP foresters</em> during registration — they don't authorize anyone else to enter, photograph, or measure the tree. If you want to visit, view from a public sidewalk or ask the property owner first.
      </p>
    </section>
  `;
}

function renderAboutPA(tree) {
  // PA records carry context fields that NJ doesn't (nominator, crew, dates,
  // free-text comments). Surface them here in plain language.
  const rows = [];
  if (tree.pa_nominator) rows.push(["Nominated by", escapeHtml(tree.pa_nominator)]);
  if (tree.pa_measure_crew) rows.push(["Last measured by", escapeHtml(tree.pa_measure_crew)]);
  const dn = formatDateShort(tree.pa_date_nominated);
  if (dn) rows.push(["Nominated", dn]);
  const dm = formatDateShort(tree.pa_date_last_measured);
  if (dm) rows.push(["Last measured", dm]);
  if (tree.pa_comments) {
    rows.push([
      "Notes",
      `<span class="about-list__value about-list__value--comment">${escapeHtml(tree.pa_comments)}</span>`,
    ]);
  }
  if (!rows.length) return "";
  return `
    <section class="detail__about">
      <h3>About this tree</h3>
      <ul class="about-list">
        ${rows.map(([label, value]) => `
          <li class="about-list__row">
            <span class="about-list__label">${escapeHtml(label)}</span>
            <span class="about-list__value">${value}</span>
          </li>
        `).join("")}
      </ul>
      <p class="perms__note">
        Pennsylvania's program doesn't expose per-tree access permissions. Many trees stand on private property — view from public rights-of-way or ask the property owner first.
      </p>
    </section>
  `;
}

function attachDetailHandlers(tree) {
  const body = document.getElementById("modal-body");
  const photos = nonCertPhotos(tree);
  const prev = body.querySelector("[data-prev]");
  const next = body.querySelector("[data-next]");
  if (prev && next) {
    const update = () => {
      const img = document.getElementById("detail-img");
      const p = photos[modalPhotoIdx];
      img.src = photoUrl(tree, p, "main");
      img.alt = altText(tree, modalPhotoIdx);
      body.querySelectorAll(".detail__dots span").forEach((s, i) => s.classList.toggle("is-active", i === modalPhotoIdx));
      prev.disabled = modalPhotoIdx === 0;
      next.disabled = modalPhotoIdx === photos.length - 1;
    };
    prev.addEventListener("click", () => { if (modalPhotoIdx > 0) { modalPhotoIdx--; update(); } });
    next.addEventListener("click", () => { if (modalPhotoIdx < photos.length - 1) { modalPhotoIdx++; update(); } });
    update();
  }
}

function mountMap(tree) {
  const el = document.getElementById("detail-map");
  if (!el) return;
  const precise = tree.is_public_location && tree.display_precision === "exact";
  const center = [tree.display_lat, tree.display_lng];
  modalMap = L.map(el, { scrollWheelZoom: false, zoomControl: true }).setView(center, precise ? 16 : 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(modalMap);
  const icon = L.divIcon({
    className: "tree-pin",
    html: `<div style="width: 32px; height: 32px; background: ${precise ? '#e0813a' : '#6b6b6b'}; border: 3px solid white; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); box-shadow: 0 3px 8px rgba(0,0,0,0.3);"></div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
  });
  L.marker(center, { icon }).addTo(modalMap);
  if (!precise) {
    L.circle(center, { radius: 1200, color: "#6b6b6b", fillColor: "#6b6b6b", fillOpacity: 0.08, weight: 1 }).addTo(modalMap);
  }
}

// ---------- Field trips (NJ only) ----------
async function loadTrips(state) {
  if (state !== "nj") return null;
  if (STATES.nj.tripsLoaded) return STATES.nj.trips;
  try {
    const r = await fetch("data/nj/trips.json");
    if (!r.ok) throw new Error(`Failed to load trips: ${r.status}`);
    const payload = await r.json();
    STATES.nj.trips = payload.trips || [];
    STATES.nj.tripsLoaded = true;
    return STATES.nj.trips;
  } catch (err) {
    console.warn("Trip data unavailable:", err);
    STATES.nj.trips = [];
    STATES.nj.tripsLoaded = true;
    return [];
  }
}

function disposeTripMaps() {
  for (const id in tripMaps) {
    try { tripMaps[id].remove(); } catch (e) {}
    delete tripMaps[id];
  }
}

function tripAccessSummary(trip) {
  // "5 residences" or "1 park · 4 residences" — readable mix, plural-aware.
  const labels = {
    park: ["park", "parks"],
    school: ["school", "schools"],
    religious: ["religious site", "religious sites"],
    public: ["public institution", "public institutions"],
    residence: ["residence", "residences"],
  };
  const parts = [];
  // Always lead with the most "public" first so park reads before residence.
  const order = ["park", "school", "religious", "public", "residence"];
  for (const key of order) {
    const n = trip.access_mix[key] || 0;
    if (!n) continue;
    parts.push(`${n} ${labels[key][n === 1 ? 0 : 1]}`);
  }
  return parts.join(" · ");
}

function renderTrips() {
  const grid = document.getElementById("trip-grid");
  const empty = document.getElementById("trip-grid-empty");
  const trips = STATES.nj.trips || [];
  const filtered = ui.tripRegion ? trips.filter(t => t.region === ui.tripRegion) : trips;
  disposeTripMaps();
  if (!filtered.length) {
    grid.innerHTML = "";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  grid.innerHTML = filtered.map(renderTripCard).join("");
  // Mount maps after the DOM is in place.
  for (const trip of filtered) {
    setTimeout(() => mountTripMap(trip), 30);
  }
  // Wire stop click handlers to open the registry modal.
  grid.querySelectorAll(".trip-stop").forEach(el => {
    el.addEventListener("click", () => openModal(el.dataset.treeId));
  });
}

function renderTripCard(trip) {
  const stops = trip.stops || [];
  return `
    <article class="trip" data-id="${escapeHtml(trip.id)}" role="listitem">
      <header class="trip__head">
        <div>
          <p class="trip__region">${escapeHtml(trip.region)}</p>
          <h3 class="trip__name">${escapeHtml(trip.name)}</h3>
        </div>
        <dl class="trip__stats">
          <div class="trip__stat"><dt>Drive</dt><dd>${trip.drive_minutes}<small>min</small></dd></div>
          <div class="trip__stat"><dt>Miles</dt><dd>${Math.round(trip.drive_miles)}</dd></div>
          <div class="trip__stat"><dt>Stops</dt><dd>${trip.stop_count}</dd></div>
        </dl>
      </header>
      <p class="trip__mix">${escapeHtml(tripAccessSummary(trip))}</p>
      <div class="trip__map" id="trip-map-${escapeHtml(trip.id)}" aria-label="Map of route through ${escapeHtml(trip.name)}"></div>
      <ol class="trip__stops">
        ${stops.map(s => renderTripStop(s)).join("")}
      </ol>
    </article>
  `;
}

function renderTripStop(stop) {
  const thumbHtml = stop.thumbnail
    ? `<img class="trip-stop__thumb" src="${stop.thumbnail}" loading="lazy" alt="${escapeHtml(stop.common_name)}">`
    : `<div class="trip-stop__thumb trip-stop__thumb--empty" aria-hidden="true"></div>`;
  const where = stop.municipality || stop.county || "";
  return `
    <li class="trip-stop" data-tree-id="${escapeHtml(stop.tree_id)}">
      <span class="trip-stop__num">${stop.order}</span>
      ${thumbHtml}
      <div class="trip-stop__body">
        <p class="trip-stop__name"><strong>${escapeHtml(stop.common_name)}</strong></p>
        <p class="trip-stop__where">${escapeHtml(where)}${stop.county && stop.municipality ? `, ${escapeHtml(stop.county)} County` : ""}</p>
        <p class="trip-stop__context trip-stop__context--${escapeHtml(stop.visit_context_key)}">${escapeHtml(stop.visit_context)}</p>
      </div>
      <span class="trip-stop__points">${fmt.format(stop.score || 0)}<small>pts</small></span>
    </li>
  `;
}

function mountTripMap(trip) {
  const el = document.getElementById(`trip-map-${trip.id}`);
  if (!el || typeof L === "undefined") return;
  if (tripMaps[trip.id]) {
    tripMaps[trip.id].remove();
    delete tripMaps[trip.id];
  }
  const map = L.map(el, { scrollWheelZoom: false, zoomControl: true, attributionControl: false });
  tripMaps[trip.id] = map;
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; OpenStreetMap',
    maxZoom: 18,
  }).addTo(map);
  L.control.attribution({ prefix: false }).addTo(map);

  // Draw the route polyline if we have one.
  if (trip.route_geojson && trip.route_geojson.coordinates && trip.route_geojson.coordinates.length > 1) {
    L.geoJSON(trip.route_geojson, {
      style: { color: "#e0813a", weight: 4, opacity: 0.85 },
    }).addTo(map);
  }

  // Numbered stop markers.
  const bounds = [];
  for (const stop of trip.stops) {
    const icon = L.divIcon({
      className: "trip-pin",
      html: `<div class="trip-pin__inner">${stop.order}</div>`,
      iconSize: [30, 30],
      iconAnchor: [15, 30],
    });
    L.marker([stop.lat, stop.lng], { icon }).addTo(map);
    bounds.push([stop.lat, stop.lng]);
  }
  if (bounds.length > 1) {
    map.fitBounds(bounds, { padding: [25, 25] });
  } else if (bounds.length === 1) {
    map.setView(bounds[0], 13);
  }
}

function renderRegionChips() {
  const container = document.getElementById("region-chips");
  if (!container) return;
  const present = new Set((STATES.nj.trips || []).map(t => t.region));
  const buttons = [`<button type="button" class="chip is-active" data-region="">All regions</button>`];
  for (const region of TRIP_REGION_ORDER) {
    if (!present.has(region)) continue;
    buttons.push(`<button type="button" class="chip" data-region="${escapeHtml(region)}">${escapeHtml(region)}</button>`);
  }
  container.innerHTML = buttons.join("");
  container.querySelectorAll(".chip[data-region]").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".chip").forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      ui.tripRegion = btn.dataset.region;
      renderTrips();
    });
  });
}

async function showTripsForState(state) {
  const section = document.getElementById("trips");
  const navLink = document.getElementById("nav-trips");
  if (state !== "nj") {
    section.hidden = true;
    if (navLink) navLink.hidden = true;
    disposeTripMaps();
    return;
  }
  const trips = await loadTrips("nj");
  if (!trips || !trips.length) {
    section.hidden = true;
    if (navLink) navLink.hidden = true;
    return;
  }
  section.hidden = false;
  if (navLink) navLink.hidden = false;
  ui.tripRegion = "";
  renderRegionChips();
  renderTrips();
}

// ---------- Tab switching ----------
async function switchToState(state, { updateUrl = true, openTreeId = null } = {}) {
  if (!STATES[state]) return;
  if (!PUBLIC_STATES.has(state)) return;  // gated off in this build
  // Persist current filter selections before switching.
  ui.filtersByState[activeState] = { ...ui.filters };
  activeState = state;

  // Update tab visuals.
  document.querySelectorAll(".state-tab").forEach(t => {
    const isActive = t.dataset.state === state;
    t.classList.toggle("is-active", isActive);
    t.setAttribute("aria-selected", isActive ? "true" : "false");
  });

  // Restore filters for incoming state, or reset.
  ui.filters = ui.filtersByState[state] || { status: "", county: "", search: "", photosOnly: false };

  try {
    await loadState(state);
  } catch (err) {
    console.error(err);
    document.getElementById("hero-count").textContent = "—";
    return;
  }
  applyStateCopy(state);
  renderStatusChips(state);
  renderCountyOptions(state);

  // Reset UI controls to reflect filters.
  document.getElementById("search").value = ui.filters.search;
  document.getElementById("county-filter").value = ui.filters.county;
  document.getElementById("photos-only").checked = ui.filters.photosOnly;
  document.querySelectorAll("#status-chips .chip").forEach(c => {
    c.classList.toggle("is-active", (c.dataset.status || "") === ui.filters.status);
  });

  renderTop10();
  applyFilters();
  showTripsForState(state);

  if (updateUrl) {
    const params = new URLSearchParams(location.search);
    if (state === "nj") params.delete("state");
    else params.set("state", state);
    const search = params.toString();
    const hash = openTreeId ? `#tree-${openTreeId}` : "";
    history.replaceState(null, "", `${location.pathname}${search ? "?" + search : ""}${hash}`);
  }

  if (openTreeId) openModal(openTreeId);

  // Total counts in tabs are stable; refresh in case data loaded a different size.
  document.querySelectorAll("[data-state-count]").forEach(el => {
    const st = el.dataset.stateCount;
    if (STATES[st].trees) el.textContent = fmt.format(STATES[st].trees.length);
  });
}

// ---------- Bind UI ----------
function bindStaticControls() {
  // Search
  document.getElementById("search").addEventListener("input", e => {
    ui.filters.search = e.target.value;
    applyFilters();
  });
  // County
  document.getElementById("county-filter").addEventListener("change", e => {
    ui.filters.county = e.target.value;
    applyFilters();
  });
  // Photos-only
  document.getElementById("photos-only").addEventListener("change", e => {
    ui.filters.photosOnly = e.target.checked;
    applyFilters();
  });
  // Tab buttons
  document.querySelectorAll(".state-tab").forEach(btn => {
    btn.addEventListener("click", () => switchToState(btn.dataset.state));
  });
}

function bindModal() {
  document.querySelectorAll("[data-close]").forEach(el => el.addEventListener("click", closeModal));
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !document.getElementById("modal").hidden) closeModal();
    if (modalTree && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
      const btn = e.key === "ArrowLeft" ? document.querySelector("[data-prev]") : document.querySelector("[data-next]");
      if (btn && !btn.disabled) btn.click();
    }
  });
  // Browser back/forward navigation between deep links.
  window.addEventListener("hashchange", () => {
    const m = location.hash.match(/^#tree-([\w-]+)/);
    if (m && (!modalTree || modalTree.id !== m[1])) openModal(m[1]);
    else if (!m && modalTree) closeModal();
  });
}

// ---------- Boot ----------
(async function init() {
  // Hide tab buttons for states not in the public allowlist. The DOM nodes
  // stay so re-enabling is a one-line flag change, not an HTML edit.
  document.querySelectorAll(".state-tab").forEach(tab => {
    if (!PUBLIC_STATES.has(tab.dataset.state)) tab.hidden = true;
  });
  // Hide the whole tab strip if there's only one state in the public build —
  // no point showing a "switch states" affordance with one option.
  if (PUBLIC_STATES.size <= 1) {
    const strip = document.querySelector(".state-tabs");
    if (strip) strip.hidden = true;
  }

  bindStaticControls();
  bindModal();

  const params = new URLSearchParams(location.search);
  const requested = params.get("state");
  const isStaleStateParam = requested && !PUBLIC_STATES.has(requested);
  const initial = requested && PUBLIC_STATES.has(requested) ? requested : "nj";

  const hashMatch = location.hash.match(/^#tree-([\w-]+)/);
  const openId = hashMatch ? hashMatch[1] : null;

  // If the user landed via a bookmarked URL for a now-gated state, drop the
  // stale ?state= so the page they see and the URL agree.
  await switchToState(initial, { updateUrl: isStaleStateParam, openTreeId: openId });

  // Pre-warm the inactive tab's count, but only for tabs we actually show.
  for (const other of Object.keys(STATES)) {
    if (other === initial || !PUBLIC_STATES.has(other)) continue;
    loadState(other).then(() => {
      document.querySelectorAll(`[data-state-count="${other}"]`).forEach(el => {
        el.textContent = fmt.format(STATES[other].trees.length);
      });
    }).catch(() => {/* fine — initial load handled separately */});
  }
})();
