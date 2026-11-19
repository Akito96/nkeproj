document.addEventListener("DOMContentLoaded", async () => {
  await window.auth.initHeader();
  const currentUser = await window.auth.requireRoleGuard(["client", "admin"]);
  if (!currentUser) return;

  const chipsContainer = document.getElementById("client-status-chips");
  const refreshBtn = document.getElementById("refresh-orders-btn");
  const listContainer = document.getElementById("client-orders-list");
  const detailContainer = document.getElementById("client-order-detail");

  const STATUS_FLOW = ["accepted", "diagnostics", "in_repair", "ready", "issued"];
  const preselectedId = Number(new URLSearchParams(window.location.search).get("order_id") || 0);

  const state = {
    statusFilter: "",
    orders: [],
    selectedOrderId: preselectedId || null,
  };

  function renderListSkeletons() {
    listContainer.innerHTML = `
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
    `;
  }

  function renderDetailSkeleton() {
    detailContainer.innerHTML = `
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
    `;
  }

  function updateChipStates() {
    chipsContainer?.querySelectorAll(".chip").forEach((chip) => {
      const status = chip.dataset.status || "";
      chip.setAttribute("aria-pressed", status === state.statusFilter ? "true" : "false");
    });
  }

  function renderOrdersList() {
    if (!state.orders || state.orders.length === 0) {
      const hasFilter = Boolean(state.statusFilter);
      listContainer.innerHTML = `
        <div class="card state-box">
          <p class="state-box__title">${hasFilter ? "По выбранному статусу заявок нет" : "У вас пока нет заявок"}</p>
          <p class="state-box__desc">${
            hasFilter
              ? "Попробуйте сбросить фильтр, чтобы увидеть все обращения."
              : "Оформите первую заявку на диагностику или ремонт устройства."
          }</p>
          <div class="hero__actions">
            ${
              hasFilter
                ? `<button type="button" id="reset-client-filter-btn" class="btn btn--outline btn--sm">Показать все</button>`
                : `<a class="btn btn--primary btn--sm" href="create-order.html">Оформить заявку</a>`
            }
          </div>
        </div>
      `;
      document.getElementById("reset-client-filter-btn")?.addEventListener("click", () => {
        state.statusFilter = "";
        updateChipStates();
        loadOrders();
      });
      return;
    }

    listContainer.innerHTML = state.orders
      .map((order) => {
        const isActive = order.id === state.selectedOrderId;
        const deviceName = `${order.device_brand} ${order.device_model}`;
        return `
          <button
            type="button"
            class="order-card${isActive ? " order-card--active" : ""}"
            data-order-id="${order.id}"
          >
            <div class="order-card__head">
              <span class="order-card__id">Заявка №${order.id}</span>
              ${window.ui.renderStatusBadge(order.status, order.status_label)}
            </div>
            <span class="order-card__device">${window.ui.escapeHtml(order.device_type)} · ${window.ui.escapeHtml(deviceName)}</span>
            <span class="order-card__desc">${window.ui.escapeHtml(order.problem_description)}</span>
            <div class="order-card__foot">
              <span>${window.ui.formatDateTime(order.created_at)}</span>
              <span class="order-card__price">${window.ui.formatPrice(order.total_cost)}</span>
            </div>
          </button>
        `;
      })
      .join("");
  }

  function renderProgressTracker(currentStatus) {
    const currentIdx = STATUS_FLOW.indexOf(currentStatus);
    return `
      <div>
        <h3 class="field__label" style="margin-block-end: 0.5rem;">Этап выполнения</h3>
        <ol class="progress-steps">
          ${STATUS_FLOW.map((st, idx) => {
            const label = window.APP_CONFIG.STATUS_META[st]?.label || st;
            let cls = "progress-step";
            if (idx < currentIdx) cls += " progress-step--done";
            else if (idx === currentIdx) cls += " progress-step--current";
            return `<li class="${cls}"${idx === currentIdx ? ' aria-current="step"' : ""}>${idx + 1}. ${window.ui.escapeHtml(label)}</li>`;
          }).join("")}
        </ol>
      </div>
    `;
  }

  function renderOrderDetail(order) {
    const history = [...(order.status_history || [])].sort(
      (a, b) => new Date(a.changed_at) - new Date(b.changed_at)
    );
    const publicComments = (order.comments || []).filter((c) => !c.is_internal);
    const parts = order.used_parts || [];
    const photos = order.photos || [];

    detailContainer.innerHTML = `
      <div class="section__header" style="margin-block-end: 0;">
        <div>
          <h2 class="section__title">Заявка №${order.id} — ${window.ui.escapeHtml(order.device_brand)} ${window.ui.escapeHtml(order.device_model)}</h2>
          <p class="section__subtitle">Создана ${window.ui.formatDateTime(order.created_at)}</p>
        </div>
        ${window.ui.renderStatusBadge(order.status, order.status_label)}
      </div>

      ${renderProgressTracker(order.status)}

      <div class="detail-grid">
        <div>
          <span class="detail-item__label">Тип устройства</span>
          <span class="detail-item__value">${window.ui.escapeHtml(order.device_type)}</span>
        </div>
        <div>
          <span class="detail-item__label">Серийный номер / IMEI</span>
          <span class="detail-item__value">${window.ui.escapeHtml(order.serial_number || "Не указан")}</span>
        </div>
        <div>
          <span class="detail-item__label">Внешний вид</span>
          <span class="detail-item__value">${window.ui.escapeHtml(order.appearance || "Без примечаний")}</span>
        </div>
        <div>
          <span class="detail-item__label">Последнее обновление</span>
          <span class="detail-item__value">${window.ui.formatDateTime(order.updated_at)}</span>
        </div>
      </div>

      <div>
        <h3 class="field__label" style="margin-block-end: 0.35rem;">Заявленная неисправность</h3>
        <p>${window.ui.escapeHtml(order.problem_description)}</p>
      </div>

      ${
        order.diagnostic_result
          ? `
        <div>
          <h3 class="field__label" style="margin-block-end: 0.35rem;">Результат диагностики</h3>
          <p>${window.ui.escapeHtml(order.diagnostic_result)}</p>
        </div>
      `
          : ""
      }

      <div class="cost-summary">
        <div class="cost-box">
          <span class="cost-box__label">Стоимость работ</span>
          <span class="cost-box__value">${window.ui.formatPrice(order.labor_cost)}</span>
        </div>
        <div class="cost-box">
          <span class="cost-box__label">Запчасти</span>
          <span class="cost-box__value">${window.ui.formatPrice(order.parts_cost)}</span>
        </div>
        <div class="cost-box cost-box--total">
          <span class="cost-box__label">Итого к оплате</span>
          <span class="cost-box__value">${window.ui.formatPrice(order.total_cost)}</span>
        </div>
      </div>

      <div>
        <h3 class="field__label" style="margin-block-end: 0.65rem;">Таймлайн статусов</h3>
        ${
          history.length > 0
            ? `
          <ol class="timeline">
            ${history
              .map((entry) => {
                const oldLabel = entry.old_status
                  ? window.APP_CONFIG.STATUS_META[entry.old_status]?.label || entry.old_status
                  : null;
                return `
                  <li class="timeline__item">
                    <div class="timeline__head">
                      <div>
                        ${oldLabel ? `<span class="field__hint">${window.ui.escapeHtml(oldLabel)} → </span>` : ""}
                        ${window.ui.renderStatusBadge(entry.new_status)}
                      </div>
                      <span class="timeline__time">${window.ui.formatDateTime(entry.changed_at)}</span>
                    </div>
                    ${entry.note ? `<p class="timeline__note">${window.ui.escapeHtml(entry.note)}</p>` : ""}
                  </li>
                `;
              })
              .join("")}
          </ol>
        `
            : `<p class="field__hint">История переходов пока пуста.</p>`
        }
      </div>

      ${
        parts.length > 0
          ? `
        <div>
          <h3 class="field__label" style="margin-block-end: 0.5rem;">Установленные запчасти</h3>
          <div class="table-wrapper" tabindex="0" role="region" aria-label="Установленные запчасти">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Наименование</th>
                  <th>Кол-во</th>
                  <th>Цена за шт.</th>
                  <th>Сумма</th>
                </tr>
              </thead>
              <tbody>
                ${parts
                  .map((rp) => {
                    const partName = rp.part ? `${rp.part.name} (${rp.part.sku})` : `Запчасть #${rp.part_id}`;
                    const subtotal = Number(rp.unit_price) * Number(rp.quantity);
                    return `
                      <tr>
                        <th scope="row">${window.ui.escapeHtml(partName)}</th>
                        <td data-label="Кол-во">${rp.quantity}</td>
                        <td data-label="Цена">${window.ui.formatPrice(rp.unit_price)}</td>
                        <td data-label="Сумма">${window.ui.formatPrice(subtotal)}</td>
                      </tr>
                    `;
                  })
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>
      `
          : ""
      }

      ${
        publicComments.length > 0
          ? `
        <div>
          <h3 class="field__label" style="margin-block-end: 0.5rem;">Комментарии мастера</h3>
          <div class="comments-list">
            ${publicComments
              .map(
                (comment) => `
              <article class="comment-item">
                <div class="comment-item__head">
                  <span class="badge badge--public">Комментарий по ремонту</span>
                  <span>${window.ui.formatDateTime(comment.created_at)}</span>
                </div>
                <p>${window.ui.escapeHtml(comment.comment_text)}</p>
              </article>
            `
              )
              .join("")}
          </div>
        </div>
      `
          : ""
      }

      ${
        photos.length > 0
          ? `
        <div>
          <h3 class="field__label" style="margin-block-end: 0.5rem;">Прикреплённые фото (${photos.length})</h3>
          <div class="photo-preview-grid">
            ${photos
              .map((photo) => {
                const src = window.ui.resolveAssetUrl(photo.file_url);
                return `
                  <a class="photo-preview-card" href="${src}" target="_blank" rel="noopener noreferrer">
                    <img class="photo-preview-card__img" src="${src}" alt="Фото к заявке №${order.id}" loading="lazy">
                  </a>
                `;
              })
              .join("")}
          </div>
        </div>
      `
          : ""
      }
    `;
  }

  async function selectOrder(orderId) {
    state.selectedOrderId = orderId;
    renderOrdersList();
    renderDetailSkeleton();

    try {
      const order = await window.api.getOrderById(orderId);
      renderOrderDetail(order);
    } catch (error) {
      detailContainer.innerHTML = `
        <div class="state-box">
          <p class="state-box__title">Не удалось загрузить детали заявки №${orderId}</p>
          <p class="state-box__desc">${window.ui.escapeHtml(error.message)}</p>
          <button type="button" id="retry-order-detail-btn" class="btn btn--primary btn--sm">Повторить</button>
        </div>
      `;
      document
        .getElementById("retry-order-detail-btn")
        ?.addEventListener("click", () => selectOrder(orderId));
    }
  }

  async function loadOrders() {
    renderListSkeletons();
    try {
      const orders = await window.api.getMyOrders({ status: state.statusFilter });
      state.orders = Array.isArray(orders) ? orders : [];
      if (
        state.selectedOrderId &&
        !state.orders.some((o) => o.id === state.selectedOrderId)
      ) {
        state.selectedOrderId = null;
      }
      if (!state.selectedOrderId && state.orders.length > 0) {
        state.selectedOrderId = state.orders[0].id;
      }
      renderOrdersList();

      if (state.selectedOrderId) {
        await selectOrder(state.selectedOrderId);
      } else {
        detailContainer.innerHTML = `
          <div class="state-box">
            <p class="state-box__title">Нет выбранной заявки</p>
            <p class="state-box__desc">Выберите заявку из списка слева или оформите новую заявку на ремонт.</p>
          </div>
        `;
      }
    } catch (error) {
      listContainer.innerHTML = `
        <div class="card state-box">
          <p class="state-box__title">Ошибка загрузки заявок</p>
          <p class="state-box__desc">${window.ui.escapeHtml(error.message)}</p>
          <button type="button" id="retry-orders-list-btn" class="btn btn--primary btn--sm">Повторить</button>
        </div>
      `;
      document
        .getElementById("retry-orders-list-btn")
        ?.addEventListener("click", loadOrders);
    }
  }

  chipsContainer?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement) || !target.classList.contains("chip")) {
      return;
    }
    state.statusFilter = target.dataset.status || "";
    updateChipStates();
    loadOrders();
  });

  listContainer?.addEventListener("click", (event) => {
    const card = event.target instanceof Element
      ? event.target.closest("[data-order-id]")
      : null;
    if (!card) return;
    const orderId = Number(card.getAttribute("data-order-id"));
    if (orderId) {
      selectOrder(orderId);
    }
  });

  refreshBtn?.addEventListener("click", loadOrders);

  await loadOrders();
});
