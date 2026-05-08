/* app.js — shared Supabase client and utilities */

// SUPABASE_URL and SUPABASE_ANON_KEY are injected by index.html / product.html
// via a <script> block that sets window.ENV before this file loads.

const { createClient } = supabase;
const db = createClient(window.ENV.SUPABASE_URL, window.ENV.SUPABASE_ANON_KEY);

// ─── List page ────────────────────────────────────────────────────────────────

async function initList() {
  const searchInput  = document.getElementById("search");
  const brandFilter  = document.getElementById("brand-filter");
  const productList  = document.getElementById("product-list");
  const countEl      = document.getElementById("result-count");

  // Populate brand dropdown dynamically
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

    let query = db.from("products").select("id,brand,model,name,category,material,image_urls").order("brand").order("model").limit(200);

    if (brand) query = query.eq("brand", brand);
    if (q)     query = query.textSearch("search_tsv", q, { type: "websearch" });

    const { data, error } = await query;

    if (error) {
      productList.innerHTML = `<p class='text-red-400 py-8 text-center'>Error: ${error.message}</p>`;
      return;
    }

    countEl.textContent = `${data.length} product${data.length !== 1 ? "s" : ""}`;

    if (!data.length) {
      productList.innerHTML = "<p class='text-gray-400 py-8 text-center'>No products found.</p>";
      return;
    }

    productList.innerHTML = data.map(p => {
      const thumb = (p.image_urls || [])[0] || "";
      const cat   = p.category ? p.category.split(">").pop().trim() : "";
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
            ${p.material ? `<p class="text-xs text-gray-400 mt-0.5">${p.material}</p>` : ""}
          </div>
          <svg class="w-4 h-4 text-gray-300 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </a>`;
    }).join("");
  }

  fetchProducts();
}


// ─── Detail page ──────────────────────────────────────────────────────────────

async function initDetail() {
  const id = new URLSearchParams(location.search).get("id");
  if (!id) { location.href = "index.html"; return; }

  const { data, error } = await db.from("products").select("*").eq("id", id).single();

  if (error || !data) {
    document.getElementById("content").innerHTML =
      `<p class='text-red-400'>Product not found.</p>`;
    return;
  }

  document.title = `${data.model} — ELMES Product Viewer`;
  document.getElementById("breadcrumb-model").textContent = data.model;

  // Images
  const images = data.image_urls || [];
  const mainImg = document.getElementById("main-image");
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
    ["Brand",     data.brand],
    ["Model",     data.model],
    ["Category",  data.category],
    ["Material",  data.material],
    ["Finish",    data.finish],
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
    document.getElementById("drawing-links").innerHTML = drawings.map((url, i) => {
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
