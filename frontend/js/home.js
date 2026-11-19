document.addEventListener("DOMContentLoaded", async () => {
  const user = await window.auth.initHeader();

  const cta = document.getElementById("hero-auth-cta");
  if (cta && user) {
    cta.textContent = "Перейти в кабинет";
    cta.href = window.auth.getRoleHomeUrl(user.role);
  }

  const badgesContainer = document.getElementById("hero-status-badges");
  if (badgesContainer) {
    const statuses = Object.keys(window.APP_CONFIG.STATUS_META);
    badgesContainer.innerHTML = statuses
      .map((status) => window.ui.renderStatusBadge(status))
      .join("");
  }

  const servicesContainer = document.getElementById("home-services-container");
  if (!servicesContainer) return;

  const CATEGORY_IMAGES = {
    "Смартфоны": "img/cat-smartphones.jpg",
    "Ноутбуки": "img/cat-laptops.jpg",
    "Пайка BGA": "img/cat-bga.jpg",
    "Планшеты": "img/cat-tablets.jpg",
    "ПК": "img/cat-pc.jpg",
  };

  const getCategoryImage = (category) =>
    CATEGORY_IMAGES[category] || "img/hero-repair.jpg";

  const loadPopular = async () => {
    servicesContainer.innerHTML = `
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
    `;
    try {
      const data = await window.api.getServices({ page: 1, size: 5 });
      if (!data.items || data.items.length === 0) {
        servicesContainer.innerHTML = `
          <div class="state-box">
            <p class="state-box__title">Прайс-лист пока пуст</p>
            <p class="state-box__desc">Администратор скоро добавит услуги.</p>
          </div>
        `;
        return;
      }

      servicesContainer.innerHTML = data.items
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
              <h3 class="price-row__title">${window.ui.escapeHtml(svc.title)}</h3>
              <p class="price-row__desc">${window.ui.escapeHtml(svc.description || "Диагностика и ремонт по регламенту сервисного центра")}</p>
            </div>
            <div class="price-row__meta">
              <span class="price-row__warranty">Гарантия ${svc.warranty_days} дн.</span>
              <span class="price-row__price">от ${window.ui.formatPrice(svc.base_price)}</span>
              <a class="btn btn--outline btn--sm" href="services.html">Подробнее</a>
            </div>
          </article>
        `
        )
        .join("");
    } catch (error) {
      servicesContainer.innerHTML = `
        <div class="state-box">
          <p class="state-box__title">Не удалось загрузить прайс-лист</p>
          <p class="state-box__desc">${window.ui.escapeHtml(error.message)}</p>
          <button type="button" id="retry-popular-btn" class="btn btn--primary btn--sm">Повторить</button>
        </div>
      `;
      document
        .getElementById("retry-popular-btn")
        ?.addEventListener("click", loadPopular);
    }
  };

  await loadPopular();
});
