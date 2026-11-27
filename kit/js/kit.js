/* kit.js — dialog pattern only (04 §7.2), must stay ≤ 1 KB minified. */
(function () {
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-dialog-open]");
    if (!t) return;
    var d = document.getElementById(t.getAttribute("data-dialog-open"));
    if (d && d.showModal) d.showModal();
  });
  document.addEventListener("close", function (e) {
    var d = e.target;
    if (!d || d.tagName !== "DIALOG" || d.returnValue !== "confirm") return;
    var f = document.getElementById(d.getAttribute("data-submit-form") || "");
    if (f) f.requestSubmit ? f.requestSubmit() : f.submit();
  }, true);
})();
