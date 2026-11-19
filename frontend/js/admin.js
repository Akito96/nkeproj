document.addEventListener("DOMContentLoaded", async () => {
  await window.auth.initHeader();
  const currentUser = await window.auth.requireRoleGuard(["admin"]);
  if (!currentUser) return;

  window.ui.initDialogs();

  const tabButtons = [...document.querySelectorAll('.tabs-bar [role="tab"]')];
  const tabPanels = [...document.querySelectorAll('[role="tabpanel"]')];

  const ordersContent = document.getElementById("admin-orders-content");
  const usersContent = document.getElementById("admin-users-content");
  const servicesContent = document.getElementById("admin-services-content");
  const inventoryContent = document.getElementById("admin-inventory-content");

  const ordersSearchForm = document.getElementById("orders-search-form");
  const ordersSearchInput = document.getElementById("orders-search-input");
  const ordersStatusFilter = document.getElementById("orders-status-filter");

  const usersSearchForm = document.getElementById("users-search-form");
  const usersSearchInput = document.getElementById("users-search-input");
  const usersRoleFilter = document.getElementById("users-role-filter");

  const servicesSearchForm = document.getElementById("admin-services-search-form");
  const servicesSearchInput = document.getElementById("admin-services-search-input");

  const inventorySearchForm = document.getElementById("inventory-search-form");
  const inventorySearchInput = document.getElementById("inventory-search-input");
  const inventoryLowStockCheckbox = document.getElementById("inventory-low-stock-checkbox");

  const state = {
    orders: [],
    users: [],
    services: [],
    parts: [],
    pendingDeleteAction: null,
  };

  function renderTableSkeleton(target) {
    target.innerHTML = `
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
    `;
  }

  function renderErrorState(target, title, message, retryFn) {
    target.innerHTML = `
      <div class="state-box">
        <p class="state-box__title">${window.ui.escapeHtml(title)}</p>
        <p class="state-box__desc">${window.ui.escapeHtml(message)}</p>
        <button type="button" class="btn btn--primary btn--sm retry-btn">Повторить</button>
      </div>
    `;
    target.querySelector(".retry-btn")?.addEventListener("click", retryFn);
  }

  function renderEmptyState(target, title, description) {
    target.innerHTML = `
      <div class="state-box">
        <p class="state-box__title">${window.ui.escapeHtml(title)}</p>
        <p class="state-box__desc">${window.ui.escapeHtml(description)}</p>
      </div>
    `;
  }

  // --- Tabs switching with roving focus ---
  function activateTab(tab) {
    tabButtons.forEach((btn) => {
      const selected = btn === tab;
      btn.setAttribute("aria-selected", selected ? "true" : "false");
      btn.setAttribute("tabindex", selected ? "0" : "-1");
    });

    tabPanels.forEach((panel) => {
      const matches = panel.getAttribute("aria-labelledby") === tab.id;
      panel.hidden = !matches;
      if (matches) {
        panel.setAttribute("tabindex", "0");
      } else {
        panel.removeAttribute("tabindex");
      }
    });

    tab.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }

  tabButtons.forEach((tab, index) => {
    tab.setAttribute("tabindex", tab.getAttribute("aria-selected") === "true" ? "0" : "-1");
    tab.addEventListener("click", () => activateTab(tab));
    tab.addEventListener("keydown", (event) => {
      let nextIdx = -1;
      if (event.key === "ArrowRight") nextIdx = (index + 1) % tabButtons.length;
      else if (event.key === "ArrowLeft") nextIdx = (index - 1 + tabButtons.length) % tabButtons.length;
      else if (event.key === "Home") nextIdx = 0;
      else if (event.key === "End") nextIdx = tabButtons.length - 1;
      if (nextIdx >= 0) {
        event.preventDefault();
        tabButtons[nextIdx].focus();
        activateTab(tabButtons[nextIdx]);
      }
    });
  });

  // Close buttons inside dialogs
  document.querySelectorAll("[data-close-dialog]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dialogId = btn.getAttribute("data-close-dialog");
      const dialog = dialogId ? document.getElementById(dialogId) : null;
      dialog?.close("cancel");
    });
  });

  // --- Confirm Delete Dialog ---
  const confirmModal = document.getElementById("confirm-delete-modal");
  const confirmMessageEl = document.getElementById("confirm-delete-message");
  const confirmDeleteBtn = document.getElementById("confirm-delete-btn");

  function openConfirmDelete(message, onConfirm) {
    confirmMessageEl.textContent = message;
    state.pendingDeleteAction = onConfirm;
    confirmModal.showModal();
  }

  confirmDeleteBtn?.addEventListener("click", async () => {
    if (!state.pendingDeleteAction) return;
    const action = state.pendingDeleteAction;
    confirmDeleteBtn.disabled = true;
    confirmDeleteBtn.textContent = "Удаление...";
    try {
      await action();
      confirmModal.close("confirmed");
    } catch (error) {
      window.ui.showToast(error.message, "error");
    } finally {
      confirmDeleteBtn.disabled = false;
      confirmDeleteBtn.textContent = "Удалить";
      state.pendingDeleteAction = null;
    }
  });

  // --- Tab 1: Orders ---
  function getUserNameById(userId) {
    if (!userId) return "Не назначен";
    const found = state.users.find((u) => u.id === userId);
    return found ? found.full_name : `Пользователь #${userId}`;
  }

  function renderOrdersTable() {
    const q = (ordersSearchInput?.value || "").trim().toLowerCase();
    const filtered = state.orders.filter((o) => {
      if (!q) return true;
      const hay = `#${o.id} ${o.device_type} ${o.device_brand} ${o.device_model} ${o.problem_description}`.toLowerCase();
      return hay.includes(q);
    });

    if (filtered.length === 0) {
      renderEmptyState(
        ordersContent,
        "Заявки не найдены",
        "Измените поисковый запрос или фильтр статуса."
      );
      return;
    }

    ordersContent.innerHTML = `
      <div class="table-wrapper" tabindex="0" role="region" aria-label="Таблица заявок">
        <table class="data-table">
          <thead>
            <tr>
              <th>№ и устройство</th>
              <th>Клиент</th>
              <th>Мастер</th>
              <th>Статус</th>
              <th>Итого</th>
              <th>Создана</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            ${filtered
              .map(
                (o) => `
              <tr>
                <th scope="row">№${o.id} · ${window.ui.escapeHtml(o.device_brand)} ${window.ui.escapeHtml(o.device_model)}</th>
                <td data-label="Клиент">${window.ui.escapeHtml(getUserNameById(o.client_id))}</td>
                <td data-label="Мастер">${window.ui.escapeHtml(o.master_id ? getUserNameById(o.master_id) : "Не назначен")}</td>
                <td data-label="Статус">${window.ui.renderStatusBadge(o.status, o.status_label)}</td>
                <td data-label="Итого">${window.ui.formatPrice(o.total_cost)}</td>
                <td data-label="Создана">${window.ui.formatDateTime(o.created_at)}</td>
                <td data-label="Действия">
                  <div class="table-actions">
                    <button type="button" class="btn btn--outline btn--sm" data-assign-order="${o.id}">Назначить мастера</button>
                  </div>
                </td>
              </tr>
            `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  async function loadOrders() {
    renderTableSkeleton(ordersContent);
    try {
      const status = ordersStatusFilter?.value || "";
      state.orders = await window.api.getAdminOrders({ status });
      renderOrdersTable();
    } catch (error) {
      renderErrorState(ordersContent, "Ошибка загрузки заявок", error.message, loadOrders);
    }
  }

  const assignModal = document.getElementById("assign-master-modal");
  const assignForm = document.getElementById("assign-master-form");
  const assignValidator = window.ui.initFormValidation(assignForm);

  ordersContent?.addEventListener("click", (event) => {
    const btn = event.target instanceof Element
      ? event.target.closest("[data-assign-order]")
      : null;
    if (!btn) return;
    const orderId = Number(btn.getAttribute("data-assign-order"));
    const order = state.orders.find((o) => o.id === orderId);
    if (!order) return;

    const activeMasters = state.users.filter((u) => u.role === "master" && u.is_active);
    if (activeMasters.length === 0) {
      window.ui.showToast("Нет активных мастеров для назначения", "error");
      return;
    }

    document.getElementById("assign-order-id").value = String(order.id);
    document.getElementById("assign-order-summary").textContent =
      `Заявка №${order.id}: ${order.device_type} ${order.device_brand} ${order.device_model}`;

    const select = document.getElementById("assign-master-select");
    select.innerHTML = activeMasters
      .map(
        (m) => `<option value="${m.id}"${m.id === order.master_id ? " selected" : ""}>${window.ui.escapeHtml(m.full_name)} (${window.ui.escapeHtml(m.email)})</option>`
      )
      .join("");
    assignModal.showModal();
  });

  assignForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!assignValidator.validateForm(assignForm)) return;
    const orderId = Number(document.getElementById("assign-order-id").value);
    const masterId = Number(document.getElementById("assign-master-select").value);
    const submitBtn = document.getElementById("assign-submit-btn");
    submitBtn.disabled = true;
    try {
      await window.api.assignMaster(orderId, masterId);
      assignModal.close("saved");
      window.ui.showToast(`На заявку №${orderId} назначен мастер`, "success");
      await loadOrders();
    } catch (error) {
      window.ui.showToast(error.message, "error");
    } finally {
      submitBtn.disabled = false;
    }
  });

  ordersSearchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadOrders();
  });
  ordersStatusFilter?.addEventListener("change", loadOrders);
  ordersSearchInput?.addEventListener("input", renderOrdersTable);

  // --- Tab 2: Users ---
  function renderUsersTable() {
    const q = (usersSearchInput?.value || "").trim().toLowerCase();
    const roleFilter = usersRoleFilter?.value || "";
    const filtered = state.users.filter((u) => {
      if (roleFilter && u.role !== roleFilter) return false;
      if (!q) return true;
      return `${u.full_name} ${u.email} ${u.phone}`.toLowerCase().includes(q);
    });

    if (filtered.length === 0) {
      renderEmptyState(
        usersContent,
        "Пользователи не найдены",
        "Попробуйте изменить поисковый запрос или роль."
      );
      return;
    }

    usersContent.innerHTML = `
      <div class="table-wrapper" tabindex="0" role="region" aria-label="Таблица пользователей">
        <table class="data-table">
          <thead>
            <tr>
              <th>ФИО</th>
              <th>ID</th>
              <th>E-mail</th>
              <th>Телефон</th>
              <th>Роль</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            ${filtered
              .map((u) => {
                const roleLabel = window.APP_CONFIG.ROLE_LABELS[u.role] || u.role;
                const statusBadge = u.is_active
                  ? `<span class="badge badge--ok">Активен</span>`
                  : `<span class="badge badge--muted">Отключён</span>`;
                return `
                  <tr>
                    <th scope="row">${window.ui.escapeHtml(u.full_name)}</th>
                    <td data-label="ID">${u.id}</td>
                    <td data-label="E-mail">${window.ui.escapeHtml(u.email)}</td>
                    <td data-label="Телефон">${window.ui.escapeHtml(u.phone)}</td>
                    <td data-label="Роль"><span class="badge badge--role">${window.ui.escapeHtml(roleLabel)}</span></td>
                    <td data-label="Статус">${statusBadge}</td>
                    <td data-label="Действия">
                      <div class="table-actions">
                        <button type="button" class="btn btn--outline btn--sm" data-edit-user="${u.id}">Изменить</button>
                        <button type="button" class="btn btn--ghost btn--sm" style="color: var(--color-danger);" data-delete-user="${u.id}">Удалить</button>
                      </div>
                    </td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  async function loadUsers() {
    renderTableSkeleton(usersContent);
    try {
      state.users = await window.api.getAdminUsers();
      renderUsersTable();
      if (state.orders.length > 0) {
        renderOrdersTable();
      }
    } catch (error) {
      renderErrorState(usersContent, "Ошибка загрузки пользователей", error.message, loadUsers);
    }
  }

  const userModal = document.getElementById("user-modal");
  const userModalForm = document.getElementById("user-modal-form");
  const userValidator = window.ui.initFormValidation(userModalForm);

  function openUserModal(user = null) {
    userModalForm.reset();
    const isEdit = Boolean(user);
    document.getElementById("user-modal-title").textContent = isEdit
      ? `Редактирование: ${user.full_name}`
      : "Новый пользователь";
    document.getElementById("user-edit-id").value = isEdit ? String(user.id) : "";
    document.getElementById("user-full-name").value = user?.full_name || "";
    document.getElementById("user-email").value = user?.email || "";
    document.getElementById("user-phone").value = user?.phone || "";
    document.getElementById("user-role").value = user?.role || "client";

    const passInput = document.getElementById("user-password");
    const passReq = document.getElementById("user-password-req");
    const passHint = document.getElementById("user-password-hint");
    const activeWrap = document.getElementById("user-active-wrap");
    const activeCheckbox = document.getElementById("user-is-active");

    if (isEdit) {
      passInput.required = false;
      passReq.hidden = true;
      passHint.textContent = "Оставьте пустым, чтобы не менять текущий пароль.";
      activeWrap.hidden = false;
      activeCheckbox.checked = Boolean(user.is_active);
    } else {
      passInput.required = true;
      passReq.hidden = false;
      passHint.textContent = "Минимум 6 символов.";
      activeWrap.hidden = true;
      activeCheckbox.checked = true;
    }
    userModal.showModal();
  }

  document.getElementById("add-user-btn")?.addEventListener("click", () => openUserModal(null));

  usersContent?.addEventListener("click", (event) => {
    const editBtn = event.target instanceof Element
      ? event.target.closest("[data-edit-user]")
      : null;
    if (editBtn) {
      const id = Number(editBtn.getAttribute("data-edit-user"));
      const user = state.users.find((u) => u.id === id);
      if (user) openUserModal(user);
      return;
    }

    const delBtn = event.target instanceof Element
      ? event.target.closest("[data-delete-user]")
      : null;
    if (delBtn) {
      const id = Number(delBtn.getAttribute("data-delete-user"));
      const user = state.users.find((u) => u.id === id);
      if (!user) return;
      openConfirmDelete(
        `Удалить пользователя «${user.full_name}» (${user.email})?`,
        async () => {
          await window.api.deleteUser(user.id);
          window.ui.showToast("Пользователь удалён", "success");
          await loadUsers();
        }
      );
    }
  });

  userModalForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!userValidator.validateForm(userModalForm)) return;

    const editId = document.getElementById("user-edit-id").value;
    const payload = {
      full_name: document.getElementById("user-full-name").value.trim(),
      email: document.getElementById("user-email").value.trim(),
      phone: document.getElementById("user-phone").value.trim(),
      role: document.getElementById("user-role").value,
    };
    const password = document.getElementById("user-password").value;
    if (password) payload.password = password;

    const saveBtn = document.getElementById("user-save-btn");
    saveBtn.disabled = true;
    try {
      if (editId) {
        payload.is_active = document.getElementById("user-is-active").checked;
        await window.api.updateUser(Number(editId), payload);
        window.ui.showToast("Данные пользователя обновлены", "success");
      } else {
        await window.api.createUser(payload);
        window.ui.showToast("Пользователь создан", "success");
      }
      userModal.close("saved");
      await loadUsers();
    } catch (error) {
      window.ui.showToast(error.message, "error");
    } finally {
      saveBtn.disabled = false;
    }
  });

  usersSearchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    renderUsersTable();
  });
  usersSearchInput?.addEventListener("input", renderUsersTable);
  usersRoleFilter?.addEventListener("change", renderUsersTable);

  // --- Tab 3: Services ---
  function renderServicesTable() {
    const q = (servicesSearchInput?.value || "").trim().toLowerCase();
    const filtered = state.services.filter((s) => {
      if (!q) return true;
      return `${s.title} ${s.category} ${s.description || ""}`.toLowerCase().includes(q);
    });

    if (filtered.length === 0) {
      renderEmptyState(
        servicesContent,
        "Услуги не найдены",
        "Добавьте новую услугу или измените поисковый запрос."
      );
      return;
    }

    servicesContent.innerHTML = `
      <div class="table-wrapper" tabindex="0" role="region" aria-label="Таблица услуг">
        <table class="data-table">
          <thead>
            <tr>
              <th>Название услуги</th>
              <th>ID</th>
              <th>Категория</th>
              <th>Базовая цена</th>
              <th>Гарантия</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            ${filtered
              .map(
                (s) => `
              <tr>
                <th scope="row">${window.ui.escapeHtml(s.title)}</th>
                <td data-label="ID">${s.id}</td>
                <td data-label="Категория">${window.ui.escapeHtml(s.category)}</td>
                <td data-label="Базовая цена">${window.ui.formatPrice(s.base_price)}</td>
                <td data-label="Гарантия">${s.warranty_days} дн.</td>
                <td data-label="Статус">${
                  s.is_active
                    ? `<span class="badge badge--ok">Активна</span>`
                    : `<span class="badge badge--muted">Скрыта</span>`
                }</td>
                <td data-label="Действия">
                  <div class="table-actions">
                    <button type="button" class="btn btn--outline btn--sm" data-edit-service="${s.id}">Изменить</button>
                    <button type="button" class="btn btn--ghost btn--sm" style="color: var(--color-danger);" data-delete-service="${s.id}">Удалить</button>
                  </div>
                </td>
              </tr>
            `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  async function loadServices() {
    renderTableSkeleton(servicesContent);
    try {
      state.services = await window.api.getAdminServices({ include_inactive: true });
      renderServicesTable();
    } catch (error) {
      renderErrorState(servicesContent, "Ошибка загрузки услуг", error.message, loadServices);
    }
  }

  const serviceModal = document.getElementById("service-modal");
  const serviceModalForm = document.getElementById("service-modal-form");
  const serviceValidator = window.ui.initFormValidation(serviceModalForm);

  function openServiceModal(svc = null) {
    serviceModalForm.reset();
    const isEdit = Boolean(svc);
    document.getElementById("service-modal-title").textContent = isEdit
      ? `Редактирование услуги #${svc.id}`
      : "Новая услуга";
    document.getElementById("service-edit-id").value = isEdit ? String(svc.id) : "";
    document.getElementById("service-title").value = svc?.title || "";
    document.getElementById("service-category").value = svc?.category || "";
    document.getElementById("service-price").value = svc ? Number(svc.base_price) : "";
    document.getElementById("service-warranty").value = svc ? svc.warranty_days : 30;
    document.getElementById("service-desc").value = svc?.description || "";
    document.getElementById("service-active").checked = svc ? Boolean(svc.is_active) : true;
    serviceModal.showModal();
  }

  document.getElementById("add-service-btn")?.addEventListener("click", () => openServiceModal(null));

  servicesContent?.addEventListener("click", (event) => {
    const editBtn = event.target instanceof Element
      ? event.target.closest("[data-edit-service]")
      : null;
    if (editBtn) {
      const id = Number(editBtn.getAttribute("data-edit-service"));
      const svc = state.services.find((s) => s.id === id);
      if (svc) openServiceModal(svc);
      return;
    }

    const delBtn = event.target instanceof Element
      ? event.target.closest("[data-delete-service]")
      : null;
    if (delBtn) {
      const id = Number(delBtn.getAttribute("data-delete-service"));
      const svc = state.services.find((s) => s.id === id);
      if (!svc) return;
      openConfirmDelete(`Удалить услугу «${svc.title}»?`, async () => {
        await window.api.deleteService(svc.id);
        window.ui.showToast("Услуга удалена", "success");
        await loadServices();
      });
    }
  });

  serviceModalForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!serviceValidator.validateForm(serviceModalForm)) return;

    const editId = document.getElementById("service-edit-id").value;
    const descVal = document.getElementById("service-desc").value.trim();
    const payload = {
      title: document.getElementById("service-title").value.trim(),
      category: document.getElementById("service-category").value.trim(),
      base_price: Number(document.getElementById("service-price").value),
      warranty_days: Number(document.getElementById("service-warranty").value),
      description: descVal || null,
      is_active: document.getElementById("service-active").checked,
    };

    const saveBtn = document.getElementById("service-save-btn");
    saveBtn.disabled = true;
    try {
      if (editId) {
        await window.api.updateService(Number(editId), payload);
        window.ui.showToast("Услуга обновлена", "success");
      } else {
        await window.api.createService(payload);
        window.ui.showToast("Услуга добавлена", "success");
      }
      serviceModal.close("saved");
      await loadServices();
    } catch (error) {
      window.ui.showToast(error.message, "error");
    } finally {
      saveBtn.disabled = false;
    }
  });

  servicesSearchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    renderServicesTable();
  });
  servicesSearchInput?.addEventListener("input", renderServicesTable);

  // --- Tab 4: Inventory ---
  function renderInventoryTable() {
    if (!state.parts || state.parts.length === 0) {
      renderEmptyState(
        inventoryContent,
        "Запчасти не найдены",
        "На складе нет позиций, соответствующих фильтру."
      );
      return;
    }

    inventoryContent.innerHTML = `
      <div class="table-wrapper" tabindex="0" role="region" aria-label="Таблица склада запчастей">
        <table class="data-table">
          <thead>
            <tr>
              <th>Наименование</th>
              <th>SKU</th>
              <th>Категория</th>
              <th>Закупка / Розница</th>
              <th>Остаток / Порог</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            ${state.parts
              .map((p) => {
                const stockBadge = p.is_low_stock
                  ? `<span class="badge badge--low-stock">${p.stock_qty} шт. (низкий)</span>`
                  : `<span class="badge badge--ok">${p.stock_qty} шт.</span>`;
                return `
                  <tr>
                    <th scope="row">${window.ui.escapeHtml(p.name)}</th>
                    <td data-label="SKU">${window.ui.escapeHtml(p.sku)}</td>
                    <td data-label="Категория">${window.ui.escapeHtml(p.category)}</td>
                    <td data-label="Цены">${window.ui.formatPrice(p.purchase_price)} / ${window.ui.formatPrice(p.retail_price)}</td>
                    <td data-label="Остаток">${stockBadge} <span class="field__hint">/ мин. ${p.min_stock_qty}</span></td>
                    <td data-label="Действия">
                      <div class="table-actions">
                        <button type="button" class="btn btn--outline btn--sm" data-move-part="${p.id}">Движение</button>
                        <button type="button" class="btn btn--outline btn--sm" data-edit-part="${p.id}">Изменить</button>
                        <button type="button" class="btn btn--ghost btn--sm" style="color: var(--color-danger);" data-delete-part="${p.id}">Удалить</button>
                      </div>
                    </td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  async function loadInventory() {
    renderTableSkeleton(inventoryContent);
    try {
      const search = (inventorySearchInput?.value || "").trim();
      const lowStockOnly = Boolean(inventoryLowStockCheckbox?.checked);
      state.parts = await window.api.getParts({
        search,
        low_stock_only: lowStockOnly,
      });
      renderInventoryTable();
    } catch (error) {
      renderErrorState(inventoryContent, "Ошибка загрузки склада", error.message, loadInventory);
    }
  }

  const partModal = document.getElementById("part-modal");
  const partModalForm = document.getElementById("part-modal-form");
  const partValidator = window.ui.initFormValidation(partModalForm);

  function openPartModal(part = null) {
    partModalForm.reset();
    const isEdit = Boolean(part);
    document.getElementById("part-modal-title").textContent = isEdit
      ? `Редактирование: ${part.sku}`
      : "Новая запчасть";
    document.getElementById("part-edit-id").value = isEdit ? String(part.id) : "";
    document.getElementById("part-sku").value = part?.sku || "";
    document.getElementById("part-name").value = part?.name || "";
    document.getElementById("part-category").value = part?.category || "";
    document.getElementById("part-purchase-price").value = part ? Number(part.purchase_price) : "";
    document.getElementById("part-retail-price").value = part ? Number(part.retail_price) : "";
    document.getElementById("part-stock-qty").value = part ? part.stock_qty : 0;
    document.getElementById("part-min-qty").value = part ? part.min_stock_qty : 2;
    partModal.showModal();
  }

  const movementModal = document.getElementById("movement-modal");
  const movementModalForm = document.getElementById("movement-modal-form");
  const movementValidator = window.ui.initFormValidation(movementModalForm);

  function openMovementModal(preselectedPartId = null) {
    if (state.parts.length === 0) {
      window.ui.showToast("Сначала добавьте запчасть на склад", "error");
      return;
    }
    movementModalForm.reset();
    const select = document.getElementById("movement-part-select");
    select.innerHTML = state.parts
      .map(
        (p) => `<option value="${p.id}"${p.id === preselectedPartId ? " selected" : ""}>${window.ui.escapeHtml(p.name)} (${window.ui.escapeHtml(p.sku)}) — остаток ${p.stock_qty} шт.</option>`
      )
      .join("");
    movementModal.showModal();
  }

  document.getElementById("add-part-btn")?.addEventListener("click", () => openPartModal(null));
  document.getElementById("open-movement-btn")?.addEventListener("click", () => openMovementModal(null));

  inventoryContent?.addEventListener("click", (event) => {
    const moveBtn = event.target instanceof Element
      ? event.target.closest("[data-move-part]")
      : null;
    if (moveBtn) {
      openMovementModal(Number(moveBtn.getAttribute("data-move-part")));
      return;
    }

    const editBtn = event.target instanceof Element
      ? event.target.closest("[data-edit-part]")
      : null;
    if (editBtn) {
      const id = Number(editBtn.getAttribute("data-edit-part"));
      const part = state.parts.find((p) => p.id === id);
      if (part) openPartModal(part);
      return;
    }

    const delBtn = event.target instanceof Element
      ? event.target.closest("[data-delete-part]")
      : null;
    if (delBtn) {
      const id = Number(delBtn.getAttribute("data-delete-part"));
      const part = state.parts.find((p) => p.id === id);
      if (!part) return;
      openConfirmDelete(
        `Удалить запчасть «${part.name}» (${part.sku})?`,
        async () => {
          await window.api.deletePart(part.id);
          window.ui.showToast("Запчасть удалена", "success");
          await loadInventory();
        }
      );
    }
  });

  partModalForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!partValidator.validateForm(partModalForm)) return;

    const editId = document.getElementById("part-edit-id").value;
    const payload = {
      sku: document.getElementById("part-sku").value.trim(),
      name: document.getElementById("part-name").value.trim(),
      category: document.getElementById("part-category").value.trim(),
      purchase_price: Number(document.getElementById("part-purchase-price").value),
      retail_price: Number(document.getElementById("part-retail-price").value),
      stock_qty: Number(document.getElementById("part-stock-qty").value),
      min_stock_qty: Number(document.getElementById("part-min-qty").value),
    };

    const saveBtn = document.getElementById("part-save-btn");
    saveBtn.disabled = true;
    try {
      if (editId) {
        await window.api.updatePart(Number(editId), payload);
        window.ui.showToast("Позиция склада обновлена", "success");
      } else {
        await window.api.createPart(payload);
        window.ui.showToast("Запчасть добавлена на склад", "success");
      }
      partModal.close("saved");
      await loadInventory();
    } catch (error) {
      window.ui.showToast(error.message, "error");
    } finally {
      saveBtn.disabled = false;
    }
  });

  movementModalForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!movementValidator.validateForm(movementModalForm)) return;

    const payload = {
      part_id: Number(document.getElementById("movement-part-select").value),
      movement_type: document.getElementById("movement-type-select").value,
      quantity: Number(document.getElementById("movement-qty-input").value),
      reason: document.getElementById("movement-reason-input").value.trim() || null,
    };

    const saveBtn = document.getElementById("movement-save-btn");
    saveBtn.disabled = true;
    try {
      await window.api.createMovement(payload);
      movementModal.close("saved");
      window.ui.showToast("Складская операция проведена", "success");
      await loadInventory();
    } catch (error) {
      window.ui.showToast(error.message, "error");
    } finally {
      saveBtn.disabled = false;
    }
  });

  inventorySearchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadInventory();
  });
  inventoryLowStockCheckbox?.addEventListener("change", loadInventory);

  async function loadAllSections() {
    await Promise.all([loadUsers(), loadOrders(), loadServices(), loadInventory()]);
  }

  document
    .getElementById("admin-refresh-all-btn")
    ?.addEventListener("click", loadAllSections);

  await loadAllSections();
});
