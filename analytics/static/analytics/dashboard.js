"use strict";

const palette = {
  primary: "#2f6fed",
  secondary: "#9db8f5",
  muted: "#c9d3e3",
  band: "rgba(47, 111, 237, 0.12)",
};

function draw(id, config) {
  const canvas = document.getElementById(id);
  if (canvas && window.Chart) {
    new window.Chart(canvas, config);
  }
}

function lineDataset(label, data, color, extra = {}) {
  return { label, data, borderColor: color, backgroundColor: color, tension: 0.25, ...extra };
}

function renderCharts(data) {
  const common = { responsive: true, maintainAspectRatio: false };

  draw("competition-chart", {
    type: "bar",
    data: {
      labels: data.competition.labels,
      datasets: [{ label: "Candidates per vacancy", data: data.competition.values, backgroundColor: palette.primary }],
    },
    options: {
      ...common,
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: { y: { ticks: { autoSkip: false } } },
    },
  });

  draw("trend-chart", {
    type: "line",
    data: {
      labels: data.trend.labels,
      datasets: [
        lineDataset("Candidates", data.trend.candidates, palette.secondary),
        lineDataset("Vacancies", data.trend.vacancies, palette.primary),
      ],
    },
    options: common,
  });

  draw("experience-chart", {
    type: "line",
    data: {
      labels: data.experience.labels,
      datasets: [
        lineDataset("Median", data.experience.median, palette.primary, { borderWidth: 3 }),
        lineDataset("75th percentile", data.experience.p75, palette.secondary, {
          backgroundColor: palette.band,
          fill: "+1",
        }),
        lineDataset("25th percentile", data.experience.p25, palette.secondary),
      ],
    },
    options: {
      ...common,
      scales: { y: { beginAtZero: true, title: { display: true, text: "USD per month" } } },
    },
  });

  draw("dynamics-chart", {
    type: "line",
    data: {
      labels: data.dynamics.labels,
      datasets: [lineDataset("Median, USD", data.dynamics.median, palette.primary)],
    },
    options: {
      ...common,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });

  draw("skills-chart", {
    type: "bar",
    data: {
      labels: data.skills.labels,
      datasets: [
        { label: "Current period", data: data.skills.current, backgroundColor: palette.primary },
        { label: "Previous period", data: data.skills.previous, backgroundColor: palette.muted },
      ],
    },
    options: { ...common, indexAxis: "y" },
  });
}

function submitFiltersOnChange() {
  const form = document.getElementById("filters");
  if (!form) {
    return;
  }
  form.querySelectorAll("select").forEach((select) => {
    select.addEventListener("change", () => form.submit());
  });
}

document.addEventListener("DOMContentLoaded", () => {
  submitFiltersOnChange();
  const payload = document.getElementById("chart-data");
  if (payload) {
    renderCharts(JSON.parse(payload.textContent));
  }
});
