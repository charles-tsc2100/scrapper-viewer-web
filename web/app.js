/* app.js — shared Supabase client, auth guard, list + detail logic */

const { createClient } = supabase;
const db = createClient(window.ENV.SUPABASE_URL, window.ENV.SUPABASE_ANON_KEY);

async function requireAuth() {
  const { data: { session } } = await db.auth.getSession();
  if (!session) location.replace("login.html");
  return session;
}

async function signOut() {
  await db.auth.signOut();
  location.replace("login.html");
}


// ─── List page ────────────────────────────────────────────────────────────────

function renderProducts(data) {
  const productList = document.getElementById("product-list");
  const countEl     = document.getElementById("result-count");

  countEl.textContent = `${data.length} product${data.length !== 1 ? "s" : ""}`;

  if (!data.length) {
    productList.innerHTML = "<p class='text-gray-400 py-8 text-center col-span-full'>No products found.</p>";
    return;
  }

  if (currentLayout === "grid") {
    productList.innerHTML = data.map(p => {
      const thumb = (p.image_urls || [])[0] || "";
      const cat   = p.category ? p.category.split(">").pop().trim() : "";
      return `
        <a href="product.html?id=${encodeURIComponent(p.id)}"
           class="flex bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow overflow-hidden">
          ${thumb
            ? `<img src="${thumb}" alt="${p.model}" class="grid-img">`
            : `<div class="grid-no-img">No img</div>`}
          <div class="card-body">
            <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">${p.brand || ""}</span>
            ${cat ? `<p class="text-xs text-gray-400 mt-1">${cat}</p>` : ""}
            <p class="font-semibold text-gray-800 text-sm mt-1 leading-tight">${p.model}</p>
            ${p.finish || p.material ? `<p class="text-xs text-gray-400 mt-1 truncate">${p.finish || p.material}</p>` : ""}
          </div>
        </a>`;
    }).join("");
    return;
  }

  if (currentLayout === "compact") {
    productList.innerHTML = data.map(p => {
      const thumb = (p.image_urls || [])[0] || "";
      const cat   = p.category ? p.category.split(">").pop().trim() : "";
      return `
        <a href="product.html?id=${encodeURIComponent(p.id)}"
           class="flex items-center gap-3 hover:bg-gray-50 transition-colors">
          ${thumb
            ? `<img src="${thumb}" alt="${p.model}" class="compact-thumb">`
            : `<div class="compact-no-img"></div>`}
          <span class="text-xs font-semibold text-blue-700 w-16 flex-shrink-0">${p.brand || ""}</span>
          <span class="font-medium text-gray-800 text-sm w-36 flex-shrink-0 truncate">${p.model}</span>
          <span class="text-xs text-gray-400 flex-1 truncate hidden sm:block">${p.finish || p.material || cat || ""}</span>
          <svg class="w-3 h-3 text-gray-300 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </a>`;
    }).join("");
    return;
  }

  // Default: list
  productList.innerHTML = data.map(p => {
    const thumb = (p.image_urls || [])[0] || "";
    const cat   = p.category ? p.category.split(">").pop().trim() : "";
    const sub   = p.finish || p.material || "";
    return `
      <a href="product.html?id=${encodeURIComponent(p.id)}"
         class="flex items-center gap-4 p-4 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow">
        ${thumb
          ? `<img src="${thumb}" alt="${p.model}" class="product-thumb">`
          : `<div class="product-thumb bg-gray-100 flex items-center justify-center text-gray-300 text-xs rounded">No img</div>`}
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">${p.brand || ""}</span>
            ${cat ? `<span class="text-xs text-gray-400">${cat}</span>` : ""}
          </div>
          <p class="font-semibold text-gray-800 mt-1 truncate">${p.model}</p>
          ${p.name && p.name !== p.model ? `<p class="text-sm text-gray-500 truncate">${p.name}</p>` : ""}
          ${sub ? `<p class="text-xs text-gray-400 mt-0.5 truncate">${sub}</p>` : ""}
        </div>
        <svg class="w-4 h-4 text-gray-300 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
        </svg>
      </a>`;
  }).join("");
}

let currentLayout = localStorage.getItem("layout") || "list";

function setLayout(layout) {
  currentLayout = layout;
  localStorage.setItem("layout", layout);
  const list = document.getElementById("product-list");
  list.className = "flex flex-col gap-3";
  if (layout === "grid")    list.classList.add("layout-grid");
  if (layout === "compact") list.classList.add("layout-compact");
  ["list","grid","compact"].forEach(l => {
    document.getElementById("btn-" + l)?.classList.toggle("active", l === layout);
  });
  if (window._lastData) renderProducts(window._lastData);
}

