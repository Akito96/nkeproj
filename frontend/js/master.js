document.addEventListener("DOMContentLoaded", async () => {
  await window.auth.initHeader();
  const currentUser = await window.auth.requireRoleGuard(["master", "admin"]);
  if (!currentUser) return;

  const subtitleEl = document.getElementById("master-subtitle");
  if (subtitleEl && currentUser.role === "admin") {
    subtitleEl.textContent = "Режим администратора: просмотр и обработка всех заявок мастерской";
  }

  const refreshBtn = document.getElementById("refresh-master-btn");
  const searchForm = document.getElementById("master-search-form");
  const searchInput = document.getElementById("master-search-input");
  const chipsContainer = document.getElementById("master-status-chips");
  const listContainer = document.getElementById("master-orders-list");
  const workspaceEl = document.getElementById("master-order-workspace");

  const state = {
    statusFilter: "",
    search: "",
    orders: [],
    parts: [],
    selectedOrderId: null,
    selectedOrder: null,
    draftParts: [],
  };

  function renderListSkeletons() {
    listContainer.innerHTML = `
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
    `;
  }

  function renderWorkspaceSkeleton() {
    workspaceEl.innerHTML = `
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

  function getFilteredOrders() {
    const query = state.search.trim().toLowerCase();
    if (!query) return state.orders;
    return state.orders.filter((order) => {
      const haystack = `#${order.id} ${order.device_type} ${order.device_brand} ${order.device_model} ${order.problem_description}`.toLowerCase();
      return haystack.includes(query);
    });
  }

  function renderOrdersList() {
    const items = getFilteredOrders();
    if (items.length === 0) {
      const hasFilters = Boolean(state.statusFilter || state.search);
      listContainer.innerHTML = `
        <div class="card state-box">
          <p class="state-box__title">${hasFilters ? "Подходящих заявок не найдено" : "Назначенных заявок пока нет"}</p>
          <p class="state-box__desc">${
            hasFilters
              ? "Попробуйте изменить параметры поиска или сбросить фильтр статуса."
              : "Как только администратор назначит вам заявку, она появится в этом списке."
          }</p>
          ${
            hasFilters
              ? `<button type="button" id="reset-master-filter-btn" class="btn btn--outline btn--sm">Сбросить фильтры</button>`
              : ""
          }
        </div>
      `;
      document.getElementById("reset-master-filter-btn")?.addEventListener("click", () => {
        state.statusFilter = "";
        state.search = "";
        if (searchInput) searchInput.value = "";
        updateChipStates();
        loadData();
      });
      return;
    }

    listContainer.innerHTML = items
      .map((order) => {
        const isActive = order.id === state.selectedOrderId;
        const deviceTitle = `${order.device_brand} ${order.device_model}`;
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
            <span class="order-card__device">${window.ui.escapeHtml(order.device_type)} · ${window.ui.escapeHtml(deviceTitle)}</span>
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

  function renderDraftPartsList() {
    const container = document.getElementById("draft-parts-container");
    if (!container) return;
    if (state.draftParts.length === 0) {
      container.innerHTML = `<p class="field__hint">Список к списанию пуст. Выберите запчасть ниже и нажмите «Добавить в список».</p>`;
      return;
    }
    container.innerHTML = state.draftParts
      .map(
        (item, idx) => `
        <div class="part-draft-row">
          <span>
            <strong>${window.ui.escapeHtml(item.name)}</strong> (${window.ui.escapeHtml(item.sku)}) —
            ${item.quantity} шт. × ${window.ui.formatPrice(item.retail_price)}
          </span>
          <button type="button" class="btn btn--ghost btn--sm" data-remove-draft="${idx}">Убрать</button>
        </div>
      `
      )
      .join("");
  }

  function renderWorkspace(order) {
    const transitions = window.APP_CONFIG.ALLOWED_STATUS_TRANSITIONS[order.status] || [];
    const history = [...(order.status_history || [])].sort(
      (a, b) => new Date(b.changed_at) - new Date(a.changed_at)
    );
    const comments = [...(order.comments || [])].sort(
      (a, b) => new Date(b.created_at) - new Date(a.created_at)
    );
    const usedParts = order.used_parts || [];
    const photos = order.photos || [];
    const isIssued = order.status === "issued";

    const availablePartsOptions = state.parts
      .map((part) => {
        const disabledAttr = part.stock_qty <= 0 ? " disabled" : "";
        const lowTag = part.is_low_stock ? " [мало]" : "";
        return `
          <option value="${part.id}"${disabledAttr}>
            ${window.ui.escapeHtml(part.name)} (${window.ui.escapeHtml(part.sku)}) — ост. ${part.stock_qty} шт.${lowTag} · ${window.ui.formatPrice(part.retail_price)}
          </option>
        `;
      })
      .join("");

    workspaceEl.innerHTML = `
      <div class="section__header" style="margin-block-end: 0;">
        <div>
          <h2 class="section__title">Заявка №${order.id} — ${window.ui.escapeHtml(order.device_brand)} ${window.ui.escapeHtml(order.device_model)}</h2>
          <p class="section__subtitle">Тип: ${window.ui.escapeHtml(order.device_type)} · Создана ${window.ui.formatDateTime(order.created_at)}</p>
        </div>
        ${window.ui.renderStatusBadge(order.status, order.status_label)}
      </div>

      <div class="detail-grid">
        <div>
          <span class="detail-item__label">Серийный номер / IMEI</span>
          <span class="detail-item__value">${window.ui.escapeHtml(order.serial_number || "Не указан")}</span>
        </div>
        <div>
          <span class="detail-item__label">Внешний вид</span>
          <span class="detail-item__value">${window.ui.escapeHtml(order.appearance || "Без примечаний")}</span>
        </div>
        <div>
          <span class="detail-item__label">Неисправность (от клиента)</span>
          <span class="detail-item__value">${window.ui.escapeHtml(order.problem_description)}</span>
        </div>
      </div>

      ${
        photos.length > 0
          ? `
        <div>
          <h3 class="field__label" style="margin-block-end: 0.45rem;">Фотографии приёмки (${photos.length})</h3>
          <div class="photo-preview-grid">
            ${photos
              .map((photo) => {
                const src = window.ui.resolveAssetUrl(photo.file_url);
                return `
                  <a class="photo-preview-card" href="${src}" target="_blank" rel="noopener noreferrer">
                    <img class="photo-preview-card__img" src="${src}" alt="Фото заявки №${order.id}" loading="lazy">
                  </a>
                `;
              })
              .join("")}
          </div>
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
          <span class="cost-box__label">Списано запчастей</span>
          <span class="cost-box__value">${window.ui.formatPrice(order.parts_cost)}</span>
        </div>
        <div class="cost-box cost-box--total">
          <span class="cost-box__label">Итого по заявке</span>
          <span class="cost-box__value">${window.ui.formatPrice(order.total_cost)}</span>
        </div>
      </div>

      <section aria-labelledby="master-status-title" style="padding-block-start: 0.75rem; border-block-start: 1px solid var(--color-border-light);">
        <h3 id="master-status-title" class="section__title" style="font-size: 1.05rem; margin-block-end: 0.65rem;">Смена статуса заявки</h3>
        ${
          transitions.length > 0
            ? `
          <form id="master-status-form" class="form" novalidate>
            <div class="form-grid-2">
              <div class="field">
                <label class="field__label" for="next-status-select">Следующий допустимый статус</label>
                <select id="next-status-select" name="status" class="field__control" required>
                  ${transitions
                    .map((st) => {
                      const label = window.APP_CONFIG.STATUS_META[st]?.label || st;
                      return `<option value="${st}">${window.ui.escapeHtml(label)}</option>`;
                    })
                    .join("")}
                </select>
              </div>
              <div class="field">
                <label class="field__label" for="status-note-input">Комментарий к переходу</label>
                <input
                  type="text"
                  id="status-note-input"
                  name="note"
                  class="field__control"
                  maxlength="255"
                  placeholder="Например, передано на тестирование"
                >
              </div>
            </div>
            <div>
              <button type="submit" id="save-status-btn" class="btn btn--primary btn--sm">Перевести статус</button>
            </div>
          </form>
        `
            : `<p class="field__hint">Заявка находится на финальном этапе («Выдана»); дальнейшая смена статуса невозможна.</p>`
        }
      </section>

      <section aria-labelledby="master-parts-title" style="padding-block-start: 0.75rem; border-block-start: 1px solid var(--color-border-light);">
        <h3 id="master-parts-title" class="section__title" style="font-size: 1.05rem; margin-block-end: 0.65rem;">Диагностика, стоимость работ и списание запчастей</h3>
        ${
          isIssued
            ? `<p class="field__hint">Выданную заявку нельзя изменять.</p>`
            : `
          <form id="master-parts-labor-form" class="form" novalidate>
            <div class="field">
              <label class="field__label" for="diagnostic-result-input">Результат диагностики</label>
              <textarea
                id="diagnostic-result-input"
                name="diagnostic_result"
                class="field__control"
                rows="3"
                placeholder="Опишите выявленную неисправность и план ремонта"
              >${window.ui.escapeHtml(order.diagnostic_result || "")}</textarea>
            </div>

            <div class="form-grid-2">
              <div class="field">
                <label class="field__label" for="labor-cost-input">Стоимость работ (₽)</label>
                <input
                  type="number"
                  id="labor-cost-input"
                  name="labor_cost"
                  class="field__control"
                  min="0"
                  step="0.01"
                  value="${Number(order.labor_cost)}"
                >
              </div>
            </div>

            <div class="photo-upload-zone">
              <span class="field__label">Добавить запчасти со склада к списанию</span>
              <div class="form-grid-2">
                <div class="field">
                  <label class="field__label" for="part-picker-select">Запчасть</label>
                  <select id="part-picker-select" class="field__control">
                    <option value="">Выберите запчасть со склада...</option>
                    ${availablePartsOptions}
                  </select>
                </div>
                <div class="field">
                  <label class="field__label" for="part-picker-qty">Количество (шт.)</label>
                  <div style="display: flex; gap: 0.5rem;">
                    <input type="number" id="part-picker-qty" class="field__control" min="1" step="1" value="1">
                    <button type="button" id="add-draft-part-btn" class="btn btn--outline btn--sm">Добавить в список</button>
                  </div>
                </div>
              </div>
              <div id="draft-parts-container" class="parts-draft-list"></div>
            </div>

            <div>
              <button type="submit" id="apply-parts-labor-btn" class="btn btn--primary btn--sm">Сохранить работы и списать запчасти</button>
            </div>
          </form>
        `
        }

        ${
          usedParts.length > 0
            ? `
          <div style="margin-block-start: 1rem;">
            <h4 class="field__label" style="margin-block-end: 0.45rem;">Уже списанные запчасти</h4>
            <div class="table-wrapper" tabindex="0" role="region" aria-label="Списанные запчасти">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Запчасть</th>
                    <th>Кол-во</th>
                    <th>Цена</th>
                    <th>Сумма</th>
                  </tr>
                </thead>
                <tbody>
                  ${usedParts
                    .map((rp) => {
                      const label = rp.part ? `${rp.part.name} (${rp.part.sku})` : `ID ${rp.part_id}`;
                      const sum = Number(rp.unit_price) * Number(rp.quantity);
                      return `
                        <tr>
                          <th scope="row">${window.ui.escapeHtml(label)}</th>
                          <td data-label="Кол-во">${rp.quantity}</td>
                          <td data-label="Цена">${window.ui.formatPrice(rp.unit_price)}</td>
                          <td data-label="Сумма">${window.ui.formatPrice(sum)}</td>
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
      </section>

      <section aria-labelledby="master-comments-title" style="padding-block-start: 0.75rem; border-block-start: 1px solid var(--color-border-light);">
        <h3 id="master-comments-title" class="section__title" style="font-size: 1.05rem; margin-block-end: 0.65rem;">Комментарии по заявке</h3>
        <form id="master-comment-form" class="form" novalidate style="margin-block-end: 0.9rem;">
          <div class="field">
            <label class="field__label" for="comment-text-input">Новый комментарий</label>
            <textarea
              id="comment-text-input"
              name="comment_text"
              class="field__control"
              rows="2"
              placeholder="Напишите комментарий для клиента или внутреннюю заметку..."
              required
              data-error="comment-text-error"
            ></textarea>
            <span id="comment-text-error" class="field__error">Введите текст комментария.</span>
          </div>
          <div class="hero__actions" style="align-items: center; justify-content: space-between;">
            <label style="display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.88rem; cursor: pointer;">
              <input type="checkbox" id="comment-internal-checkbox" name="is_internal" style="inline-size: 1.1rem; block-size: 1.1rem; accent-color: var(--color-primary);">
              <span>Внутренний комментарий (скрыт от клиента)</span>
            </label>
            <button type="submit" id="send-comment-btn" class="btn btn--outline btn--sm">Добавить комментарий</button>
          </div>
        </form>

        <div class="comments-list">
          ${
            comments.length > 0
              ? comments
                  .map(
                    (c) => `
                  <article class="comment-item${c.is_internal ? " comment-item--internal" : ""}">
                    <div class="comment-item__head">
                      <span class="badge ${c.is_internal ? "badge--internal" : "badge--public"}">${
                        c.is_internal ? "Внутренний" : "Для клиента"
                      }</span>
                      <span>${window.ui.formatDateTime(c.created_at)}</span>
                    </div>
                    <p>${window.ui.escapeHtml(c.comment_text)}</p>
                  </article>
                `
                  )
                  .join("")
              : `<p class="field__hint">Комментариев пока нет.</p>`
          }
        </div>
      </section>

      ${
        history.length > 0
          ? `
        <section aria-labelledby="master-history-title" style="padding-block-start: 0.75rem; border-block-start: 1px solid var(--color-border-light);">
          <h3 id="master-history-title" class="section__title" style="font-size: 1.05rem; margin-block-end: 0.65rem;">История статусов</h3>
          <ol class="timeline">
            ${history
              .map(
                (entry) => `
                <li class="timeline__item">
                  <div class="timeline__head">
                    ${window.ui.renderStatusBadge(entry.new_status)}
                    <span class="timeline__time">${window.ui.formatDateTime(entry.changed_at)}</span>
                  </div>
                  ${entry.note ? `<p class="timeline__note">${window.ui.escapeHtml(entry.note)}</p>` : ""}
                </li>
              `
              )
              .join("")}
          </ol>
        </section>
      `
          : ""
      }
    `;

    renderDraftPartsList();
    bindWorkspaceHandlers(order);
  }

  function bindWorkspaceHandlers(order) {
    const statusForm = document.getElementById("master-status-form");
    statusForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const btn = document.getElementById("save-status-btn");
      const nextStatus = document.getElementById("next-status-select").value;
      const note = document.getElementById("status-note-input").value.trim() || null;

      btn.disabled = true;
      btn.textContent = "Сохранение...";
      try {
        const updated = await window.api.updateOrderStatus(order.id, {
          status: nextStatus,
          note,
        });
        window.ui.showToast("Статус заявки обновлён", "success");
        await refreshAfterMutation(updated);
      } catch (error) {
        window.ui.showToast(error.message, "error");
        btn.disabled = false;
        btn.textContent = "Перевести статус";
      }
    });

    const partsForm = document.getElementById("master-parts-labor-form");
    if (partsForm) {
      document.getElementById("add-draft-part-btn")?.addEventListener("click", () => {
        const partId = Number(document.getElementById("part-picker-select").value || 0);
        const qty = Number(document.getElementById("part-picker-qty").value || 0);
        if (!partId) {
          window.ui.showToast("Выберите запчасть из списка", "error");
          return;
        }
        if (!Number.isInteger(qty) || qty < 1) {
          window.ui.showToast("Количество должно быть целым числом больше 0", "error");
          return;
        }
        const part = state.parts.find((p) => p.id === partId);
        if (!part) return;

        const alreadyDrafted = state.draftParts
          .filter((d) => d.part_id === partId)
          .reduce((acc, d) => acc + d.quantity, 0);
        if (alreadyDrafted + qty > part.stock_qty) {
          window.ui.showToast(
            `Недостаточно на складе «${part.name}»: доступно ${part.stock_qty} шт.`,
            "error"
          );
          return;
        }

        const existing = state.draftParts.find((d) => d.part_id === partId);
        if (existing) {
          existing.quantity += qty;
        } else {
          state.draftParts.push({
            part_id: part.id,
            name: part.name,
            sku: part.sku,
            retail_price: part.retail_price,
            quantity: qty,
          });
        }
        renderDraftPartsList();
      });

      document
        .getElementById("draft-parts-container")
        ?.addEventListener("click", (event) => {
          const btn = event.target instanceof Element
            ? event.target.closest("[data-remove-draft]")
            : null;
          if (!btn) return;
          const idx = Number(btn.getAttribute("data-remove-draft"));
          if (Number.isInteger(idx)) {
            state.draftParts.splice(idx, 1);
            renderDraftPartsList();
          }
        });

      partsForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const diagVal = document.getElementById("diagnostic-result-input").value.trim();
        const laborRaw = document.getElementById("labor-cost-input").value;
        const payload = {};

        if (diagVal) {
          payload.diagnostic_result = diagVal;
        }
        if (laborRaw !== "") {
          const laborNum = Number(laborRaw);
          if (Number.isNaN(laborNum) || laborNum < 0) {
            window.ui.showToast("Стоимость работ не может быть отрицательной", "error");
            return;
          }
          payload.labor_cost = laborNum;
        }
        if (state.draftParts.length > 0) {
          payload.parts = state.draftParts.map((d) => ({
            part_id: d.part_id,
            quantity: d.quantity,
          }));
        }

        if (Object.keys(payload).length === 0) {
          window.ui.showToast("Укажите диагностику, стоимость работ или запчасти", "error");
          return;
        }

        const btn = document.getElementById("apply-parts-labor-btn");
        btn.disabled = true;
        btn.textContent = "Проведение...";
        try {
          const updated = await window.api.addOrderPartsAndLabor(order.id, payload);
          state.draftParts = [];
          window.ui.showToast("Работы и запчасти сохранены", "success");
          await refreshAfterMutation(updated);
        } catch (error) {
          window.ui.showToast(error.message, "error");
          btn.disabled = false;
          btn.textContent = "Сохранить работы и списать запчасти";
        }
      });
    }

    const commentForm = document.getElementById("master-comment-form");
    if (commentForm) {
      const commentValidator = window.ui.initFormValidation(commentForm);
      commentForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!commentValidator.validateForm(commentForm)) {
          return;
        }
        const commentText = document.getElementById("comment-text-input").value.trim();
        const isInternal = document.getElementById("comment-internal-checkbox").checked;
        const btn = document.getElementById("send-comment-btn");

        btn.disabled = true;
        btn.textContent = "Отправка...";
        try {
          await window.api.addOrderComment(order.id, {
            comment_text: commentText,
            is_internal: isInternal,
          });
          window.ui.showToast("Комментарий добавлен", "success");
          await selectOrder(order.id);
        } catch (error) {
          window.ui.showToast(error.message, "error");
          btn.disabled = false;
          btn.textContent = "Добавить комментарий";
        }
      });
    }
  }

  async function selectOrder(orderId) {
    state.selectedOrderId = orderId;
    state.draftParts = [];
    renderOrdersList();
    renderWorkspaceSkeleton();
    try {
      const order = await window.api.getOrderById(orderId);
      state.selectedOrder = order;
      renderWorkspace(order);
    } catch (error) {
      workspaceEl.innerHTML = `
        <div class="state-box">
          <p class="state-box__title">Не удалось загрузить заявку №${orderId}</p>
          <p class="state-box__desc">${window.ui.escapeHtml(error.message)}</p>
          <button type="button" id="retry-master-detail-btn" class="btn btn--primary btn--sm">Повторить</button>
        </div>
      `;
      document
        .getElementById("retry-master-detail-btn")
        ?.addEventListener("click", () => selectOrder(orderId));
    }
  }

  async function refreshAfterMutation(updatedOrder) {
    try {
      const [orders, parts] = await Promise.all([
        currentUser.role === "admin"
          ? window.api.getAdminOrders({ status: state.statusFilter })
          : window.api.getMasterOrders({ status: state.statusFilter }),
        window.api.getParts(),
      ]);
      state.orders = Array.isArray(orders) ? orders : [];
      state.parts = Array.isArray(parts) ? parts : [];
      state.selectedOrder = updatedOrder;
      renderOrdersList();
      renderWorkspace(updatedOrder);
    } catch {
      renderWorkspace(updatedOrder);
    }
  }

  async function loadData() {
    renderListSkeletons();
    try {
      const [orders, parts] = await Promise.all([
        currentUser.role === "admin"
          ? window.api.getAdminOrders({ status: state.statusFilter })
          : window.api.getMasterOrders({ status: state.statusFilter }),
        window.api.getParts(),
      ]);
      state.orders = Array.isArray(orders) ? orders : [];
      state.parts = Array.isArray(parts) ? parts : [];

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
        workspaceEl.innerHTML = `
          <div class="state-box">
            <p class="state-box__title">Нет выбранной заявки</p>
            <p class="state-box__desc">Выберите заявку из списка слева для диагностики и ремонта.</p>
          </div>
        `;
      }
    } catch (error) {
      listContainer.innerHTML = `
        <div class="card state-box">
          <p class="state-box__title">Ошибка загрузки рабочего места</p>
          <p class="state-box__desc">${window.ui.escapeHtml(error.message)}</p>
          <button type="button" id="retry-master-list-btn" class="btn btn--primary btn--sm">Повторить</button>
        </div>
      `;
      document
        .getElementById("retry-master-list-btn")
        ?.addEventListener("click", loadData);
    }
  }

  searchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    state.search = searchInput?.value || "";
    renderOrdersList();
  });

  searchInput?.addEventListener("input", () => {
    state.search = searchInput.value || "";
    renderOrdersList();
  });

  chipsContainer?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement) || !target.classList.contains("chip")) {
      return;
    }
    state.statusFilter = target.dataset.status || "";
    updateChipStates();
    loadData();
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

  refreshBtn?.addEventListener("click", loadData);

  await loadData();
});
