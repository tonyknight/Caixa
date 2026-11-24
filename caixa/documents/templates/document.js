/* Documents, over the page: Open shows a document's PDF in a frame over this one, drawn by the
   browser's own viewer (at the page asked for, #page=N); Escape, a click beside it or the cross
   closes it, and Open in its own window shows it in a tab of its own. The page works without this:
   each card links to its PDF. */
(function () {
  var box = null, frame = null, away = null, title = null, last = null;
  function open() { return box !== null && box.classList.contains("open"); }
  function key(event) {
    if (open() && event.key === "Escape") { event.preventDefault(); close(); }
  }
  function make() {
    box = document.createElement("div");
    box.className = "document-overlay";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", "Document");
    box.innerHTML = '<div class="do-panel"><div class="do-bar"><span class="do-title"></span>' +
      '<a class="do-away" target="_blank" rel="noopener">Open in its own window</a>' +
      '<button type="button" class="do-close" aria-label="Close">&times;</button></div>' +
      '<iframe title="Document"></iframe></div>';
    frame = box.querySelector("iframe");
    away = box.querySelector(".do-away");
    title = box.querySelector(".do-title");
    document.body.appendChild(box);
  }
  function show(link) {
    if (box === null) make();
    last = link;
    frame.src = link.href;
    away.href = link.href;
    title.textContent = link.getAttribute("data-title") || "";
    box.classList.add("open");
    document.documentElement.classList.add("do-open");
    box.querySelector(".do-close").focus();
  }
  function close() {
    box.classList.remove("open");
    document.documentElement.classList.remove("do-open");
    frame.src = "about:blank";
    if (last) last.focus();
  }
  document.addEventListener("click", function (event) {
    var target = event.target;
    if (open()) {
      if (target.closest(".do-close") || !target.closest(".do-panel")) {
        event.preventDefault();
        close();
      }
      return;
    }
    var link = target.closest ? target.closest("a.open-document") : null;
    if (!link || event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    show(link);
  });
  document.addEventListener("keydown", key);
})();
