(() => {
  if (!Object.hasOwn(HTMLElement.prototype, "popover")) {
    import("https://unpkg.com/@oddbird/popover-polyfill@latest/dist/popover.min.js").catch(
      () => {}
    );
  }

  const { STATUS_META } = window.APP_CONFIG;
  let toastSeq = 0;
  let lastTriggerEl = null;

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function ensureToastRegion() {
    let region = document.getElementById("toast-container");
    if (!region) {
      region = document.createElement("div");
      region.id = "toast-container";
      region.className = "toast-region";
      region.setAttribute("role", "region");
      region.setAttribute("aria-label", "Уведомления");
      document.body.append(region);
    }

    let announcer = document.getElementById("toast-announcer");
    if (!announcer) {
      const label = document.createElement("p");
      label.className = "visually-hidden";
      label.textContent = "Системные уведомления";
      announcer = document.createElement("div");
      announcer.id = "toast-announcer";
      announcer.className = "visually-hidden";
      announcer.setAttribute("aria-live", "assertive");
      document.body.append(label, announcer);
    }

    return { region, announcer };
  }

  function updateToastOffsets(region) {
    const toasts = [...region.querySelectorAll(".toast")];
    let offset = 16;
    for (let i = toasts.length - 1; i >= 0; i -= 1) {
      const item = toasts[i];
      item.style.setProperty("--toast-bottom", `${offset}px`);
      const height = item.offsetHeight || 52;
      offset += height + 10;
    }
  }

  function announceToastText(toast, text, announcer) {
    if (typeof toast.ariaNotify === "function") {
      toast.ariaNotify(text);
      return;
    }
    announcer.textContent = "";
    requestAnimationFrame(() => {
      announcer.textContent = text;
    });
  }

  function showToast(message, type = "info", { duration = 5000 } = {}) {
    const { region, announcer } = ensureToastRegion();
    const activeBefore = document.activeElement;
    if (
      activeBefore instanceof HTMLElement &&
      !region.contains(activeBefore) &&
      activeBefore !== document.body
    ) {
      lastTriggerEl = activeBefore;
    }

    toastSeq += 1;
    const toastId = `toast-item-${toastSeq}`;
    const toast = document.createElement("div");
    toast.id = toastId;
    toast.className = `toast toast--${type}`;
    toast.setAttribute("popover", "manual");

    const textEl = document.createElement("span");
    textEl.className = "toast__text";
    textEl.textContent = message;

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "toast__close";
    closeBtn.setAttribute("popovertarget", toastId);
    closeBtn.setAttribute("popovertargetaction", "hide");
    closeBtn.setAttribute("aria-label", "Закрыть уведомление");
    closeBtn.textContent = "✕";

    toast.append(textEl, closeBtn);
    region.append(toast);

    let timerId = null;
    let remaining = duration;
    let startedAt = Date.now();
    let isRemoved = false;

    const dismiss = (manual = false) => {
      if (isRemoved) return;
      isRemoved = true;
      clearTimeout(timerId);

      const wasFocused = toast.contains(document.activeElement);
      try {
        toast.hidePopover?.();
      } catch {
        // ignore if polyfill not loaded
      }

      const allToasts = [...region.querySelectorAll(".toast")];
      const currentIdx = allToasts.indexOf(toast);
      const nextToast =
        allToasts[currentIdx + 1] || allToasts[currentIdx - 1] || null;

      toast.remove();
      updateToastOffsets(region);

      if (manual && wasFocused) {
        const nextBtn = nextToast?.querySelector(".toast__close");
        if (nextBtn instanceof HTMLElement) {
          nextBtn.focus();
        } else if (lastTriggerEl && document.contains(lastTriggerEl)) {
          lastTriggerEl.focus();
        }
      }
    };

    const startTimer = () => {
      if (duration <= 0) return;
      startedAt = Date.now();
      clearTimeout(timerId);
      timerId = setTimeout(() => {
        if (toast.contains(document.activeElement)) return;
        dismiss(false);
      }, remaining);
    };

    toast.addEventListener("focusin", () => {
      clearTimeout(timerId);
      remaining = Math.max(1200, remaining - (Date.now() - startedAt));
    });

    toast.addEventListener("focusout", () => {
      requestAnimationFrame(() => {
        if (!toast.contains(document.activeElement)) {
          startTimer();
        }
      });
    });

    closeBtn.addEventListener("click", () => dismiss(true));
    toast.addEventListener("toggle", (event) => {
      if (event.newState === "closed") {
        dismiss(true);
      }
    });

    try {
      toast.showPopover?.();
    } catch {
      toast.classList.add("toast--fallback-open");
    }

    updateToastOffsets(region);
    announceToastText(toast, message, announcer);
    startTimer();
    return toast;
  }

  function renderStatusBadge(status, customLabel = null) {
    const meta = STATUS_META[status] || {
      label: customLabel || status,
      className: "badge--accepted",
    };
    const label = escapeHtml(customLabel || meta.label);
    return `<span class="badge ${meta.className}">${label}</span>`;
  }

  function formatPrice(value) {
    const num = Number(value);
    if (Number.isNaN(num)) return "0 ₽";
    return `${num.toLocaleString("ru-RU")} ₽`;
  }

  function formatDateTime(isoString) {
    if (!isoString) return "—";
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return String(isoString);
    return date.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function resolveAssetUrl(path) {
    if (!path) return "";
    if (/^https?:\/\//i.test(path)) return path;
    const base = window.APP_CONFIG.BACKEND_ORIGIN || "";
    return `${base}${path.startsWith("/") ? path : `/${path}`}`;
  }

  function initDialogs(root = document) {
    const hasClosedBy = "closedBy" in HTMLDialogElement.prototype;
    root.querySelectorAll("dialog").forEach((dialog) => {
      if (dialog.dataset.dialogBound === "true") return;
      dialog.dataset.dialogBound = "true";

      dialog.addEventListener("close", () => {
        dialog.returnValue = "";
      });

      if (!hasClosedBy && dialog.getAttribute("closedby") === "any") {
        let pressedOutside = false;
        const outside = (e) => {
          const r = dialog.getBoundingClientRect();
          return (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          );
        };
        dialog.addEventListener("pointerdown", (e) => {
          pressedOutside = outside(e);
        });
        dialog.addEventListener("pointerup", (e) => {
          if (pressedOutside && outside(e)) {
            dialog.close("dismiss");
          }
          pressedOutside = false;
        });
      }
    });
  }

  function initPasswordToggles(root = document) {
    root.querySelectorAll(".password-toggle").forEach((button) => {
      if (button.dataset.bound === "true") return;
      button.dataset.bound = "true";
      button.addEventListener("click", () => {
        const targetId = button.getAttribute("aria-controls");
        const input = targetId ? document.getElementById(targetId) : null;
        if (!(input instanceof HTMLInputElement)) return;
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        button.setAttribute("aria-pressed", show ? "true" : "false");
        button.setAttribute("aria-label", show ? "Скрыть пароль" : "Показать пароль");
        button.textContent = show ? "Скрыть" : "Показать";
      });
    });
  }

  function linkError(el, shown) {
    const errorId = el.dataset.error;
    if (!errorId) return;
    const ids = (el.getAttribute("aria-describedby") || "")
      .split(/\s+/)
      .filter((id) => id && id !== errorId);
    if (shown) ids.push(errorId);
    if (ids.length) el.setAttribute("aria-describedby", ids.join(" "));
    else el.removeAttribute("aria-describedby");
  }

  function spokenText(node) {
    const copy = node.cloneNode(true);
    copy.querySelectorAll('[aria-hidden="true"]').forEach((n) => n.remove());
    copy
      .querySelectorAll('[role="img"][aria-label]')
      .forEach((n) => n.replaceWith(`${n.getAttribute("aria-label")}: `));
    return copy.textContent.replace(/\s+/g, " ").trim();
  }

  function initFormValidation(root = document) {
    let fieldAnnouncer = document.getElementById("form-field-announcer");
    if (!fieldAnnouncer) {
      fieldAnnouncer = document.createElement("div");
      fieldAnnouncer.id = "form-field-announcer";
      fieldAnnouncer.setAttribute("aria-live", "polite");
      fieldAnnouncer.className = "visually-hidden";
      document.body.append(fieldAnnouncer);
    }

    let announceTimer;
    let announcedField;

    const announceError = (el) => {
      const errorId = el.dataset.error;
      const error = errorId ? document.getElementById(errorId) : null;
      if (!error) return;
      const label = el.labels?.[0] ? `${spokenText(el.labels[0])}: ` : "";
      clearTimeout(announceTimer);
      fieldAnnouncer.textContent = "";
      announcedField = el;
      announceTimer = setTimeout(() => {
        fieldAnnouncer.textContent = label + spokenText(error);
      }, 500);
    };

    const supportsUserInvalid = CSS.supports("selector(:user-invalid)");
    const dirtyState = new WeakMap();
    const flagged = new WeakSet();
    const announced = new WeakSet();

    const syncAria = (el, announce = false, forceFallbackCheck = false) => {
      if (!el.matches?.("input, select, textarea")) return;
      let invalid = false;
      if (supportsUserInvalid) {
        invalid = el.matches(":user-invalid");
      } else if (forceFallbackCheck) {
        invalid = !el.validity.valid;
        el.classList.toggle("user-invalid-fallback", invalid);
        el.classList.toggle("user-valid-fallback", !invalid);
      } else {
        invalid = el.classList.contains("user-invalid-fallback");
      }

      if (invalid) {
        if (announce && !announced.has(el)) {
          announceError(el);
          announced.add(el);
        }
        el.setAttribute("aria-invalid", "true");
        linkError(el, true);
        flagged.add(el);
      } else if (flagged.has(el) || el.getAttribute("aria-invalid") !== "true") {
        el.setAttribute("aria-invalid", "false");
        linkError(el, false);
        flagged.delete(el);
        announced.delete(el);
        if (announcedField === el) {
          clearTimeout(announceTimer);
          fieldAnnouncer.textContent = "";
        }
      }
    };

    root.querySelectorAll("input, select, textarea").forEach((el) => {
      if (!el.hasAttribute("aria-invalid")) {
        el.setAttribute("aria-invalid", "false");
      }
      syncAria(el);
    });

    root.addEventListener(
      "blur",
      (event) => {
        const el = event.target;
        if (!(el instanceof HTMLElement) || !el.matches?.("input, select, textarea")) return;
        if (!supportsUserInvalid) {
          const state = dirtyState.get(el) || { hasInteracted: false, hasBlurred: false };
          state.hasBlurred = true;
          dirtyState.set(el, state);
          if (state.hasInteracted) {
            syncAria(el, true, true);
          }
          return;
        }
        syncAria(el, true);
      },
      true
    );

    root.addEventListener("input", (event) => {
      const el = event.target;
      if (!(el instanceof HTMLElement) || !el.matches?.("input, select, textarea")) return;
      if (!supportsUserInvalid) {
        const state = dirtyState.get(el) || { hasInteracted: false, hasBlurred: false };
        state.hasInteracted = true;
        dirtyState.set(el, state);
        if (state.hasBlurred) {
          syncAria(el, false, true);
        }
        return;
      }
      if (el.hasAttribute("aria-invalid")) {
        syncAria(el);
      }
    });

    root.addEventListener(
      "change",
      (event) => {
        const el = event.target;
        if (!(el instanceof HTMLElement) || !el.matches?.("input, select, textarea")) return;
        if (!supportsUserInvalid) {
          const state = dirtyState.get(el) || { hasInteracted: false, hasBlurred: false };
          state.hasInteracted = true;
          dirtyState.set(el, state);
          if (state.hasBlurred) {
            syncAria(el, true, true);
          }
          return;
        }
        syncAria(el, true);
      },
      true
    );

    root.addEventListener(
      "invalid",
      (event) => {
        const el = event.target;
        if (!(el instanceof HTMLElement) || !el.matches?.("input, select, textarea")) return;
        if (!supportsUserInvalid) {
          dirtyState.set(el, { hasInteracted: true, hasBlurred: true });
          syncAria(el, false, true);
          return;
        }
        announced.add(el);
        syncAria(el);
      },
      true
    );

    root.addEventListener(
      "reset",
      (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        setTimeout(() => {
          for (const control of form.elements) {
            dirtyState.delete(control);
            control.classList.remove("user-invalid-fallback", "user-valid-fallback");
            if (control instanceof HTMLElement) {
              syncAria(control);
            }
          }
        });
      },
      true
    );

    return {
      validateForm(form) {
        const controls = [...form.elements].filter((el) =>
          el.matches?.("input, select, textarea")
        );
        let firstInvalid = null;
        for (const control of controls) {
          const isValid = control.checkValidity();
          if (!isValid) {
            if (!supportsUserInvalid) {
              dirtyState.set(control, { hasInteracted: true, hasBlurred: true });
              syncAria(control, false, true);
            } else {
              control.setAttribute("aria-invalid", "true");
              linkError(control, true);
            }
            if (!firstInvalid) firstInvalid = control;
          } else {
            syncAria(control, false, !supportsUserInvalid);
          }
        }
        if (firstInvalid) {
          firstInvalid.focus();
          return false;
        }
        return true;
      },
    };
  }

  window.ui = Object.freeze({
    escapeHtml,
    showToast,
    renderStatusBadge,
    formatPrice,
    formatDateTime,
    resolveAssetUrl,
    initDialogs,
    initPasswordToggles,
    initFormValidation,
  });
})();
