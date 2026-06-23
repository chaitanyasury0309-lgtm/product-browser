const state = {
  cursor: null,
  snapshot: null,
  category: "",
  rows: 0,
};

const products = document.querySelector("#products");
const category = document.querySelector("#category");
const limit = document.querySelector("#limit");
const next = document.querySelector("#next");
const refresh = document.querySelector("#refresh");
const status = document.querySelector("#status");
const summary = document.querySelector("#summary");
const totalProducts = document.querySelector("#totalProducts");

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function shortDate(value) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(value));
}

function setStatus(text) {
  status.textContent = text;
}

function rowTemplate(item) {
  return `
    <tr>
      <td>
        <img class="product-thumb" src="${item.image_url}" alt="${item.category} product thumbnail">
      </td>
      <td>${item.id}</td>
      <td>${item.name}</td>
      <td>${item.category}</td>
      <td>${money(item.price)}</td>
      <td>${shortDate(item.created_at)}</td>
      <td>${shortDate(item.updated_at)}</td>
    </tr>
  `;
}

async function loadCategories() {
  const response = await fetch("/api/categories");
  const data = await response.json();
  const total = data.items.reduce((sum, item) => sum + item.count, 0);
  totalProducts.textContent = total.toLocaleString();
  for (const item of data.items) {
    const option = document.createElement("option");
    option.value = item.category;
    option.textContent = `${item.category} (${item.count.toLocaleString()})`;
    category.append(option);
  }
}

async function loadProducts({ reset = false } = {}) {
  if (reset) {
    state.cursor = null;
    state.snapshot = null;
    state.rows = 0;
    products.innerHTML = "";
  }

  next.disabled = true;
  setStatus("Loading...");

  const params = new URLSearchParams({ limit: limit.value });
  if (category.value) params.set("category", category.value);
  if (state.cursor) params.set("cursor", state.cursor);
  if (state.snapshot) params.set("snapshot", state.snapshot);

  const response = await fetch(`/api/products?${params}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Failed to load products");

  products.insertAdjacentHTML("beforeend", data.items.map(rowTemplate).join(""));
  state.cursor = data.next_cursor;
  state.snapshot = data.snapshot;
  state.rows += data.items.length;
  next.disabled = !data.next_cursor;
  summary.textContent = category.value
    ? `Browsing ${category.value} products newest first with a stable page snapshot.`
    : "Browse 200,000 seeded products newest first with stable cursor pagination.";
  setStatus(`${state.rows.toLocaleString()} products loaded`);
}

refresh.addEventListener("click", () => loadProducts({ reset: true }).catch((err) => setStatus(err.message)));
next.addEventListener("click", () => loadProducts().catch((err) => setStatus(err.message)));
category.addEventListener("change", () => loadProducts({ reset: true }).catch((err) => setStatus(err.message)));
limit.addEventListener("change", () => loadProducts({ reset: true }).catch((err) => setStatus(err.message)));

loadCategories()
  .then(() => loadProducts({ reset: true }))
  .catch((err) => setStatus(err.message));
