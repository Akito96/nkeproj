document.addEventListener("DOMContentLoaded", async () => {
  await window.auth.initHeader();
  const currentUser = await window.auth.requireRoleGuard(["admin"]);
  if (!currentUser) return;

  const boardEl = document.getElementById("kanban-board");
  const stateBox = document.getElementById("kanban-state-box");
  const refreshBtn = document.getElementById("kanban-refresh-btn");
  const filterForm = document.getElementById("kanban-filter-form");
  const searchInput = document.getElementById("kanban-search-input");
  const masterFilter = document.getElementById("kanban-master-filter");

  const STATUS_COLUMNS = [
    { key: "accepted", title: "Принята" },
    { key: "diagnostics", title: "В диагностике" },
    { key: "in_repair", title: "В ремонте" },
    { key: "ready", title: "Готова к выдаче" },
    { key: "issued", title: "Выдана" },
  ];

  const state = {
    orders: [],
    usersById: new Map(),
    sortables: [],
  };

  function destroySortables() {
    state.sortables.forEach((instance) => {
      try {
        instance.destroy();
      } catch {
        // ignore destroy errors
      }
    });
    state.sortables = [];
  }

  function showLoading() {
    destroySortables();
    stateBox.hidden = true;
    boardEl.hidden = false;
    boardEl.innerHTML = STATUS_COLUMNS.map(
      (col) => `
      <div class="kanban-col">
        <div class="kanban-col__head">
          <span class="kanban-col__title">${window.ui.escapeHtml(col.title)}</span>
          <span class="kanban-col__count">…</span>
        </div>
        <div class="kanban-list">
          <div class="skeleton-row" aria-hidden="true"></div>
          <div class="skeleton-row" aria-hidden="true"></div>
        </div>
      </div>
    `
    ).join("");
  }

  function showError(message) {
    destroySortables();
    boardEl.hidden = true;
    stateBox.hidden = false;
    stateBox.innerHTML = `
      <div class="card state-box">
        <p class="state-box__title">Не удалось загрузить Kanban-доску</p>
        <p class="state-box__desc">${window.ui.escapeHtml(message)}</p>
        <button type="button" id="retry-kanban-btn" class="btn btn--primary btn--sm">Повторить</button>
      </div>
    `;
    document.getElementById("retry-kanban-btn")?.addEventListener("click", loadBoard);
  }

  function getFilteredOrders() {
    const query = (searchInput?.value || "").trim().toLowerCase();
    const masterVal = masterFilter?.value || "";
    return state.orders.filter((order) => {
      if (masterVal === "unassigned" && order.master_id !== null) return false;
      if (masterVal && masterVal !== "unassigned" && String(order.master_id) !== masterVal) {
        return false;
      }
      if (!query) return true;
      const hay = `#${order.id} ${order.device_type} ${order.device_brand} ${order.device_model} ${order.problem_description}`.toLowerCase();
      return hay.includes(query);
    });
  }

  function syncColumnCountersAndPlaceholders() {
    boardEl.querySelectorAll(".kanban-col").forEach((colEl) => {
      const listEl = colEl.querySelector(".kanban-list");
      const countEl = colEl.querySelector(".kanban-col__count");
      if (!listEl || !countEl) return;

      const cards = [...listEl.querySelectorAll(".kanban-card")];
      countEl.textContent = String(cards.length);

      const existingEmpty = listEl.querySelector(".kanban-empty");
      if (cards.length === 0 && !existingEmpty) {
        const emptyEl = document.createElement("div");
        emptyEl.className = "kanban-empty";
        emptyEl.textContent = "Нет заявок";
        listEl.append(emptyEl);
      } else if (cards.length > 0 && existingEmpty) {
        existingEmpty.remove();
      }
    });
  }

  function restoreCardPosition(cardEl, originList, oldIndex) {
    const currentCards = [...originList.querySelectorAll(".kanban-card")].filter(
      (el) => el !== cardEl
    );
    if (oldIndex >= 0 && oldIndex < currentCards.length) {
      originList.insertBefore(cardEl, currentCards[oldIndex]);
    } else {
      originList.append(cardEl);
    }
    syncColumnCountersAndPlaceholders();
  }

  function renderCardHtml(order) {
    const masterName = order.master_id
      ? state.usersById.get(order.master_id) || `Мастер #${order.master_id}`
      : "Не назначен";
    return `
      <article class="kanban-card" data-order-id="${order.id}" data-status="${order.status}">
        <div class="kanban-card__top">
          <span class="kanban-card__id">№${order.id}</span>
          <span>${window.ui.formatDateTime(order.created_at)}</span>
        </div>
        <h3 class="kanban-card__title">${window.ui.escapeHtml(order.device_brand)} ${window.ui.escapeHtml(order.device_model)}</h3>
        <p class="kanban-card__problem">${window.ui.escapeHtml(order.problem_description)}</p>
        <div class="kanban-card__meta">
          <span>${window.ui.escapeHtml(masterName)}</span>
          <span class="kanban-card__price">${window.ui.formatPrice(order.total_cost)}</span>
        </div>
      </article>
    `;
  }

  function initSortableColumns() {
    destroySortables();
    if (typeof window.Sortable === "undefined") {
      window.ui.showToast("Библиотека SortableJS не загрузилась", "error");
      return;
    }

    boardEl.querySelectorAll(".kanban-list").forEach((listEl) => {
      const sortable = new window.Sortable(listEl, {
        group: "repair-orders-kanban",
        draggable: ".kanban-card",
        animation: 160,
        ghostClass: "kanban-card--ghost",
        chosenClass: "kanban-card--chosen",
        onEnd: async (evt) => {
          const fromList = evt.from;
          const toList = evt.to;
          const cardEl = evt.item;
          const fromStatus = fromList.dataset.status;
          const toStatus = toList.dataset.status;

          if (!fromStatus || !toStatus || fromStatus === toStatus) {
            return;
          }

          const orderId = Number(cardEl.dataset.orderId);
          const toLabel = window.APP_CONFIG.STATUS_META[toStatus]?.label || toStatus;
          syncColumnCountersAndPlaceholders();
          cardEl.classList.add("kanban-card--pending");

          try {
            const updated = await window.api.updateOrderStatus(orderId, {
              status: toStatus,
              note: `Перенос на Kanban-доске в статус «${toLabel}»`,
            });
            cardEl.dataset.status = updated.status;
            const localOrder = state.orders.find((o) => o.id === orderId);
            if (localOrder) {
              localOrder.status = updated.status;
              localOrder.status_label = updated.status_label;
            }
            window.ui.showToast(
              `Заявка №${orderId} переведена в статус «${toLabel}»`,
              "success"
            );
          } catch (error) {
            restoreCardPosition(cardEl, fromList, evt.oldIndex);
            window.ui.showToast(
              `Заявка №${orderId}: ${error.message}`,
              "error"
            );
          } finally {
            cardEl.classList.remove("kanban-card--pending");
            syncColumnCountersAndPlaceholders();
          }
        },
      });
      state.sortables.push(sortable);
    });
  }

  function renderBoard() {
    const filtered = getFilteredOrders();
    stateBox.hidden = true;
    boardEl.hidden = false;

    boardEl.innerHTML = STATUS_COLUMNS.map((col) => {
      const colOrders = filtered.filter((o) => o.status === col.key);
      return `
        <section class="kanban-col" aria-label="Колонка ${window.ui.escapeHtml(col.title)}">
          <header class="kanban-col__head">
            <span class="kanban-col__title">${window.ui.escapeHtml(col.title)}</span>
            <span class="kanban-col__count">${colOrders.length}</span>
          </header>
          <div class="kanban-list" data-status="${col.key}">
            ${
              colOrders.length > 0
                ? colOrders.map(renderCardHtml).join("")
                : `<div class="kanban-empty">Нет заявок</div>`
            }
          </div>
        </section>
      `;
    }).join("");

    initSortableColumns();
  }

  function populateMastersFilter(users) {
    const currentValue = masterFilter?.value || "";
    const masters = users.filter((u) => u.role === "master");
    if (!masterFilter) return;
    masterFilter.innerHTML =
      `<option value="">Все мастера</option><option value="unassigned">Без мастера</option>` +
      masters
        .map(
          (m) =>
            `<option value="${m.id}"${String(m.id) === currentValue ? " selected" : ""}>${window.ui.escapeHtml(m.full_name)}</option>`
        )
        .join("");
  }

  async function loadBoard() {
    showLoading();
    try {
      const [orders, users] = await Promise.all([
        window.api.getAdminOrders(),
        window.api.getAdminUsers(),
      ]);
      state.orders = Array.isArray(orders) ? orders : [];
      state.usersById = new Map((users || []).map((u) => [u.id, u.full_name]));
      populateMastersFilter(users || []);
      renderBoard();
    } catch (error) {
      showError(error.message);
    }
  }

  filterForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    renderBoard();
  });
  searchInput?.addEventListener("input", renderBoard);
  masterFilter?.addEventListener("change", renderBoard);
  refreshBtn?.addEventListener("click", loadBoard);

  await loadBoard();
});
