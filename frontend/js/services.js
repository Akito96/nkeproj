document.addEventListener("DOMContentLoaded", async () => {
  await window.auth.initHeader();

  const searchForm = document.getElementById("services-search-form");
  const searchInput = document.getElementById("services-search");
  const chipsContainer = document.getElementById("category-chips");
  const listContainer = document.getElementById("services-list");
  const paginationEl = document.getElementById("services-pagination");
  const prevBtn = document.getElementById("prev-page-btn");
  const nextBtn = document.getElementById("next-page-btn");
  const pageInfoEl = document.getElementById("pagination-info");

  const state = {
    search: "",
    category: "",
    page: 1,
    size: 6,
    pages: 0,
  };

  const CATEGORY_IMAGES = {
    "Смартфоны": "img/cat-smartphones.jpg",
    "Ноутбуки": "img/cat-laptops.jpg",
    "Пайка BGA": "img/cat-bga.jpg",
    "Планшеты": "img/cat-tablets.jpg",
    "ПК": "img/cat-pc.jpg",
  };

  function getCategoryImage(category) {
    return CATEGORY_IMAGES[category] || "img/hero-repair.jpg";
  }

  function renderSkeletons() {
    listContainer.innerHTML = `
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
    `;
    paginationEl.hidden = true;
  }

  function updateChipStates() {
    chipsContainer?.querySelectorAll(".chip").forEach((chip) => {
      const cat = chip.dataset.category || "";
      chip.setAttribute("aria-pressed", cat === state.category ? "true" : "false");
    });
  }

  async function loadServices() {
    renderSkeletons();
    try {
      const data = await window.api.getServices({
        search: state.search,
        category: state.category,
        page: state.page,
        size: state.size,
      });

      state.pages = data.pages || 0;

      if (!data.items || data.items.length === 0) {
        listContainer.innerHTML = `
          <div class="state-box">
            <p class="state-box__title">Услуги не найдены</p>
            <p class="state-box__desc">По выбранным параметрам фильтрации и поиска ничего не найдено.</p>
            <button type="button" id="reset-filters-btn" class="btn btn--outline btn--sm">Сбросить фильтры</button>
          </div>
        `;
        document.getElementById("reset-filters-btn")?.addEventListener("click", () => {
          state.search = "";
          state.category = "";
          state.page = 1;
          if (searchInput) searchInput.value = "";
          updateChipStates();
          loadServices();
        });
        return;
      }

      listContainer.innerHTML = data.items
        .map(
          (svc) => `
          <article class="price-row">
            <img
              class="price-row__thumb"
              src="${getCategoryImage(svc.category)}"
              alt="${window.ui.escapeHtml(svc.category)}"
              loading="lazy"
              width="76"
              height="60"
            >
            <div class="price-row__main">
              <span class="price-row__cat">${window.ui.escapeHtml(svc.category)}</span>
              <h2 class="price-row__title">${window.ui.escapeHtml(svc.title)}</h2>
              <p class="price-row__desc">${window.ui.escapeHtml(svc.description || "Стандартный регламент обслуживания и проверки узлов.")}</p>
            </div>
            <div class="price-row__meta">
              <span class="price-row__warranty">Гарантия ${svc.warranty_days} дн.</span>
              <span class="price-row__price">от ${window.ui.formatPrice(svc.base_price)}</span>
              <a class="btn btn--primary btn--sm" href="create-order.html?service_id=${svc.id}">Записаться</a>
            </div>
          </article>
        `
        )
        .join("");

      if (state.pages > 1) {
        paginationEl.hidden = false;
        pageInfoEl.textContent = `Страница ${state.page} из ${state.pages} (всего: ${data.total})`;
        prevBtn.disabled = state.page <= 1;
        nextBtn.disabled = state.page >= state.pages;
      } else {
        paginationEl.hidden = true;
      }
    } catch (error) {
      listContainer.innerHTML = `
        <div class="state-box">
          <p class="state-box__title">Не удалось загрузить каталог</p>
          <p class="state-box__desc">${window.ui.escapeHtml(error.message)}</p>
          <button type="button" id="retry-services-btn" class="btn btn--primary btn--sm">Повторить попытку</button>
        </div>
      `;
      document
        .getElementById("retry-services-btn")
        ?.addEventListener("click", loadServices);
    }
  }

  searchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    state.search = (searchInput?.value || "").trim();
    state.page = 1;
    loadServices();
  });

  chipsContainer?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement) || !target.classList.contains("chip")) {
      return;
    }
    state.category = target.dataset.category || "";
    state.page = 1;
    updateChipStates();
    loadServices();
  });

  prevBtn?.addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      loadServices();
    }
  });

  nextBtn?.addEventListener("click", () => {
    if (state.page < state.pages) {
      state.page += 1;
      loadServices();
    }
  });

  await loadServices();
});
