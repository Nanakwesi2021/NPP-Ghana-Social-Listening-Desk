// Keyboard shortcuts: j/k rows, g then o/t/i/s to navigate, / search, a take ownership, ? help.
// Ignored while typing in a field or with a modifier key held.
(() => {
  const dialog = document.getElementById("shortcuts");
  const typing = (el) => el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
  const rows = () => [...document.querySelectorAll("[data-row]")].filter((el) => el.offsetParent !== null);
  let awaitingG = false;
  let gTimer;

  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-open-shortcuts]") && dialog) dialog.showModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || typing(e.target)) return;
    if (awaitingG) {
      awaitingG = false;
      const link = document.querySelector(`[data-nav="${e.key}"]`);
      if (link) { e.preventDefault(); link.click(); }
      return;
    }
    switch (e.key) {
      case "g":
        awaitingG = true;
        clearTimeout(gTimer);
        gTimer = setTimeout(() => { awaitingG = false; }, 1200);
        break;
      case "j":
      case "k": {
        const list = rows();
        if (!list.length) return;
        e.preventDefault();
        const i = list.indexOf(document.activeElement);
        const next = i === -1 ? 0 : e.key === "j" ? Math.min(i + 1, list.length - 1) : Math.max(i - 1, 0);
        list[next].focus();
        break;
      }
      case "/": {
        const search = document.querySelector("[data-search]");
        if (search && search.offsetParent !== null) { e.preventDefault(); search.focus(); }
        break;
      }
      case "a": {
        const take = document.querySelector('form[data-shortcut="take"]');
        if (take) { e.preventDefault(); take.requestSubmit(); }
        break;
      }
      case "?":
        if (dialog) { e.preventDefault(); dialog.showModal(); }
        break;
    }
  });
})();
