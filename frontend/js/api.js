(() => {
  const { API_BASE_URL, TOKEN_STORAGE_KEY, USER_STORAGE_KEY } = window.APP_CONFIG;

  class ApiError extends Error {
    constructor(message, status, data = null) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.data = data;
    }
  }

  function getToken() {
    try {
      return localStorage.getItem(TOKEN_STORAGE_KEY);
    } catch {
      return null;
    }
  }

  function setToken(token) {
    try {
      if (token) {
        localStorage.setItem(TOKEN_STORAGE_KEY, token);
      } else {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      }
    } catch {
      // ignore storage errors in restricted contexts
    }
  }

  function clearAuthStorage() {
    try {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(USER_STORAGE_KEY);
    } catch {
      // ignore storage errors
    }
  }

  function extractErrorMessage(data, status) {
    if (data && typeof data === "object") {
      if (typeof data.detail === "string" && data.detail.trim()) {
        return data.detail;
      }
      if (Array.isArray(data.detail) && data.detail.length > 0) {
        const messages = data.detail
          .map((item) => {
            if (!item || typeof item !== "object") return "";
            return String(item.msg || "").replace(/^Value error,\s*/i, "").trim();
          })
          .filter(Boolean);
        if (messages.length > 0) {
          return messages.join("; ");
        }
      }
      if (typeof data.message === "string" && data.message.trim()) {
        return data.message;
      }
    }
    if (status === 401) return "Требуется авторизация";
    if (status === 403) return "Недостаточно прав для выполнения операции";
    if (status === 404) return "Запрошенный ресурс не найден";
    if (status >= 500) return "Внутренняя ошибка сервера. Попробуйте позже.";
    return "Ошибка при выполнении запроса";
  }

  function buildUrl(endpoint, params) {
    const normalized = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const url = new URL(`${API_BASE_URL}${normalized}`);
    if (params && typeof params === "object") {
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.set(key, String(value));
        }
      }
    }
    return url.toString();
  }

  async function request(endpoint, options = {}) {
    const {
      method = "GET",
      params = null,
      body = undefined,
      headers: customHeaders = {},
      skipAuthRedirect = false,
    } = options;

    const headers = new Headers(customHeaders);
    const token = getToken();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    let requestBody = body;
    if (body !== undefined && !(body instanceof FormData) && typeof body === "object") {
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      requestBody = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(buildUrl(endpoint, params), {
        method,
        headers,
        body: requestBody,
      });
    } catch {
      throw new ApiError(
        "Не удалось подключиться к серверу. Проверьте, запущен ли API.",
        0,
        null
      );
    }

    const contentType = response.headers.get("content-type") || "";
    let data = null;
    if (response.status !== 204 && contentType.includes("application/json")) {
      try {
        data = await response.json();
      } catch {
        data = null;
      }
    }

    if (response.status === 401) {
      clearAuthStorage();
      const page = window.location.pathname.split("/").pop() || "index.html";
      const isAuthPage = page === "login.html" || page === "register.html";
      if (!skipAuthRedirect && !isAuthPage) {
        window.location.href = "login.html?expired=1";
      }
    }

    if (!response.ok) {
      throw new ApiError(extractErrorMessage(data, response.status), response.status, data);
    }

    return data;
  }

  window.api = Object.freeze({
    ApiError,
    getToken,
    setToken,
    clearAuthStorage,
    request,
    get(endpoint, params, options = {}) {
      return request(endpoint, { ...options, method: "GET", params });
    },
    post(endpoint, body, options = {}) {
      return request(endpoint, { ...options, method: "POST", body });
    },
    patch(endpoint, body, options = {}) {
      return request(endpoint, { ...options, method: "PATCH", body });
    },
    delete(endpoint, options = {}) {
      return request(endpoint, { ...options, method: "DELETE" });
    },
    getServices({ search = "", category = "", page = 1, size = 9 } = {}) {
      return request("/services", {
        method: "GET",
        params: { search, category, page, size },
        skipAuthRedirect: true,
      });
    },
    login({ email, password }) {
      return request("/auth/login", {
        method: "POST",
        body: { email, password },
        skipAuthRedirect: true,
      });
    },
    register({ full_name, email, phone, password }) {
      return request("/auth/register", {
        method: "POST",
        body: { full_name, email, phone, password },
        skipAuthRedirect: true,
      });
    },
    getMe(options = {}) {
      return request("/auth/me", { method: "GET", ...options });
    },
    createOrder(formData) {
      return request("/orders", { method: "POST", body: formData });
    },
    getMyOrders({ status = "" } = {}) {
      return request("/orders/my", {
        method: "GET",
        params: status ? { status } : null,
      });
    },
    getOrderById(orderId) {
      return request(`/orders/${orderId}`, { method: "GET" });
    },
    getMasterOrders({ status = "" } = {}) {
      return request("/master/orders", {
        method: "GET",
        params: status ? { status } : null,
      });
    },
    updateOrderStatus(orderId, { status, note = null }) {
      return request(`/master/orders/${orderId}/status`, {
        method: "PATCH",
        body: { status, note },
      });
    },
    addOrderComment(orderId, { comment_text, is_internal = false }) {
      return request(`/master/orders/${orderId}/comments`, {
        method: "POST",
        body: { comment_text, is_internal },
      });
    },
    addOrderPartsAndLabor(orderId, payload) {
      return request(`/master/orders/${orderId}/parts`, {
        method: "POST",
        body: payload,
      });
    },
    getParts({ category = "", search = "", low_stock_only = false } = {}) {
      const params = {};
      if (category) params.category = category;
      if (search) params.search = search;
      if (low_stock_only) params.low_stock_only = true;
      return request("/inventory/parts", { method: "GET", params });
    },
    createPart(payload) {
      return request("/inventory/parts", { method: "POST", body: payload });
    },
    updatePart(partId, payload) {
      return request(`/inventory/parts/${partId}`, { method: "PATCH", body: payload });
    },
    deletePart(partId) {
      return request(`/inventory/parts/${partId}`, { method: "DELETE" });
    },
    getMovements({ part_id = "" } = {}) {
      return request("/inventory/movements", {
        method: "GET",
        params: part_id ? { part_id } : null,
      });
    },
    createMovement(payload) {
      return request("/inventory/movements", { method: "POST", body: payload });
    },
    getAdminStats({ date_from = "", date_to = "" } = {}) {
      const params = {};
      if (date_from) params.date_from = date_from;
      if (date_to) params.date_to = date_to;
      return request("/admin/stats", { method: "GET", params });
    },
    getAdminOrders({ status = "", master_id = "", client_id = "" } = {}) {
      const params = {};
      if (status) params.status = status;
      if (master_id) params.master_id = master_id;
      if (client_id) params.client_id = client_id;
      return request("/admin/orders", { method: "GET", params });
    },
    assignMaster(orderId, master_id) {
      return request(`/admin/orders/${orderId}/assign`, {
        method: "PATCH",
        body: { master_id },
      });
    },
    getAdminServices({ include_inactive = true } = {}) {
      return request("/admin/services", {
        method: "GET",
        params: { include_inactive },
      });
    },
    createService(payload) {
      return request("/admin/services", { method: "POST", body: payload });
    },
    updateService(serviceId, payload) {
      return request(`/admin/services/${serviceId}`, {
        method: "PATCH",
        body: payload,
      });
    },
    deleteService(serviceId) {
      return request(`/admin/services/${serviceId}`, { method: "DELETE" });
    },
    getAdminUsers({ role = "" } = {}) {
      return request("/admin/users", {
        method: "GET",
        params: role ? { role } : null,
      });
    },
    createUser(payload) {
      return request("/admin/users", { method: "POST", body: payload });
    },
    updateUser(userId, payload) {
      return request(`/admin/users/${userId}`, { method: "PATCH", body: payload });
    },
    deleteUser(userId) {
      return request(`/admin/users/${userId}`, { method: "DELETE" });
    },
    getAdminEmployees({ role = "" } = {}) {
      return request("/admin/employees", {
        method: "GET",
        params: role ? { role } : null,
      });
    },
  });
})();
