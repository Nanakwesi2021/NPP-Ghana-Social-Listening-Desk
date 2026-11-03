// Refreshes server-rendered panels ([data-refresh-url]) once a minute. Pauses while the tab is
// hidden, never swaps a panel that holds keyboard focus, and keeps the last good data on failure.
(() => {
  const regions = [...document.querySelectorAll("[data-refresh-url]")];
  if (!regions.length) return;
  const seconds = Number(document.body.dataset.refreshSeconds || 60);
  const banner = document.querySelector("[data-offline-banner]");
  const title = banner && banner.querySelector("[data-offline-title]");
  const gmt = (d) => d.toISOString().slice(11, 16);
  let timer;

  async function refresh() {
    if (document.hidden) return;
    try {
      for (const region of regions) {
        if (region.contains(document.activeElement)) continue;
        const res = await fetch(region.dataset.refreshUrl, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } });
        if (res.redirected) { window.location.reload(); return; }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        region.innerHTML = await res.text();
      }
      if (banner) banner.hidden = true;
    } catch (err) {
      if (banner) {
        banner.hidden = false;
        if (title) title.textContent = `Could not refresh at ${gmt(new Date())} GMT`;
      }
    }
  }

  function start() {
    clearInterval(timer);
    timer = setInterval(refresh, seconds * 1000);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) { refresh(); start(); }
  });
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-refresh-now]")) refresh();
  });
  start();
})();
