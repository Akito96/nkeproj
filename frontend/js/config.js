(() => {
  const isSameBackendOrigin =
    typeof window !== "undefined" &&
    window.location &&
    /^https?:$/i.test(window.location.protocol) &&
    window.location.port === "8000";

  const fallbackHost =
    typeof window !== "undefined" &&
    window.location &&
    window.location.hostname &&
    window.location.hostname !== ""
      ? window.location.hostname
      : "127.0.0.1";

  const backendOrigin = isSameBackendOrigin
    ? window.location.origin
    : `http://${fallbackHost}:8000`;

  window.APP_CONFIG = Object.freeze({
    API_BASE_URL: `${backendOrigin}/api`,
    BACKEND_ORIGIN: backendOrigin,
    TOKEN_STORAGE_KEY: "repair_shop_jwt",
    USER_STORAGE_KEY: "repair_shop_user",
    ROLE_LABELS: Object.freeze({
      client: "Клиент",
      master: "Мастер",
      admin: "Администратор",
    }),
    ROLE_HOME_PAGES: Object.freeze({
      client: "client.html",
      master: "master.html",
      admin: "admin.html",
    }),
    STATUS_META: Object.freeze({
      accepted: Object.freeze({ label: "Принята", className: "badge--accepted" }),
      diagnostics: Object.freeze({ label: "В диагностике", className: "badge--diagnostics" }),
      in_repair: Object.freeze({ label: "В ремонте", className: "badge--in_repair" }),
      ready: Object.freeze({ label: "Готова к выдаче", className: "badge--ready" }),
      issued: Object.freeze({ label: "Выдана", className: "badge--issued" }),
    }),
    ALLOWED_STATUS_TRANSITIONS: Object.freeze({
      accepted: Object.freeze(["diagnostics"]),
      diagnostics: Object.freeze(["in_repair"]),
      in_repair: Object.freeze(["ready"]),
      ready: Object.freeze(["issued"]),
      issued: Object.freeze([]),
    }),
    MOVEMENT_LABELS: Object.freeze({
      in: "Приход",
      out: "Расход",
      return: "Возврат",
      write_off: "Списание",
    }),
  });
})();
