document.addEventListener("DOMContentLoaded", async () => {
  await window.auth.initHeader();
  const currentUser = await window.auth.requireRoleGuard(["admin"]);
  if (!currentUser) return;

  const periodChips = document.getElementById("period-chips");
  const periodForm = document.getElementById("stats-period-form");
  const dateFromInput = document.getElementById("stats-date-from");
  const dateToInput = document.getElementById("stats-date-to");
  const stateBox = document.getElementById("stats-state-box");
  const contentBox = document.getElementById("stats-content");
  const kpiGrid = document.getElementById("stats-kpi-grid");

  const charts = {
    daily: null,
    statuses: null,
    devices: null,
    masters: null,
  };

  function toIsoDate(dateObj) {
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, "0");
    const day = String(dateObj.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function applyPresetDays(preset) {
    periodChips?.querySelectorAll(".chip").forEach((chip) => {
      chip.setAttribute("aria-pressed", chip.dataset.days === preset ? "true" : "false");
    });

    if (preset === "all") {
      dateFromInput.value = "";
      dateToInput.value = "";
      return;
    }

    const days = Number(preset);
    const today = new Date();
    const start = new Date();
    start.setDate(today.getDate() - (days - 1));
    dateFromInput.value = toIsoDate(start);
    dateToInput.value = toIsoDate(today);
  }

  function destroyCharts() {
    Object.keys(charts).forEach((key) => {
      if (charts[key]) {
        charts[key].destroy();
        charts[key] = null;
      }
    });
  }

  function showLoading() {
    stateBox.hidden = true;
    contentBox.hidden = false;
    kpiGrid.innerHTML = `
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
      <div class="skeleton-row" aria-hidden="true"></div>
    `;
  }

  function showState(title, desc, showRetry = false) {
    destroyCharts();
    contentBox.hidden = true;
    stateBox.hidden = false;
    stateBox.innerHTML = `
      <div class="card state-box">
        <p class="state-box__title">${window.ui.escapeHtml(title)}</p>
        <p class="state-box__desc">${window.ui.escapeHtml(desc)}</p>
        ${
          showRetry
            ? `<button type="button" id="retry-stats-btn" class="btn btn--primary btn--sm">Повторить</button>`
            : `<button type="button" id="reset-stats-period-btn" class="btn btn--outline btn--sm">Показать за всё время</button>`
        }
      </div>
    `;
    document.getElementById("retry-stats-btn")?.addEventListener("click", loadStats);
    document.getElementById("reset-stats-period-btn")?.addEventListener("click", () => {
      applyPresetDays("all");
      loadStats();
    });
  }

  function renderKpis(summary) {
    kpiGrid.innerHTML = `
      <div class="kpi-card kpi-card--accent">
        <span class="kpi-card__label">Выручка за период</span>
        <span class="kpi-card__value">${window.ui.formatPrice(summary.total_revenue)}</span>
        <span class="kpi-card__sub">Средний чек: ${window.ui.formatPrice(summary.avg_order_value)}</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-card__label">Всего заявок</span>
        <span class="kpi-card__value">${summary.total_orders}</span>
        <span class="kpi-card__sub">За выбранный интервал</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-card__label">В работе</span>
        <span class="kpi-card__value">${summary.active_orders}</span>
        <span class="kpi-card__sub">От приёмки до готовности</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-card__label">Завершено (выдано)</span>
        <span class="kpi-card__value">${summary.completed_orders}</span>
        <span class="kpi-card__sub">Успешно выдано клиентам</span>
      </div>
    `;
  }

  function renderCharts(data) {
    if (typeof window.Chart === "undefined") {
      showState(
        "Библиотека Chart.js не загрузилась",
        "Проверьте подключение к сети для загрузки Chart.js с CDN.",
        true
      );
      return;
    }

    destroyCharts();

    const fontFamily = "'Manrope', 'Segoe UI', sans-serif";
    window.Chart.defaults.font.family = fontFamily;
    window.Chart.defaults.color = "#4b5954";

    // 1. Line chart: daily orders & revenue
    const dailyLabels = data.daily.map((d) => {
      const [y, m, day] = d.date.split("-");
      return `${day}.${m}.${y.slice(-2)}`;
    });
    const dailyCounts = data.daily.map((d) => d.orders_count);
    const dailyRevenue = data.daily.map((d) => Number(d.revenue));

    charts.daily = new window.Chart(document.getElementById("chart-daily"), {
      type: "line",
      data: {
        labels: dailyLabels,
        datasets: [
          {
            label: "Выручка (₽)",
            data: dailyRevenue,
            borderColor: "#059669",
            backgroundColor: "rgba(16, 185, 129, 0.14)",
            fill: true,
            tension: 0.3,
            yAxisID: "yRevenue",
          },
          {
            label: "Заявок (шт.)",
            data: dailyCounts,
            borderColor: "#0f766e",
            backgroundColor: "#0f766e",
            borderDash: [5, 4],
            tension: 0.25,
            yAxisID: "yOrders",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          yRevenue: {
            type: "linear",
            position: "left",
            beginAtZero: true,
            title: { display: true, text: "₽" },
          },
          yOrders: {
            type: "linear",
            position: "right",
            beginAtZero: true,
            ticks: { precision: 0 },
            grid: { drawOnChartArea: false },
            title: { display: true, text: "Шт." },
          },
        },
      },
    });

    // 2. Doughnut chart: orders by status
    const statusColors = ["#0ea5e9", "#8b5cf6", "#f59e0b", "#10b981", "#64748b"];
    charts.statuses = new window.Chart(document.getElementById("chart-statuses"), {
      type: "doughnut",
      data: {
        labels: data.by_status.map((item) => item.label),
        datasets: [
          {
            data: data.by_status.map((item) => item.count),
            backgroundColor: statusColors,
            borderWidth: 2,
            borderColor: "#ffffff",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom" },
        },
      },
    });

    // 3. Bar chart: revenue by device type
    charts.devices = new window.Chart(document.getElementById("chart-devices"), {
      type: "bar",
      data: {
        labels: data.by_device_type.map((item) => item.device_type),
        datasets: [
          {
            label: "Выручка (₽)",
            data: data.by_device_type.map((item) => Number(item.revenue)),
            backgroundColor: "#10b981",
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: { beginAtZero: true },
        },
      },
    });

    // 4. Horizontal bar chart: master workload
    charts.masters = new window.Chart(document.getElementById("chart-masters"), {
      type: "bar",
      data: {
        labels: data.by_master.map((item) => item.master_name),
        datasets: [
          {
            label: "Заявок",
            data: data.by_master.map((item) => item.orders_count),
            backgroundColor: "#047857",
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterLabel(ctx) {
                const entry = data.by_master[ctx.dataIndex];
                return entry ? `Выручка: ${window.ui.formatPrice(entry.revenue)}` : "";
              },
            },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { precision: 0 },
          },
        },
      },
    });
  }

  async function loadStats() {
    const date_from = dateFromInput?.value || "";
    const date_to = dateToInput?.value || "";
    if (date_from && date_to && date_from > date_to) {
      window.ui.showToast("Дата начала не может быть позже даты окончания", "error");
      return;
    }

    showLoading();
    try {
      const data = await window.api.getAdminStats({ date_from, date_to });
      if (!data || data.summary.total_orders === 0) {
        showState(
          "За выбранный период заявок нет",
          "Попробуйте расширить диапазон дат или выбрать период «Всё время».",
          false
        );
        return;
      }

      stateBox.hidden = true;
      contentBox.hidden = false;
      renderKpis(data.summary);
      renderCharts(data);
    } catch (error) {
      showState("Не удалось загрузить статистику", error.message, true);
    }
  }

  periodChips?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement) || !target.classList.contains("chip")) {
      return;
    }
    applyPresetDays(target.dataset.days || "30");
    loadStats();
  });

  periodForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    periodChips?.querySelectorAll(".chip").forEach((chip) => {
      chip.setAttribute("aria-pressed", "false");
    });
    loadStats();
  });

  applyPresetDays("30");
  await loadStats();
});
