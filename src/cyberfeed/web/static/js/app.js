/* CyberFeed — client-side JS (HTMX config, theme toggle, helpers) */

// Theme toggle (DaisyUI data-theme)
(function initTheme() {
  const html = document.documentElement;
  if (!localStorage.getItem("theme")) {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    localStorage.setItem("theme", prefersDark ? "dark" : "light");
  }
  html.setAttribute("data-theme", localStorage.getItem("theme"));
})();

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  html.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
}

// HTMX: attach access_token to all requests from cookie (already httpOnly)
// HTMX: show toast on errors
document.addEventListener("htmx:responseError", function (evt) {
  const toast = document.getElementById("toast-container");
  if (toast) {
    const msg = evt.detail.xhr?.statusText || "Request failed";
    showToast(msg, "error");
  }
});

// Toast helper
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const alertClass =
    type === "error"
      ? "alert-error"
      : type === "success"
        ? "alert-success"
        : "alert-info";

  const div = document.createElement("div");
  div.className = `alert ${alertClass} toast-enter`;
  div.innerHTML = `<span>${message}</span>`;
  container.appendChild(div);

  setTimeout(() => {
    div.style.opacity = "0";
    div.style.transition = "opacity 0.3s";
    setTimeout(() => div.remove(), 300);
  }, 3000);
}

// HTMX: handle HX-Trigger response header for toasts + close modals on success
document.addEventListener("htmx:afterRequest", function (evt) {
  const trigger = evt.detail.xhr?.getResponseHeader("HX-Trigger");
  if (trigger) {
    try {
      const data = JSON.parse(trigger);
      if (data.showToast) {
        showToast(data.showToast.message, data.showToast.type);
      }
    } catch {
      // not JSON, ignore
    }
  }

  // Close modals and reload on successful form submissions
  if (evt.detail.successful) {
    const formId = evt.detail.elt?.id;
    if (formId === "add-source-form") {
      document.getElementById("add-source-modal")?.close();
      location.reload();
    }
    if (formId === "add-notification-form") {
      document.getElementById("add-notification-modal")?.close();
      location.reload();
    }
    if (formId === "add-category-form") {
      document.getElementById("add-category-modal")?.close();
      location.reload();
    }
  }
});

// Service worker registration
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}
