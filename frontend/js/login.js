document.addEventListener("DOMContentLoaded", async () => {
  await window.auth.initHeader();
  await window.auth.redirectIfAuthenticated();

  const params = new URLSearchParams(window.location.search);
  if (params.get("expired") === "1") {
    window.ui.showToast("Сессия истекла. Войдите в систему снова.", "info");
  }

  const form = document.getElementById("login-form");
  const emailInput = document.getElementById("login-email");
  const passwordInput = document.getElementById("login-password");
  const submitBtn = document.getElementById("login-submit");
  const serverAlert = document.getElementById("login-server-error");

  window.ui.initPasswordToggles(form);
  const validator = window.ui.initFormValidation(form);

  document.querySelectorAll(".demo-fill-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (emailInput) emailInput.value = btn.dataset.email || "";
      if (passwordInput) passwordInput.value = "Password123!";
      if (serverAlert) serverAlert.hidden = true;
      window.ui.showToast("Тестовые данные подставлены", "info", { duration: 2500 });
    });
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (serverAlert) serverAlert.hidden = true;

    if (!validator.validateForm(form)) {
      window.ui.showToast("Проверьте правильность заполнения полей", "error");
      return;
    }

    const email = (emailInput?.value || "").trim();
    const password = passwordInput?.value || "";

    submitBtn.disabled = true;
    submitBtn.textContent = "Вход...";

    try {
      const tokenResp = await window.api.login({ email, password });
      window.api.setToken(tokenResp.access_token);
      const user = await window.auth.fetchAndStoreCurrentUser();

      window.ui.showToast(
        user ? `Добро пожаловать, ${user.full_name}!` : "Вход выполнен успешно!",
        "success"
      );

      const nextUrl = params.get("next");
      const target =
        nextUrl && /^[a-z0-9_-]+\.html$/i.test(nextUrl)
          ? nextUrl
          : window.auth.getRoleHomeUrl(user?.role);

      setTimeout(() => {
        window.location.href = target;
      }, 450);
    } catch (error) {
      if (serverAlert) {
        serverAlert.textContent = error.message;
        serverAlert.hidden = false;
      }
      window.ui.showToast(error.message, "error");
      submitBtn.disabled = false;
      submitBtn.textContent = "Войти";
    }
  });
});
