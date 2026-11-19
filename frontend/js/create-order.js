document.addEventListener("DOMContentLoaded", async () => {
  await window.auth.initHeader();
  const currentUser = await window.auth.requireRoleGuard(["client", "admin"]);
  if (!currentUser) return;

  const loadingBox = document.getElementById("order-page-loading");
  const formCard = document.getElementById("order-form-card");
  const form = document.getElementById("create-order-form");
  const serviceSelect = document.getElementById("order-service");
  const servicesLoadStatus = document.getElementById("services-load-status");
  const photosInput = document.getElementById("order-photos");
  const photosCounter = document.getElementById("photos-counter");
  const photosError = document.getElementById("photos-error");
  const previewGrid = document.getElementById("photos-preview-grid");
  const formErrorBox = document.getElementById("order-form-error");
  const formErrorText = document.getElementById("order-form-error-text");
  const submitBtn = document.getElementById("submit-order-btn");

  const MAX_FILES = 5;
  const MAX_SIZE_BYTES = 5 * 1024 * 1024;
  const ALLOWED_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".webp"]);
  const ALLOWED_TYPES = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"]);

  let selectedItems = [];

  const validator = window.ui.initFormValidation(form);

  function showPhotoError(message) {
    if (!photosError) return;
    if (message) {
      photosError.textContent = message;
      photosError.style.display = "block";
      photosInput?.setAttribute("aria-invalid", "true");
    } else {
      photosError.textContent = "";
      photosError.style.display = "none";
      photosInput?.setAttribute("aria-invalid", "false");
    }
  }

  function formatFileSize(bytes) {
    if (bytes >= 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(2)} МБ`;
    }
    return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  }

  function syncInputFiles() {
    if (!photosInput) return;
    const dt = new DataTransfer();
    selectedItems.forEach((item) => dt.items.add(item.file));
    photosInput.files = dt.files;
  }

  function renderPhotoPreviews() {
    if (photosCounter) {
      photosCounter.textContent = `Выбрано: ${selectedItems.length} из ${MAX_FILES}`;
    }
    if (!previewGrid) return;
    if (selectedItems.length === 0) {
      previewGrid.innerHTML = "";
      return;
    }

    previewGrid.innerHTML = selectedItems
      .map(
        (item, index) => `
        <div class="photo-preview-card">
          <img class="photo-preview-card__img" src="${item.url}" alt="${window.ui.escapeHtml(item.file.name)}">
          <button
            type="button"
            class="photo-preview-card__remove"
            data-remove-index="${index}"
            aria-label="Удалить фото ${window.ui.escapeHtml(item.file.name)}"
          >✕</button>
          <div class="photo-preview-card__meta">
            <span class="photo-preview-card__name" title="${window.ui.escapeHtml(item.file.name)}">${window.ui.escapeHtml(item.file.name)}</span>
            <span class="photo-preview-card__size">${formatFileSize(item.file.size)}</span>
          </div>
        </div>
      `
      )
      .join("");
  }

  function clearSelectedPhotos() {
    selectedItems.forEach((item) => URL.revokeObjectURL(item.url));
    selectedItems = [];
    syncInputFiles();
    renderPhotoPreviews();
    showPhotoError("");
  }

  function validateFile(file) {
    const ext = file.name.includes(".")
      ? `.${file.name.split(".").pop().toLowerCase()}`
      : "";
    const type = (file.type || "").toLowerCase();
    if (!ALLOWED_EXTENSIONS.has(ext) || (type && !ALLOWED_TYPES.has(type))) {
      return `Файл «${file.name}» не поддерживается. Допустимы только JPG, PNG или WEBP.`;
    }
    if (file.size <= 0) {
      return `Файл «${file.name}» пустой.`;
    }
    if (file.size > MAX_SIZE_BYTES) {
      return `Файл «${file.name}» превышает лимит 5 МБ.`;
    }
    return "";
  }

  async function loadServicesDropdown() {
    const preselectedId = new URLSearchParams(window.location.search).get("service_id");
    if (servicesLoadStatus) {
      servicesLoadStatus.textContent = "Загрузка списка услуг...";
    }
    try {
      const data = await window.api.getServices({ page: 1, size: 100 });
      const items = data?.items || [];
      if (items.length === 0) {
        if (servicesLoadStatus) {
          servicesLoadStatus.textContent = "Список услуг пуст — вы можете отправить заявку без выбора услуги.";
        }
        return;
      }
      serviceSelect.innerHTML = `<option value="">Выбрать позже после диагностики</option>` + items
        .map(
          (svc) => `
          <option value="${svc.id}"${preselectedId === String(svc.id) ? " selected" : ""}>
            ${window.ui.escapeHtml(svc.category)} — ${window.ui.escapeHtml(svc.title)} (от ${window.ui.formatPrice(svc.base_price)})
          </option>
        `
        )
        .join("");
      if (servicesLoadStatus) {
        servicesLoadStatus.textContent = "";
      }
    } catch (error) {
      if (servicesLoadStatus) {
        servicesLoadStatus.textContent = `Не удалось загрузить каталог услуг: ${error.message}`;
      }
    }
  }

  photosInput?.addEventListener("change", () => {
    const files = Array.from(photosInput.files || []);
    if (files.length === 0) return;

    const errors = [];
    for (const file of files) {
      if (selectedItems.length >= MAX_FILES) {
        errors.push(`Можно прикрепить не более ${MAX_FILES} фотографий.`);
        break;
      }
      const err = validateFile(file);
      if (err) {
        errors.push(err);
        continue;
      }
      const duplicate = selectedItems.some(
        (item) => item.file.name === file.name && item.file.size === file.size
      );
      if (!duplicate) {
        selectedItems.push({
          file,
          url: URL.createObjectURL(file),
        });
      }
    }

    syncInputFiles();
    renderPhotoPreviews();

    if (errors.length > 0) {
      showPhotoError(errors[0]);
      window.ui.showToast(errors[0], "error");
    } else {
      showPhotoError("");
    }
  });

  previewGrid?.addEventListener("click", (event) => {
    const btn = event.target instanceof Element
      ? event.target.closest("[data-remove-index]")
      : null;
    if (!btn) return;
    const idx = Number(btn.getAttribute("data-remove-index"));
    if (Number.isInteger(idx) && idx >= 0 && idx < selectedItems.length) {
      URL.revokeObjectURL(selectedItems[idx].url);
      selectedItems.splice(idx, 1);
      syncInputFiles();
      renderPhotoPreviews();
      showPhotoError("");
    }
  });

  form?.addEventListener("reset", () => {
    clearSelectedPhotos();
    if (formErrorBox) formErrorBox.style.display = "none";
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (formErrorBox) formErrorBox.style.display = "none";

    if (!validator.validateForm(form)) {
      window.ui.showToast("Проверьте правильность заполнения полей", "error");
      return;
    }

    if (selectedItems.length > MAX_FILES) {
      showPhotoError(`Можно прикрепить не более ${MAX_FILES} фотографий.`);
      return;
    }

    const fd = new FormData();
    const serviceVal = serviceSelect?.value?.trim();
    if (serviceVal) fd.set("service_id", serviceVal);
    fd.set("device_type", document.getElementById("device-type").value.trim());
    fd.set("device_brand", document.getElementById("device-brand").value.trim());
    fd.set("device_model", document.getElementById("device-model").value.trim());

    const serialVal = document.getElementById("serial-number").value.trim();
    if (serialVal) fd.set("serial_number", serialVal);

    const appearanceVal = document.getElementById("appearance").value.trim();
    if (appearanceVal) fd.set("appearance", appearanceVal);

    fd.set("problem_description", document.getElementById("problem-description").value.trim());
    selectedItems.forEach((item) => fd.append("photos", item.file));

    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = "Отправка заявки...";

    try {
      const created = await window.api.createOrder(fd);
      clearSelectedPhotos();
      window.ui.showToast(`Заявка №${created.id} успешно создана`, "success");
      const targetUrl =
        currentUser.role === "admin"
          ? "admin.html"
          : `client.html?order_id=${created.id}`;
      setTimeout(() => {
        window.location.href = targetUrl;
      }, 450);
    } catch (error) {
      if (formErrorBox && formErrorText) {
        formErrorText.textContent = error.message;
        formErrorBox.style.display = "grid";
      }
      window.ui.showToast(error.message, "error");
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
    }
  });

  await loadServicesDropdown();
  if (loadingBox) loadingBox.hidden = true;
  if (formCard) formCard.hidden = false;
});
