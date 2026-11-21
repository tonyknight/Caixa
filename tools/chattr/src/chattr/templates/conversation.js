/* Conversations, over the page: Read the conversation opens a mail conversation's page in a frame
   over this one; Escape, a click beside it or the cross closes it, and Open in its own window shows
   it in a tab of its own. The page works without this: each entry is a link to its page. */
(function () {
  var box = null, frame = null, away = null, last = null;
  function open() { return box !== null && box.classList.contains("open"); }
  function key(event) {
    if (open() && event.key === "Escape") { event.preventDefault(); close(); }
  }
  function make() {
    box = document.createElement("div");
    box.className = "conversation-overlay";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", "Conversation");
    box.innerHTML = '<div class="co-panel"><div class="co-bar">' +
      '<a class="co-away" target="_blank" rel="noopener">Open in its own window</a>' +
      '<button type="button" class="co-close" aria-label="Close">&times;</button></div>' +
      '<iframe title="Conversation"></iframe></div>';
    frame = box.querySelector("iframe");
    away = box.querySelector(".co-away");
    frame.addEventListener("load", function () {
      // Escape inside the frame too, when the browser lets this page reach it (not from disk)
      try { frame.contentWindow.document.addEventListener("keydown", key); } catch (e) { }
    });
    document.body.appendChild(box);
  }
  function show(link) {
    if (box === null) make();
    last = link;
    frame.src = link.href;
    away.href = link.href;
    box.classList.add("open");
    document.documentElement.classList.add("co-open");
    box.querySelector(".co-close").focus();
  }
  function close() {
    box.classList.remove("open");
    document.documentElement.classList.remove("co-open");
    frame.src = "about:blank";
    if (last) last.focus();
  }
  document.addEventListener("click", function (event) {
    var target = event.target;
    if (open()) {
      if (target.closest(".co-close") || !target.closest(".co-panel")) {
        event.preventDefault();
        close();
      }
      return;
    }
    var link = target.closest ? target.closest("a.read-conversation") : null;
    if (!link || event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    show(link);
  });
  document.addEventListener("keydown", key);
})();
