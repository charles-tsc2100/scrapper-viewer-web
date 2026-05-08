/* app.js — shared Supabase client, auth guard, list + detail logic */

const { createClient } = supabase;
const db = createClient(window.ENV.SUPABASE_URL, window.ENV.SUPABASE_ANON_KEY);

function downloadFile(url, filename) {
  fetch(url)
    .then(r => { if (!r.ok) throw new Error("fetch failed"); return r.blob(); })
    .then(blob => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(a.href), 100);
    })
    .catch(() => window.open(url, "_blank"));
}

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


// ─── Gallery ──────────────────────────────────────────────────────────────────

window._galleryImages = [];

function openGallery(startIdx = 0) {
  const modal = document.getElementById("gallery-modal");
  modal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  _setGalleryMain(startIdx);
  document.getElementById("gallery-thumbs").innerHTML = window._galleryImages.map((url, i) =>
    `<img src="${url}" class="${i === startIdx ? "active" : ""}"
          onclick="_setGalleryMain(${i})">`
  ).join("");
}

function _setGalleryMain(idx) {
  document.getElementById("gallery-main-img").src = window._galleryImages[idx];
  document.querySelectorAll("#gallery-thumbs img").forEach((img, i) =>
    img.classList.toggle("active", i === idx)
  );
}

function closeGallery() {
  document.getElementById("gallery-modal").classList.add("hidden");
  document.body.style.overflow = "";
}


// (DXF canvas viewer removed — drawing JPGs now appear in the image gallery)

function viewDrawing(url, name) {
  const viewer = document.getElementById("drawing-viewer");
  document.getElementById("drawing-viewer-name").textContent = name;
  document.getElementById("drawing-viewer-wrap").innerHTML =
    `<img src="${url}" alt="${name}" style="max-width:100%;max-height:480px;object-fit:contain;">`;
  viewer.classList.remove("hidden");
  viewer.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function closeDrawingViewer() {
  document.getElementById("drawing-viewer").classList.add("hidden");
}


// ─── Detail page ──────────────────────────────────────────────────────────────

function setMainImage(el, url) {
  document.getElementById("main-image").src = url;
  document.querySelectorAll(".thumb-strip img").forEach(img => img.classList.remove("active"));
  el.classList.add("active");
}

async function initDetail() {
  await requireAuth();

  const id = new URLSearchParams(location.search).get("id");
  if (!id) { location.href = "index.html"; return; }

  const { data, error } = await db.from("products").select("*").eq("id", id).single();

  if (error || !data) {
    document.getElementById("content").innerHTML = `<p class='text-red-400'>Product not found.</p>`;
    return;
  }

  document.title = `${data.model} — Product Catalogue`;
  document.getElementById("breadcrumb-model").textContent = data.model;

  // Images — 1-row strip, max 5 thumbnails shown; Show more opens gallery
  const images = data.image_urls || [];
  window._galleryImages = images;
  const mainImg   = document.getElementById("main-image");
  const strip     = document.getElementById("thumb-strip");
  const showAllBtn = document.getElementById("show-all-btn");

  if (images.length) {
    mainImg.src = images[0];
    mainImg.alt = data.model;
    const MAX_THUMBS = 5;
    const visible = images.slice(0, MAX_THUMBS);
    strip.innerHTML = visible.map((url, i) =>
      `<img src="${url}" alt="${data.model} ${i + 1}" class="${i === 0 ? "active" : ""}"
            onclick="setMainImage(this, '${url}')">`
    ).join("");
    if (images.length > 1) {
      const extra = images.length - MAX_THUMBS;
      showAllBtn.textContent = extra > 0 ? `Show more (${extra} more)` : "Show all";
      showAllBtn.classList.remove("hidden");
    }
  } else {
    mainImg.parentElement.classList.add("hidden");
  }

  // Core spec table
  const specRows = [
    ["Brand",         data.brand],
    ["Model",         data.model],
    ["Category",      data.category],
    ["Subcategory",   data.subcategory],
    ["Material",      data.material],
    ["Finish",        data.finish],
    ["Load Capacity",  data.load_capacity_kg  != null ? `${data.load_capacity_kg} kg`  : null],
    ["Max Door Height",data.door_height_mm    != null ? `${data.door_height_mm} mm`    : null],
    ["Max Door Width", data.door_width_mm     != null ? `${data.door_width_mm} mm`     : null],
    ["Door Thickness", data.door_thickness_mm != null ? `${data.door_thickness_mm} mm` : null],
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
  const extra = Object.entries(data.raw || {}).filter(([k, v]) => !promoted.has(k) && v != null && v !== "");
  if (extra.length) {
    document.getElementById("extra-specs").innerHTML = extra.map(([k, v]) =>
      `<tr><td class="py-1">${k}</td><td class="py-1 text-gray-800">${v}</td></tr>`
    ).join("");
  } else {
    document.getElementById("extra-section").classList.add("hidden");
  }

  // Spec Sheet PDF button
  if (data.spec_pdf_url) {
    const pdfUrl  = data.spec_pdf_url;
    const pdfName = decodeURIComponent(pdfUrl.split("/").pop().split("?")[0]);
    const a = document.getElementById("pdf-link");
    a.onclick = e => { e.preventDefault(); downloadFile(pdfUrl, pdfName); };
    a.classList.remove("hidden");
  }

  // drawing_urls now only contains non-image files (DXF, SVG, PDF)
  const drawings    = data.drawing_urls || [];
  const pdfDrawings = drawings.filter(u => u.toLowerCase().split("?")[0].endsWith(".pdf"));
  const cadFiles    = drawings.filter(u => !u.toLowerCase().split("?")[0].endsWith(".pdf"));

  // PDFs listed directly below the Spec Sheet button
  if (pdfDrawings.length) {
    document.getElementById("extra-pdf-links").innerHTML = pdfDrawings.map(url => {
      const name = decodeURIComponent(url.split("/").pop().split("?")[0]);
      return `<a href="#" onclick="event.preventDefault(); downloadFile('${url}', '${name}')"
                 class="inline-flex items-center gap-2 text-sm text-red-700 hover:underline cursor-pointer">
                <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
                </svg>
                ${name}
              </a>`;
    }).join("");
  }

  // CAD/DXF files — view button for images, download for all
  const _viewableExts = new Set([".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]);
  if (cadFiles.length) {
    document.getElementById("drawing-links").innerHTML = cadFiles.map(url => {
      const name = decodeURIComponent(url.split("/").pop().split("?")[0]);
      const ext  = ("." + name.split(".").pop()).toLowerCase();
      const canView = _viewableExts.has(ext);
      const viewBtn = canView
        ? `<button onclick="viewDrawing('${url}', '${name}')"
                   class="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 text-xs font-medium hover:bg-blue-100 transition-colors">
             <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
             </svg>
             View
           </button>`
        : "";
      return `<div class="flex items-center gap-2">
                ${viewBtn}
                <a href="#" onclick="event.preventDefault(); downloadFile('${url}', '${name}')"
                   class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-xs font-medium hover:bg-gray-200 transition-colors">
                  <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M4 16v1a2 2 0 002 2h12a2 2 0 002-2v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                  </svg>
                  ${name}
                </a>
              </div>`;
    }).join("");
    document.getElementById("drawing-section").classList.remove("hidden");
  }

  document.getElementById("source-link").href = data.source_url || "#";
  document.getElementById("content").classList.remove("hidden");
  document.getElementById("loading").classList.add("hidden");
}