async function initList() {
  await requireAuth();

  const searchInput = document.getElementById("search");
  const brandFilter = document.getElementById("brand-filter");
  const productList = document.getElementById("product-list");
  const countEl     = document.getElementById("result-count");

  // Apply saved layout on load
  setLayout(currentLayout);

  // Populate brand dropdown
  const { data: brands } = await db.from("products").select("brand").order("brand");
  const unique = [...new Set((brands || []).map(r => r.brand).filter(Boolean))];
  unique.forEach(b => {
    const opt = document.createElement("option");
    opt.value = b; opt.textContent = b;
    brandFilter.appendChild(opt);
  });

  let debounce;
  function onFilter() {
    clearTimeout(debounce);
    debounce = setTimeout(fetchProducts, 250);
  }

  searchInput.addEventListener("input", onFilter);
  brandFilter.addEventListener("change", onFilter);

  async function fetchProducts() {
    const q     = searchInput.value.trim();
    const brand = brandFilter.value;

    productList.innerHTML = "<p class='text-gray-400 py-8 text-center'>Loading…</p>";

    let query = db
      .from("products")
      .select("id,brand,model,name,category,subcategory,material,finish,image_urls")
      .order("brand")
      .order("model")
      .limit(200);

    if (brand) query = query.eq("brand", brand);

    if (q) {
      // Full-text search on indexed tsvector first; also OR-match material/finish/raw
      query = query.or(
        `search_tsv.fts.${q},material.ilike.%${q}%,finish.ilike.%${q}%,raw.fts.${q}`
      );
    }

    const { data, error } = await query;

    if (error) {
      if (q) {
        let fallback = db
          .from("products")
          .select("id,brand,model,name,category,subcategory,material,finish,image_urls")
          .order("brand").order("model").limit(200);
        if (brand) fallback = fallback.eq("brand", brand);
        fallback = fallback.or(`material.ilike.%${q}%,finish.ilike.%${q}%,model.ilike.%${q}%,name.ilike.%${q}%,category.ilike.%${q}%`);
        const { data: fbData, error: fbErr } = await fallback;
        if (!fbErr && fbData) { window._lastData = fbData; return renderProducts(fbData); }
      }
      productList.innerHTML = `<p class='text-red-400 py-8 text-center col-span-full'>Error: ${error.message}</p>`;
      return;
    }

    window._lastData = data;
    renderProducts(data);
  }

  fetchProducts();
}


// ─── Detail page ──────────────────────────────────────────────────────────────

async function initDetail() {
  await requireAuth();

  const id = new URLSearchParams(location.search).get("id");
  if (!id) { location.href = "index.html"; return; }

  const { data, error } = await db.from("products").select("*").eq("id", id).single();

  if (error || !data) {
    document.getElementById("content").innerHTML =
      `<p class='text-red-400'>Product not found.</p>`;
    return;
  }

  document.title = `${data.model} — Product Catalogue`;
  document.getElementById("breadcrumb-model").textContent = data.model;

  // Images
  const images = data.image_urls || [];
  const mainImg  = document.getElementById("main-image");
  const thumbGrid = document.getElementById("thumb-grid");

  if (images.length) {
    mainImg.src = images[0];
    mainImg.alt = data.model;
    thumbGrid.innerHTML = images.map((url, i) =>
      `<img src="${url}" alt="${data.model} ${i+1}" onclick="document.getElementById('main-image').src='${url}'">`
    ).join("");
  } else {
    mainImg.parentElement.classList.add("hidden");
  }

  // Core spec table
  const specRows = [
    ["Brand",          data.brand],
    ["Model",          data.model],
    ["Category",       data.category],
    ["Subcategory",    data.subcategory],
    ["Material",       data.material],
    ["Finish",         data.finish],
    ["Load Capacity",    data.load_capacity_kg  != null ? `${data.load_capacity_kg} kg`  : null],
    ["Max Door Height",  data.door_height_mm    != null ? `${data.door_height_mm} mm`    : null],
    ["Max Door Width",   data.door_width_mm     != null ? `${data.door_width_mm} mm`     : null],
    ["Door Thickness",   data.door_thickness_mm != null ? `${data.door_thickness_mm} mm` : null],
  ].filter(([, v]) => v != null);

  document.getElementById("spec-table").innerHTML = specRows.map(([k, v]) =>
    `<tr><td class="py-1">${k}</td><td class="py-1 text-gray-800">${v}</td></tr>`
  ).join("");

  // Additional specs from raw
  const promoted = new Set([
    "Model","URL","Category","Subcategory","Name",
    "Material & Finish","Images","Drawings","Has 2D Drawing",
    "Series Model","Item Code","Item Image","Series Images","Spec Sheet PDF",
    "Slug","Hero Image","Finish Image","CAD Drawings","Installation PDF","Brand",
    "Material","Finish","Height","Thickness","Load Capacity",
  ]);
  const extra = Object.entries(data.raw || {})
    .filter(([k, v]) => !promoted.has(k) && v != null && v !== "");
  if (extra.length) {
    document.getElementById("extra-specs").innerHTML = extra.map(([k, v]) =>
      `<tr><td class="py-1">${k}</td><td class="py-1 text-gray-800">${v}</td></tr>`
    ).join("");
  } else {
    document.getElementById("extra-section").classList.add("hidden");
  }

  // PDF link
  if (data.spec_pdf_url) {
    const a = document.getElementById("pdf-link");
    a.href = data.spec_pdf_url;
    a.classList.remove("hidden");
  }

  // Drawing links
  const drawings = data.drawing_urls || [];
  if (drawings.length) {
    document.getElementById("drawing-links").innerHTML = drawings.map(url => {
      const name = url.split("/").pop();
      return `<a href="${url}" target="_blank" download
                 class="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M4 16v1a2 2 0 002 2h12a2 2 0 002-2v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                ${name}
              </a>`;
    }).join("");
    document.getElementById("drawing-section").classList.remove("hidden");
  }

  document.getElementById("source-link").href = data.source_url || "#";
  document.getElementById("content").classList.remove("hidden");
  document.getElementById("loading").classList.add("hidden");
}
