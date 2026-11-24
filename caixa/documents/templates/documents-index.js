/* The documents' index: the filter box keeps the documents, and the authors, whose words hold every
   word typed (accents and case aside), and the year range hides the years outside it. Opened in
   Caixa (under /box/), the search form searches every page's words through Caixa (documents.search)
   and lists the pages found, each opening at its page. Without this script everything shows. */
(function () {
  var controls = document.querySelector(".controls");
  if (!controls) return;
  controls.hidden = false;
  var filter = controls.querySelector(".doc-filter");
  var from = controls.querySelector(".year-from"), to = controls.querySelector(".year-to");
  function plain(text) { return (text || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function apply() {
    var words = plain(filter.value).split(/\s+/).filter(Boolean);
    var low = from.value, high = to.value;
    function within(year) { return !year || ((!low || year >= low) && (!high || year <= high)); }
    Array.prototype.forEach.call(document.querySelectorAll("[data-words]"), function (item) {
      var text = item.getAttribute("data-words");
      var holds = words.every(function (word) { return text.indexOf(word) >= 0; });
      item.hidden = !(holds && within(item.getAttribute("data-year")));
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-year-block]"), function (block) {
      block.hidden = !within(block.getAttribute("data-year-block"));
    });
  }
  filter.addEventListener("input", apply);
  from.addEventListener("change", apply);
  to.addEventListener("change", apply);

  var form = document.querySelector("form.search"), hits = document.querySelector("ol.hits");
  var CAIXA = /^https?:$/.test(location.protocol) && location.pathname.indexOf("/box/") === 0;
  if (!form || !hits || !CAIXA) return;
  form.hidden = false;
  var here = "Documents/PDF/";
  function link(path) { return encodeURI(path.indexOf(here) === 0 ? path.slice(here.length) : "../../" + path); }
  function say(text) {
    hits.textContent = "";
    var item = document.createElement("li");
    item.className = "said";
    item.textContent = text;
    hits.appendChild(item);
  }
  function marked(parent, snippet) {  // [word] becomes <mark>word</mark>, everything else is text
    String(snippet || "").split(/(\[[^\]]*\])/).forEach(function (part) {
      if (/^\[[^\]]*\]$/.test(part)) {
        var mark = document.createElement("mark");
        mark.textContent = part.slice(1, -1);
        parent.appendChild(mark);
      } else if (part) parent.appendChild(document.createTextNode(part));
    });
  }
  function show(found) {
    hits.textContent = "";
    if (!found.length) { say("Nothing found."); return; }
    found.forEach(function (hit) {
      var item = document.createElement("li");
      var title = hit.title || hit.original_filename;
      var head = document.createElement("div");
      var name = document.createElement("strong");
      name.textContent = title;
      head.appendChild(name);
      var where = document.createElement("span");
      where.className = "where";
      where.textContent = " · " + [hit.author, hit.date, "page " + hit.page + (hit.source === "ocr" ? " (read by OCR)" : "")]
        .filter(Boolean).join(" · ");
      head.appendChild(where);
      item.appendChild(head);
      var snippet = document.createElement("p");
      snippet.className = "snippet";
      marked(snippet, hit.snippet);
      item.appendChild(snippet);
      var open = document.createElement("a");
      open.className = "open-document";
      open.href = link(hit.file_path) + "#page=" + hit.page;
      open.setAttribute("data-title", title);
      open.textContent = "Open at page " + hit.page;
      item.appendChild(open);
      hits.appendChild(item);
    });
  }
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var params = { query: form.querySelector(".doc-search").value, limit: 50 };
    var kind = form.querySelector(".doc-type").value;
    if (kind) params.type = kind;
    if (from.value) params.date_from = from.value;
    if (to.value) params.date_to = to.value;
    if (!params.query.trim() && !kind && !from.value && !to.value) { hits.textContent = ""; return; }
    say("Searching…");
    fetch("/api/caixa/rpc", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" },
      body: JSON.stringify({ method: "documents.search", params: params }) })
      .then(function (response) { return response.json(); })
      .then(function (reply) {
        if (!reply.ok) throw new Error((reply.error && reply.error.message) || "Caixa refused.");
        show(reply.result.hits);
      })
      .catch(function (error) { say("The search could not be done: " + error.message); });
  });
})();
