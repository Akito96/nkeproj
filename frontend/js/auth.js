(() => {
  const { USER_STORAGE_KEY, ROLE_LABELS, ROLE_HOME_PAGES } = window.APP_CONFIG;

  function getStoredUser() {
    try {
      const raw = localStorage.getItem(USER_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function saveStoredUser(user) {
    try {
      if (user) {
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
      } else {
        localStorage.removeItem(USER_STORAGE_KEY);
      }
    } catch {
      // ignore storage errors
    }
  }

  async function fetchAndStoreCurrentUser() {
    const token = window.api.getToken();
    if (!token) {
      saveStoredUser(null);
      return null;
    }
    try {
      const user = await window.api.getMe({ skipAuthRedirect: true });
      saveStoredUser(user);
      return user;
    } catch {
      window.api.clearAuthStorage();
      return null;
    }
  }

  function logout() {
    window.api.clearAuthStorage();
    window.ui.showToast("Вы вышли из учётной записи", "info");
    setTimeout(() => {
      window.location.href = "index.html";
    }, 400);
  }

  function getRoleHomeUrl(role) {
    return ROLE_HOME_PAGES[role] || "index.html";
  }

  function checkRole(allowedRoles) {
    const user = getStoredUser();
    if (!user || !window.api.getToken()) return false;
    if (!allowedRoles || allowedRoles.length === 0) return true;
    return allowedRoles.includes(user.role);
  }

  async function requireRoleGuard(allowedRoles) {
    const user = await fetchAndStoreCurrentUser();
    if (!user) {
      const current = window.location.pathname.split("/").pop() || "index.html";
      window.location.href = `login.html?next=${encodeURIComponent(current)}`;
      return null;
    }
    if (allowedRoles && allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
      window.ui.showToast("Недостаточно прав для доступа к странице", "error");
      window.location.href = getRoleHomeUrl(user.role);
      return null;
    }
    return user;
  }

  async function redirectIfAuthenticated() {
    if (!window.api.getToken()) return null;
    const user = await fetchAndStoreCurrentUser();
    if (user) {
      window.location.href = getRoleHomeUrl(user.role);
      return user;
    }
    return null;
  }

  function currentPageName() {
    const name = window.location.pathname.split("/").pop();
    return name || "index.html";
  }

  function renderHeaderMarkup(user) {
    const page = currentPageName();
    const isCurrent = (href) => (page === href ? ' aria-current="page"' : "");
    const safeName = user ? window.ui.escapeHtml(user.full_name) : "";
    const roleLabel = user ? ROLE_LABELS[user.role] || user.role : "";

    const authItems = user
      ? `
        ${
          user.role === "client"
            ? `
          <li><a class="nav-link" href="create-order.html"${isCurrent("create-order.html")}>Новая заявка</a></li>
          <li><a class="nav-link" href="client.html"${isCurrent("client.html")}>Мои заявки</a></li>
        `
            : ""
        }
        ${
          user.role === "master"
            ? `
          <li><a class="nav-link" href="master.html"${isCurrent("master.html")}>Рабочее место</a></li>
        `
            : ""
        }
        ${
          user.role === "admin"
            ? `
          <li><a class="nav-link" href="admin.html"${isCurrent("admin.html")}>Админ-панель</a></li>
          <li><a class="nav-link" href="kanban.html"${isCurrent("kanban.html")}>Kanban</a></li>
          <li><a class="nav-link" href="stats.html"${isCurrent("stats.html")}>Статистика</a></li>
          <li><a class="nav-link" href="master.html"${isCurrent("master.html")}>Пост мастера</a></li>
        `
            : ""
        }
        <li class="nav-user">
          <span class="nav-user__name">${safeName}</span>
          <span class="badge badge--role">${window.ui.escapeHtml(roleLabel)}</span>
        </li>
        <li>
          <button type="button" id="logout-btn" class="btn btn--ghost btn--sm">Выйти</button>
        </li>
      `
      : `
        <li><a class="nav-link" href="login.html"${isCurrent("login.html")}>Вход</a></li>
        <li><a class="nav-link btn btn--primary btn--sm" href="register.html"${isCurrent("register.html")}>Регистрация</a></li>
      `;

    return `
      <div class="container header-inner">
        <a class="site-logo" href="index.html">
          <span class="site-logo__mark" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <rect x="6" y="6" width="12" height="12" rx="1"></rect>
              <path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"></path>
            </svg>
          </span>
          <span>РемМастер</span>
          <span class="site-logo__tag">СЦ</span>
        </a>

        <nav class="site-nav" aria-label="Основная навигация">
          <button
            class="menu-button"
            type="button"
            popovertarget="site-menu"
            popovertargetaction="toggle"
            aria-controls="site-menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
            <span>Меню</span>
          </button>

          <ul id="site-menu" class="site-menu" popover="auto">
            <li><a class="nav-link" href="index.html"${isCurrent("index.html")}>Главная</a></li>
            <li><a class="nav-link" href="services.html"${isCurrent("services.html")}>Каталог услуг</a></li>
            ${authItems}
          </ul>
        </nav>
      </div>
    `;
  }

  let headerObserver = null;

  function attachAdaptiveNavbar(header) {
    if (headerObserver) {
      headerObserver.disconnect();
      headerObserver = null;
    }
    const inner = header.querySelector(".header-inner");
    const menu = header.querySelector("#site-menu");
    if (!inner || !menu) return;

    let lastObservedWidth = 0;

    const measure = () => {
      const currentWidth = header.getBoundingClientRect().width;
      const isCurrentlyWide = header.classList.contains("is-wide");
      if (!isCurrentlyWide && lastObservedWidth > 0 && currentWidth <= lastObservedWidth) {
        lastObservedWidth = currentWidth;
        return;
      }
      lastObservedWidth = currentWidth;

      let wasOpen = false;
      try {
        wasOpen = menu.matches(":popover-open");
      } catch {
        wasOpen = menu.classList.contains(":popover-open");
      }

      header.classList.add("is-measuring", "is-wide");
      const fitsInline = inner.scrollWidth <= inner.clientWidth;

      if (fitsInline) {
        header.classList.add("is-wide");
        menu.removeAttribute("popover");
      } else {
        header.classList.remove("is-wide");
        menu.setAttribute("popover", "auto");
        if (wasOpen) {
          try {
            menu.showPopover?.();
          } catch {
            // ignore
          }
        }
      }

      requestAnimationFrame(() => {
        header.classList.remove("is-measuring");
      });
    };

    headerObserver = new ResizeObserver(() => measure());
    headerObserver.observe(header);
    headerObserver.observe(menu);
    measure();
  }

  async function initHeader() {
    let header = document.getElementById("site-header");
    if (!header) {
      header = document.createElement("header");
      header.id = "site-header";
      header.className = "site-header";
      document.body.prepend(header);
    }

    const cachedUser = getStoredUser();
    header.innerHTML = renderHeaderMarkup(cachedUser);
    attachAdaptiveNavbar(header);

    const bindLogout = () => {
      const btn = header.querySelector("#logout-btn");
      if (btn) {
        btn.addEventListener("click", logout);
      }
    };
    bindLogout();

    if (window.api.getToken()) {
      const freshUser = await fetchAndStoreCurrentUser();
      header.innerHTML = renderHeaderMarkup(freshUser);
      attachAdaptiveNavbar(header);
      bindLogout();
      return freshUser;
    }
    return null;
  }

  window.auth = Object.freeze({
    getStoredUser,
    saveStoredUser,
    fetchAndStoreCurrentUser,
    logout,
    getRoleHomeUrl,
    checkRole,
    requireRoleGuard,
    redirectIfAuthenticated,
    initHeader,
  });
})();
