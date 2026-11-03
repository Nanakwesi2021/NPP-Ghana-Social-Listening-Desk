// Small progressive enhancements. Without JavaScript every filter has an Apply button and
// every section of an issue is visible.
(() => {
  // Filters submit when a select changes (delegated, so it survives panel refreshes).
  document.addEventListener("change", (e) => {
    const form = e.target.closest("form[data-autosubmit]");
    if (form && e.target.matches("select")) form.requestSubmit();
  });

  // Close an open menu or decision form when clicking elsewhere.
  document.addEventListener("click", (e) => {
    document.querySelectorAll("details[open]").forEach((d) => {
      if (!d.contains(e.target)) d.open = false;
    });
  });

  // Issue review on narrow screens: Original · Evidence · History tabs.
  const tabs = document.querySelector("[data-tabs]");
  if (!tabs) return;
  const narrow = window.matchMedia("(max-width: 767px)");
  const panels = [...document.querySelectorAll("[data-tab-panel]")];

  function select(name) {
    tabs.querySelectorAll("[data-tab]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === name)));
    panels.forEach((p) => { p.hidden = narrow.matches && p.dataset.tabPanel !== name; });
  }

  function fromHash() {
    const target = location.hash && document.getElementById(location.hash.slice(1));
    const panel = target && target.closest("[data-tab-panel]");
    select(panel ? panel.dataset.tabPanel : "original");
  }

  tabs.addEventListener("click", (e) => {
    const tab = e.target.closest("[data-tab]");
    if (!tab) return;
    e.preventDefault();
    select(tab.dataset.tab);
    history.replaceState(null, "", `#${tab.dataset.tab}`);
  });
  document.querySelectorAll("[data-tab-link]").forEach((a) => a.addEventListener("click", () => select(a.dataset.tabLink)));
  narrow.addEventListener("change", fromHash);
  fromHash();
})();
