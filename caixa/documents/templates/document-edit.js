/* Documents, corrected by their owner: opened in Caixa (under /box/), a card waiting in Unrecognized
   shows Author and Date to fill in, and every other card a Correct button; Apply sends the values to
   Caixa (documents.update), which files and names the document at once. Each field offers what is
   already known, with where it came from. From disk nothing here shows: the page is for reading. */
(function () {
  var CAIXA = /^https?:$/.test(location.protocol) && location.pathname.indexOf("/box/") === 0;
  if (!CAIXA) return;
  var counter = 0;
  function lists(form) {
    var known = {};
    try { known = JSON.parse(form.getAttribute("data-candidates") || "{}"); } catch (e) { known = {}; }
    Array.prototype.forEach.call(form.querySelectorAll("input[name]"), function (input) {
      var found = known[input.name] || [];
      if (!found.length) return;
      var list = document.createElement("datalist");
      list.id = "known-" + (counter += 1);
      found.forEach(function (one) {
        var option = document.createElement("option");
        option.value = one.value;
        option.label = "from " + one.label;
        list.appendChild(option);
      });
      form.appendChild(list);
      input.setAttribute("list", list.id);
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll("form.edit"), function (form) {
    lists(form);
    var said = form.querySelector(".said");
    var card = form.closest(".card");
    var button = card ? card.querySelector("button.correct") : null;
    if (form.getAttribute("data-unrecognized")) form.hidden = false;
    else if (button) {
      button.hidden = false;
      button.addEventListener("click", function () { form.hidden = !form.hidden; });
    }
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var params = { item_id: form.getAttribute("data-item") };
      Array.prototype.forEach.call(form.querySelectorAll("[name]"), function (field) {
        if (field.value.trim()) params[field.name] = field.value.trim();
      });
      said.textContent = "Filing…";
      fetch("/api/caixa/rpc", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" },
        body: JSON.stringify({ method: "documents.update", params: params }) })
        .then(function (response) { return response.json(); })
        .then(function (reply) {
          if (!reply.ok) throw new Error((reply.error && reply.error.message) || "Caixa refused.");
          said.textContent = "Filed as " + reply.result.document.file_path + ". The pages show it after Update the pages.";
        })
        .catch(function (error) { said.textContent = error.message; });
    });
  });
})();
