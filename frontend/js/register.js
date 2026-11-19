document.addEventListener("DOMContentLoaded", async () => {
  await window.auth.initHeader();
  await window.auth.redirectIfAuthenticated();

  const form = document.getElementById("register-form");
  const fullNameInput = document.getElementById("reg-full-name");
  const emailInput = document.getElementById("reg-email");
  const phoneInput = document.getElementById("reg-phone");
  const passwordInput = document.getElementById("reg-password");
  const submitBtn = document.getElementById("register-submit");
  const serverAlert = document.getElementById("register-server-error");

  window.ui.initPasswordToggles(form);
  const validator = window.ui.initFormValidation(form);

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (serverAlert) serverAlert.hidden = true;

    if (!validator.validateForm(form)) {
      window.ui.showToast("Исправьте ошибки в форме регистрации", "error");
      return;
    }

    const payload = {
      full_name: (fullNameInput?.value || "").trim(),
      email: (emailInput?.value || "").trim(),
      phone: (phoneInput?.value || "").trim(),
      password: passwordInput?.value || "",
    };

    submitBtn.disabled = true;
    submitBtn.textContent = "Регистрация...";

    try {
      await window.api.register(payload);
      const tokenResp = await window.api.login({
        email: payload.email,
        password: payload.password,
      });
      window.api.setToken(tokenResp.access_token);
      const user = await window.auth.fetchAndStoreCurrentUser();

      window.ui.showToast("Аккаунт создан! Добро пожаловать в РемМастер.", "success");
      setTimeout(() => {
        window.location.href = window.auth.getRoleHomeUrl(user?.role || "client");
      }, 600);
    } catch (error) {
      if (serverAlert) {
        serverAlert.textContent = error.message;
        serverAlert.hidden = false;
      }
      window.ui.showToast(error.message, "error");
      submitBtn.disabled = false;
      submitBtn.textContent = "Создать аккаунт";
    }
  });
});
