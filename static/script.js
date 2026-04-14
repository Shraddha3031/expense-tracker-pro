function toggleTheme() {
  const body = document.body;
  const btn = document.getElementById("themeToggleBtn");

  body.classList.toggle("dark-theme");

  if (body.classList.contains("dark-theme")) {
    localStorage.setItem("theme", "dark");
    if (btn) btn.textContent = "🌞 Light Mode";
  } else {
    localStorage.setItem("theme", "light");
    if (btn) btn.textContent = "🌙 Dark Mode";
  }
}

function loadSavedTheme() {
  const savedTheme = localStorage.getItem("theme");
  const btn = document.getElementById("themeToggleBtn");

  if (savedTheme === "dark") {
    document.body.classList.add("dark-theme");
    if (btn) btn.textContent = "🌞 Light Mode";
  } else {
    if (btn) btn.textContent = "🌙 Dark Mode";
  }
}

function animateCounters() {
  const counters = document.querySelectorAll(".count-value");

  counters.forEach((counter) => {
    const target = parseFloat(counter.dataset.target) || 0;
    const duration = 1200;
    const steps = 60;
    const increment = Math.abs(target) / steps;
    let current = 0;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      current += increment;

      if (target < 0) {
        counter.textContent = `₹-${current.toFixed(0)}`;
      } else {
        counter.textContent = `₹${current.toFixed(0)}`;
      }

      if (step >= steps) {
        clearInterval(timer);
        if (target < 0) {
          counter.textContent = `₹-${Math.abs(target).toFixed(0)}`;
        } else {
          counter.textContent = `₹${target.toFixed(0)}`;
        }
      }
    }, duration / steps);
  });
}

function animateProgressBar() {
  const progressFill = document.querySelector(".progress-fill");
  if (!progressFill) return;

  const progress = parseFloat(progressFill.dataset.progress) || 0;

  setTimeout(() => {
    progressFill.style.width = `${progress}%`;
  }, 250);
}

function loadChart() {
  const chartCanvas = document.getElementById("expenseChart");

  if (
    chartCanvas &&
    typeof chartLabels !== "undefined" &&
    typeof chartValues !== "undefined" &&
    chartLabels.length > 0
  ) {
    new Chart(chartCanvas, {
      type: "doughnut",
      data: {
        labels: chartLabels,
        datasets: [
          {
            data: chartValues,
            borderWidth: 1
          }
        ]
      },
      options: {
        responsive: true,
        animation: {
          duration: 1400
        },
        plugins: {
          legend: {
            position: "bottom"
          }
        }
      }
    });
  }
}

function changeFilter(value) {
  const url = new URL(window.location.href);
  url.searchParams.set("filter", value);
  window.location.href = url.toString();
}

function scrollToSection(id) {
  const element = document.getElementById(id);
  if (element) {
    element.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  loadSavedTheme();
  animateCounters();
  animateProgressBar();
  loadChart();
});