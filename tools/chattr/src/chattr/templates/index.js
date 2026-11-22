/* The box's index: a category at a time, sorting people into categories and their subcategories,
   naming the people nobody named and removing people from the box. Without this script every section shows, one after
   another. Changes need Caixa (it saves them in the box); opened any other way the page says so
   and only browses. */
(function () {
  document.documentElement.className += " js";
  // opened in Caixa, which serves the box under /box/
  var CAIXA = /^https?:$/.test(location.protocol) &&
    (location.pathname === "/box/" || location.pathname === "/box/index.html");
  var LABELS = { all: "All people", family: "Family", friends: "Friends", business: "Business",
    acquaintance: "Acquaintances", unrecognized: "Unrecognized", unassigned: "Unassigned",
    groups: "Groups", mail: "Mail" };
  var ASSIGNED = { family: 1, friends: 1, business: 1, acquaintance: 1 };
  var CHOOSING = { unassigned: 1, unrecognized: 1 };  // the views where people are selected
  var NEEDS_CAIXA = "Changing the box works when it is opened in Caixa.";
  // The script brings the styles for what it adds, so a page drawn by an earlier version (Caixa
  // serves every page with the current script) looks right too.
  var STYLE = [
    "[hidden]{display:none !important}",
    ".cell{position:relative;display:flex;flex-direction:column}",
    ".cell .tile{flex:1}",
    ".cell .tool{position:absolute;top:.3rem;right:.4rem;z-index:3;width:1.6rem;height:1.6rem;padding:0;border-radius:50%;border:1px solid var(--line);background:var(--card);color:var(--fg);font:inherit;font-size:.9rem;line-height:1;cursor:pointer;display:grid;place-items:center;box-shadow:0 1px 3px var(--shadow);opacity:0;pointer-events:none;transition:opacity .12s}",
    ".cell:hover .tool,.cell:focus-within .tool{opacity:1;pointer-events:auto}",
    ".cell .tool:hover,.cell .tool:focus-visible{background:var(--accent);color:var(--on-accent);border-color:var(--accent)}",
    ".cell .tool.unassign:hover,.cell .tool.unassign:focus-visible{background:#bf616a;border-color:#bf616a;color:#eceff4}",
    ".tile.selected::after{right:auto !important;left:.6rem}",
    ".cell .naming{position:relative;display:flex;gap:.3rem;align-items:center;margin:.35rem .35rem 0;visibility:hidden}",
    ".cell:hover .naming,.cell:focus-within .naming,.cell .naming.filled{visibility:visible}",
    ".cell .naming input{flex:1;min-width:0;font:inherit;font-size:.8rem;padding:.3rem .5rem;border:1px solid var(--line);border-radius:.45rem;background:var(--card);color:var(--fg)}",
    ".cell .naming input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 30%,transparent)}",
    ".cell .naming .apply{font:inherit;font-size:.78rem;padding:.3rem .6rem;border-radius:.45rem;border:1px solid var(--accent);background:var(--accent);color:var(--on-accent);cursor:pointer}",
    ".cell .naming .suggest{position:absolute;left:0;right:0;top:calc(100% + .2rem);z-index:6;margin:0;padding:.25rem;list-style:none;background:var(--card);border:1px solid var(--line);border-radius:.5rem;box-shadow:0 6px 18px var(--shadow);text-align:left;max-height:14rem;overflow-y:auto}",
    ".cell .naming .suggest li{padding:.3rem .5rem;border-radius:.35rem;font-size:.8rem;cursor:pointer;overflow-wrap:anywhere}",
    ".cell .naming .suggest li[aria-selected=true],.cell .naming .suggest li:hover{background:var(--accent);color:var(--on-accent)}",
    ".cell .naming .suggest li small{display:block;opacity:.75;font-size:.7rem}",
    ".app[data-view=unrecognized] .tile .tip{top:auto;bottom:calc(100% - .3rem)}",
    ".cell:focus-within .tile .tip{display:none !important}",
    "dialog.confirm{border:1px solid var(--line);border-radius:.8rem;background:var(--card);color:var(--fg);padding:1.2rem 1.4rem;max-width:26rem;box-shadow:0 10px 30px var(--shadow)}",
    "dialog.confirm::backdrop{background:rgba(46,52,64,.45)}",
    "dialog.confirm h2{font-size:1.05rem;margin:0 0 .5rem}dialog.confirm p{font-size:.9rem;color:var(--muted);margin:0 0 1rem}",
    "dialog.confirm .buttons{display:flex;justify-content:flex-end;gap:.5rem}",
    "dialog.confirm button{font:inherit;font-size:.88rem;padding:.35rem .9rem;border-radius:.5rem;border:1px solid var(--line);background:var(--panel);color:var(--fg);cursor:pointer}",
    "dialog.confirm button.danger{background:#bf616a;border-color:#bf616a;color:#eceff4}"
  ].join("\n");
  function init() {
    var app = document.querySelector(".app");
    if (!app || app.getAttribute("data-ready")) return;
    app.setAttribute("data-ready", "1");
    var style = document.createElement("style");
    style.textContent = STYLE;
    document.head.appendChild(style);
    var tiles = Array.prototype.slice.call(document.querySelectorAll("#people .tile"));
    var title = document.getElementById("view-title");
    var footer = { count: document.getElementById("count"), picked: document.getElementById("picked"),
      actions: document.getElementById("actions"), said: document.getElementById("said") };
    var view = "all", anchor = null;
    function cell(tile) { return tile.parentNode; }
    // How many items a tile stands for: its data-items, or (on a page drawn before it had one) the
    // number its counts line begins with, as in "1,234 items · 2019–2024".
    function items(tile) {
      var given = tile.getAttribute("data-items");
      if (given !== null) return Number(given) || 0;
      var meta = tile.querySelector(".meta");
      var found = meta && /^\s*([\d.,\s\u00a0\u202f]+?)\s*items?\b/.exec(meta.textContent);
      return found ? Number(found[1].replace(/\D/g, "")) || 0 : 0;
    }
    tiles.forEach(function (t, i) { t.setAttribute("data-order", String(i)); });
    // a tile renamed in place takes the place its new name has among the others
    function renumber(renamed) {
      var others = tiles.filter(function (t) { return t !== renamed; }).sort(function (a, b) {
        return Number(a.getAttribute("data-order")) - Number(b.getAttribute("data-order"));
      });
      var key = renamed.querySelector(".name").textContent.toLowerCase(), at = others.length;
      for (var i = 0; i < others.length; i++) {
        if (others[i].querySelector(".name").textContent.toLowerCase().localeCompare(key) > 0) { at = i; break; }
      }
      others.splice(at, 0, renamed);
      others.forEach(function (t, n) { t.setAttribute("data-order", String(n)); });
    }
    // Unrecognized is worked through busiest first: the most items on top. Everywhere else, the
    // page's own order (by name).
    function arrange(name) {
      var order = function (a, b) { return Number(a.getAttribute("data-order")) - Number(b.getAttribute("data-order")); };
      tiles.sort(name === "unrecognized" ? function (a, b) { return items(b) - items(a) || order(a, b); } : order);
      var gallery = document.getElementById("people");
      tiles.forEach(function (t) { gallery.appendChild(cell(t)); });
    }
    // --- Subcategories: views named sub-<id>, each holding its people and its own's -----------
    function subLink(id) { return document.querySelector('.sidebar a[data-sub="' + id + '"]'); }
    function subName(link) { return link ? link.firstChild.textContent.trim() : ""; }
    function isSub(name) { return /^sub-\d+$/.test(name) && subLink(name.slice(4)) !== null; }
    function inSub(tile, id) {
      var own = tile.getAttribute("data-sub");
      if (!own) return false;
      if (own === id) return true;
      var link = subLink(own);
      return link !== null && link.getAttribute("data-parent") === id;
    }
    // Each category and subcategory holds only its own people, as a folder holds only its own
    // files; ⌘-click on its label flattens it (everyone beneath it too), and again nests it.
    var FLAT = "caixa-index-flat";
    var flat = {};
    try { (JSON.parse(localStorage.getItem(FLAT) || "[]") || []).forEach(function (k) { flat[k] = true; }); } catch (e) { /* (from disk: not kept) */ }
    function flattens(name) {  // a label with something beneath it: a category, or a subcategory that can have its own
      return !!ASSIGNED[name] || (isSub(name) && !subLink(name.slice(4)).getAttribute("data-parent"));
    }
    function flatten(name) {
      if (flat[name]) delete flat[name]; else flat[name] = true;
      try { localStorage.setItem(FLAT, JSON.stringify(Object.keys(flat))); } catch (e) { /* (from disk: not kept) */ }
      marks();
    }
    function marks() {
      Array.prototype.forEach.call(document.querySelectorAll(".sidebar [data-view]"), function (link) {
        link.classList.toggle("flat", !!flat[link.getAttribute("data-view")]);
      });
    }
    function label(name) {
      var text = isSub(name) ? subName(subLink(name.slice(4))) : LABELS[name];
      return flat[name] && flattens(name) ? text + ", with its subcategories" : text;
    }
    function belongs(tile, name) {
      if (/^sub-/.test(name)) {
        var id = name.slice(4);
        return flat[name] ? inSub(tile, id) : tile.getAttribute("data-sub") === id;
      }
      var category = tile.getAttribute("data-category");
      if (ASSIGNED[name]) return category === name && (flat[name] || !tile.getAttribute("data-sub"));
      if (name === "all") return category !== "unrecognized";
      if (name === "unassigned") return category === "";
      return category === name;
    }
    function shown() { return tiles.filter(function (t) { return belongs(t, view); }); }
    // a category or a subcategory, in Caixa: a click opens the page; ⌘-click, Shift-⌘-click and a
    // box drawn around people select them, to move them into a subcategory
    function inCategory(name) { return CAIXA && (ASSIGNED[name] || isSub(name)); }
    function selecting(name) { return (CHOOSING[name] && CAIXA) || inCategory(name); }
    function selected() { return tiles.filter(function (t) { return t.classList.contains("selected"); }); }
    function plural(n, word) { return n.toLocaleString() + " " + word + (n === 1 ? "" : "s"); }
    function people(n) { return plural(n, "person").replace("persons", "people"); }
    function say(text) { footer.said.textContent = text || ""; }
    function rpc(method, params) {
      return fetch("/api/caixa/rpc", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" },
        body: JSON.stringify({ method: method, params: params }) })
        .then(function (response) { return response.json(); })
        .then(function (reply) {
          if (!reply.ok) throw new Error((reply.error && reply.error.message) || "Caixa refused.");
          return reply.result;
        }, function () { throw new Error("Caixa could not be reached."); });
    }
    function counts() {
      Array.prototype.forEach.call(document.querySelectorAll(".sidebar [data-view]"), function (link) {
        var name = link.getAttribute("data-view"), badge = link.querySelector(".n");
        if (!badge || name === "groups" || name === "mail") return;
        badge.textContent = tiles.filter(function (t) { return belongs(t, name); }).length.toLocaleString();
      });
    }
    function update() {
      tiles.forEach(function (t) { cell(t).hidden = !belongs(t, view); });
      if (view === "groups") footer.count.textContent = plural(document.querySelectorAll("#groups .tile").length, "group");
      else if (view === "mail") footer.count.textContent = plural(document.querySelectorAll("#mail li").length, "conversation");
      else footer.count.textContent = people(shown().length);
      var picked = selected().length;
      footer.picked.textContent = selecting(view) ? picked.toLocaleString() + " selected" : "";
      footer.actions.hidden = !(view === "unassigned" && CAIXA && picked);
      app.setAttribute("data-picked", picked ? "1" : "");
      counts();
    }
    function unpick(t) { t.classList.remove("selected"); if (t.hasAttribute("aria-pressed")) t.setAttribute("aria-pressed", "false"); }
    function clear() { selected().forEach(unpick); anchor = null; }
    function choosable(t, name) { return CAIXA && ((name === "unassigned" && t.getAttribute("data-name") !== null) || name === "unrecognized"); }
    function show(name) {
      if (!LABELS[name] && !isSub(name)) name = "all";
      view = name;
      clear();
      arrange(name);
      say(CHOOSING[name] && !CAIXA ? NEEDS_CAIXA : "");
      var hint = document.querySelector(".hint.selecting");
      if (hint) hint.hidden = !inCategory(name);
      app.setAttribute("data-view", name);
      title.textContent = label(name);
      Array.prototype.forEach.call(document.querySelectorAll(".sidebar [data-view]"), function (link) {
        link.classList.toggle("current", link.getAttribute("data-view") === name);
      });
      tiles.forEach(function (t) {
        var pickable = choosable(t, name);
        // dragged onto a category or a subcategory: from Unassigned, or from within a category
        t.draggable = CAIXA;  // onto a category, a subcategory, Unassigned or another person, from any view
        if (pickable) t.setAttribute("aria-pressed", "false"); else t.removeAttribute("aria-pressed");
      });
      update();
    }
    function pick(tile, range) {
      if (range && anchor) {
        var list = shown(), from = list.indexOf(anchor), to = list.indexOf(tile);
        if (from > to) { var swap = from; from = to; to = swap; }
        list.slice(from, to + 1).forEach(function (t) { t.classList.add("selected"); t.setAttribute("aria-pressed", "true"); });
      } else {
        var on = !tile.classList.contains("selected");
        tile.classList.toggle("selected", on);
        tile.setAttribute("aria-pressed", on ? "true" : "false");
        anchor = tile;
      }
      update();
    }
    // Someone known only by a number or address is kept as a person, under that name, before they
    // are sorted (as naming them does).
    function keepAsPeople(chosen) {
      var chain = Promise.resolve();
      chosen.forEach(function (t) {
        if (t.getAttribute("data-name") !== null) return;
        var who = t.querySelector(".name").textContent.trim();
        JSON.parse(t.getAttribute("data-handles") || "[]").forEach(function (h) {
          chain = chain.then(function () { return rpc("people.link", { service: h.service, identifier: h.identifier, person: who }); });
        });
        chain = chain.then(function () {
          t.setAttribute("data-name", who);
          t.removeAttribute("data-handles");
          var form = cell(t).querySelector(".naming");
          if (form) form.parentNode.removeChild(form);
          known.push({ name: who, detail: "" });
        });
      });
      return chain;
    }
    function categorize(chosen, category, done, sub) {
      if (!chosen.length) return;
      if (!CAIXA) { say(NEEDS_CAIXA); return; }
      say("Saving…");
      if (category === "unrecognized") chosen = chosen.filter(function (t) { return t.getAttribute("data-name") !== null; });
      keepAsPeople(chosen).then(function () {
        var names = chosen.map(function (t) { return t.getAttribute("data-name"); });
        if (!names.length) return [];
        var params = { people: names, category: category };
        if (sub) params.subcategory = Number(sub);
        return rpc("people.categorize", params).then(function () { return names; });
      }).then(function (names) {
        if (!names.length) return;
        chosen.forEach(function (t) {
          t.setAttribute("data-category", category || "");
          if (sub) t.setAttribute("data-sub", sub); else t.removeAttribute("data-sub");
          unpick(t); t.draggable = CAIXA; t.removeAttribute("aria-pressed");
        });
        anchor = null;
        say(done(names.length));
        update();
      }).catch(function (error) { say("Not saved: " + error.message); });
    }
    function move(category, sub) {
      category = category || null;  // (Unassigned: no category)
      var chosen = selected(), where = sub ? subName(subLink(sub)) : LABELS[category || "unassigned"];
      categorize(chosen, category, function (n) { return people(n) + " moved to " + where + "."; }, sub);
      setTimeout(function () { show(view); }, 0);
    }

    // --- Removing people from the box ------------------------------------------------------
    var dialog = document.createElement("dialog");
    dialog.className = "confirm";
    dialog.setAttribute("aria-labelledby", "confirm-title");
    dialog.innerHTML = '<h2 id="confirm-title"></h2><p></p><div class="buttons">' +
      '<button type="button" value="cancel">Cancel</button><button type="button" class="danger" value="delete">Delete</button></div>';
    document.body.appendChild(dialog);
    var asking = null;
    dialog.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) return;
      dialog.close();
      var then = asking; asking = null;
      if (button.value === "delete" && then) then();
    });
    dialog.addEventListener("cancel", function () { asking = null; });
    function confirmRemoval(chosen) {
      var n = chosen.length;
      dialog.querySelector("h2").textContent = "Delete " + people(n) + " from this box?";
      dialog.querySelector("p").textContent = (n === 1 ? "Their" : "Each one's") +
        " conversations with you and the photos, recordings and files in them are deleted, and later imports leave them out. " +
        "What they wrote in group conversations stays. This can't be undone.";
      asking = function () { remove(chosen); };
      if (dialog.showModal) dialog.showModal(); else if (window.confirm(dialog.querySelector("h2").textContent)) remove(chosen);
      dialog.querySelector("button.danger").focus();
    }
    function remove(chosen) {
      var names = [], handles = [];
      chosen.forEach(function (t) {
        var name = t.getAttribute("data-name");
        if (name !== null) names.push(name);
        else handles = handles.concat(JSON.parse(t.getAttribute("data-handles") || "[]"));
      });
      say("Deleting…");
      rpc("people.delete", { people: names, handles: handles }).then(function () {
        chosen.forEach(function (t) { var c = cell(t); c.parentNode.removeChild(c); });
        tiles = tiles.filter(function (t) { return chosen.indexOf(t) < 0; });
        anchor = null;
        say(people(chosen.length) + " deleted. The pages are being redrawn.");
        update();
      }, function (error) { say("Not deleted: " + error.message); });
    }

    // --- Naming someone nobody named -------------------------------------------------------
    // The people already in the box, offered as a name is typed (so a number can join someone
    // known); any other name makes a new person.
    var known = [];
    function learnKnown(list) {
      var seen = {};
      known = list.filter(function (p) {
        var key = p.name.toLowerCase();
        if (!p.name || seen[key]) return false;
        seen[key] = 1;
        return true;
      }).sort(function (a, b) { return a.name.localeCompare(b.name); });
    }
    learnKnown(tiles.filter(function (t) { return t.getAttribute("data-name") !== null; })
      .map(function (t) { return { name: t.getAttribute("data-name"), detail: "" }; }));
    if (CAIXA) {
      rpc("people.list", {}).then(function (result) {
        learnKnown(result.people.filter(function (p) { return !p.is_owner; }).map(function (p) {
          return { name: p.name, detail: p.items ? plural(p.items, "item") : "" };
        }));
      }, function () { /* the names on the page will do */ });
    }
    function existing(typed) {
      var key = typed.toLowerCase();
      for (var i = 0; i < known.length; i++) if (known[i].name.toLowerCase() === key) return known[i].name;
      return null;
    }
    function matches(typed) {
      var key = typed.trim().toLowerCase();
      if (!key) return [];
      var first = [], then = [];
      known.forEach(function (p) {
        var name = p.name.toLowerCase();
        if (name.indexOf(key) === 0) first.push(p);
        else if (name.split(/\s+/).some(function (word) { return word.indexOf(key) === 0; }) || name.indexOf(key) > 0) then.push(p);
      });
      return first.concat(then).slice(0, 8);
    }
    function name(tile, typed) {
      var handles = JSON.parse(tile.getAttribute("data-handles") || "[]");
      if (!handles.length) return;
      var joins = existing(typed);
      if (joins) typed = joins;
      say("Saving…");
      var chain = Promise.resolve();
      handles.forEach(function (h) {
        chain = chain.then(function () { return rpc("people.link", { service: h.service, identifier: h.identifier, person: typed }); });
      });
      chain.then(function () {
        if (joins) {  // someone already in the box: the tile joins theirs when the pages are redrawn
          var gone = cell(tile);
          gone.parentNode.removeChild(gone);
          tiles = tiles.filter(function (t) { return t !== tile; });
          say("Linked to " + joins + ". Their page is being redrawn with everything from this number.");
          update();
          return;
        }
        unpick(tile);
        tile.removeAttribute("aria-pressed");
        tile.removeAttribute("data-handles");
        tile.setAttribute("data-name", typed);
        tile.setAttribute("data-category", "");
        tile.querySelector(".name").textContent = typed;
        renumber(tile);
        labels(cell(tile), typed);
        var form = cell(tile).querySelector(".naming");
        if (form) form.parentNode.removeChild(form);
        known.push({ name: typed, detail: "" });
        say(typed + " is kept as a person, in Unassigned.");
        update();
      }, function (error) { say("Not saved: " + error.message); });
    }

    // --- Each tile in a cell, with its tools -----------------------------------------------
    function labels(box, who) {
      var open = box.querySelector(".tool.window"), out = box.querySelector(".tool.unassign");
      if (open) open.setAttribute("aria-label", "Open " + who + " in a new window");
      if (out) out.setAttribute("aria-label", "Move " + who + " back to Unassigned");
    }
    tiles.forEach(function (tile) {
      var box = document.createElement("div");
      box.className = "cell";
      tile.parentNode.insertBefore(box, tile);
      box.appendChild(tile);
      var open = document.createElement("button");
      open.type = "button"; open.className = "tool window"; open.textContent = "↗";
      open.title = "Open in a new window";
      box.appendChild(open);
      if (!CAIXA) { labels(box, tile.querySelector(".name").textContent); return; }
      var out = document.createElement("button");
      out.type = "button"; out.className = "tool unassign"; out.textContent = "×";
      out.title = "Back to Unassigned";
      box.appendChild(out);
      labels(box, tile.querySelector(".name").textContent);
      if (tile.getAttribute("data-name") === null) {
        var form = document.createElement("div");
        form.className = "naming";
        form.innerHTML = '<input type="text" name="name" placeholder="Name" aria-label="Name for this person" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false">' +
          '<button type="button" class="apply" hidden>Apply</button><ul class="suggest" role="listbox" aria-label="People in this box" hidden></ul>';
        box.appendChild(form);
      }
    });
    var gallery = document.getElementById("people");
    gallery.addEventListener("click", function (event) {
      var tool = event.target.closest(".tool");
      if (tool) {
        event.preventDefault();
        var tile = cell(tool).querySelector(".tile");
        if (tool.classList.contains("window")) window.open(tile.href, "_blank", "noopener");
        else categorize([tile], null, function () { return tile.querySelector(".name").textContent + " moved back to Unassigned."; });
        return;
      }
      var apply = event.target.closest(".naming .apply");
      if (apply) { applyName(apply.parentNode); return; }
      var option = event.target.closest(".naming .suggest li");
      if (option) { choose(option.parentNode.parentNode, option.getAttribute("data-name")); return; }
      if (event.target.closest(".naming")) return;
      var picked = event.target.closest(".tile");
      if (!picked) return;
      if (inCategory(view) && (event.metaKey || event.ctrlKey) && picked.getAttribute("data-name") !== null) {
        event.preventDefault();  // selected in place: the page is not opened
        pick(picked, event.shiftKey);
        return;
      }
      if (!CHOOSING[view] || !choosable(picked, view)) return;
      event.preventDefault();
      pick(picked, event.shiftKey);
    });
    // --- The name field: Apply once something is typed, and the people it could be ---------
    function applyName(form) {
      var field = form.querySelector("input"), typed = field.value.trim();
      if (!typed) { field.focus(); return; }
      suggest(form, false);
      name(cell(form).querySelector(".tile"), typed);
    }
    function choose(form, chosen) {
      var field = form.querySelector("input");
      field.value = chosen;
      typing(form);
      suggest(form, false);
      field.focus();
    }
    function suggest(form, open) {
      var list = form.querySelector(".suggest"), field = form.querySelector("input");
      var found = open ? matches(field.value) : [];
      list.innerHTML = "";
      found.forEach(function (p, i) {
        var item = document.createElement("li");
        item.setAttribute("role", "option");
        item.setAttribute("data-name", p.name);
        item.setAttribute("aria-selected", i === 0 ? "true" : "false");
        item.textContent = p.name;
        if (p.detail) { var small = document.createElement("small"); small.textContent = p.detail; item.appendChild(small); }
        list.appendChild(item);
      });
      list.hidden = !found.length;
      field.setAttribute("aria-expanded", found.length ? "true" : "false");
    }
    function typing(form) {
      var filled = form.querySelector("input").value.trim() !== "";
      form.classList.toggle("filled", filled);
      form.querySelector(".apply").hidden = !filled;
    }
    gallery.addEventListener("input", function (event) {
      var form = event.target.closest && event.target.closest(".naming");
      if (!form) return;
      typing(form);
      suggest(form, true);
    });
    gallery.addEventListener("keydown", function (event) {
      var field = event.target.closest && event.target.closest(".naming input");
      if (!field) return;
      var form = field.parentNode, list = form.querySelector(".suggest");
      var items = Array.prototype.slice.call(list.querySelectorAll("li"));
      var at = items.findIndex(function (li) { return li.getAttribute("aria-selected") === "true"; });
      if ((event.key === "ArrowDown" || event.key === "ArrowUp") && items.length) {
        event.preventDefault();
        var next = event.key === "ArrowDown" ? Math.min(items.length - 1, at + 1) : Math.max(0, at - 1);
        items.forEach(function (li, i) { li.setAttribute("aria-selected", i === next ? "true" : "false"); });
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (!list.hidden && at >= 0) choose(form, items[at].getAttribute("data-name"));
        else applyName(form);
      } else if (event.key === "Escape") {
        suggest(form, false);
      }
    });
    gallery.addEventListener("focusout", function (event) {
      var form = event.target.closest && event.target.closest(".naming");
      if (form && !form.contains(event.relatedTarget)) setTimeout(function () { if (!form.contains(document.activeElement)) suggest(form, false); }, 150);
    });
    // the tools show for the views they belong to
    function tools() {
      Array.prototype.forEach.call(document.querySelectorAll("#people .cell"), function (c) {
        var t = c.querySelector(".tile"), out = c.querySelector(".tool.unassign"), win = c.querySelector(".tool.window"), form = c.querySelector(".naming");
        // one button in the corner: the close box in a category, the open-a-page button where a
        // click selects (Unassigned, Unrecognized)
        if (out) out.hidden = !(CAIXA && ASSIGNED[view] && ASSIGNED[t.getAttribute("data-category")]);
        if (win) win.hidden = !CHOOSING[view];
        if (form) form.hidden = view !== "unrecognized";
      });
    }
    var shownView = show;
    show = function (name) { shownView(name); tools(); };
    var updated = update;
    update = function () { updated(); tools(); };

    document.querySelector(".sidebar").addEventListener("click", function (event) {
      var link = event.target.closest("[data-view]");
      if (!link) return;
      event.preventDefault();
      if ((event.metaKey || event.ctrlKey) && flattens(link.getAttribute("data-view"))) flatten(link.getAttribute("data-view"));
      show(link.getAttribute("data-view"));
      history.replaceState(null, "", "#" + link.getAttribute("data-view"));
    });
    footer.actions.addEventListener("click", function (event) {
      var button = event.target.closest("[data-move]");
      if (button) move(button.getAttribute("data-move"));
    });
    document.addEventListener("keydown", function (event) {
      if (inCategory(view) && event.key === "Escape" && !dialog.open && !(event.target.closest && event.target.closest("input, textarea, select"))) {
        clear(); update(); return;
      }
      if (!CHOOSING[view] || (dialog.open)) return;
      if (event.target.closest && event.target.closest("input, textarea, select")) return;
      if (event.key === "Escape") { clear(); update(); }
      else if (event.key === "Delete" || event.key === "Backspace") {
        var chosen = selected();
        if (!chosen.length) return;
        event.preventDefault();
        if (!CAIXA) { say(NEEDS_CAIXA); return; }
        confirmRemoval(chosen);
      }
    });
    document.addEventListener("dragstart", function (event) {
      var tile = event.target.closest && event.target.closest(".tile");
      if (!tile || !tile.draggable) return;
      if (!tile.classList.contains("selected")) { clear(); pick(tile, false); }
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", selected().length + " people");
      app.classList.add("dragging");
    });
    document.addEventListener("dragend", function () {
      app.classList.remove("dragging");
      if (!selecting(view)) { clear(); update(); }
      Array.prototype.forEach.call(document.querySelectorAll(".drop"), function (el) { el.classList.remove("drop"); });
    });
    var sidebar = document.querySelector(".sidebar");
    function dropTarget(event) { return event.target.closest ? event.target.closest(".sidebar a[data-category]") : null; }
    sidebar.addEventListener("dragover", function (event) {
      var target = dropTarget(event);
      if (!target || !app.classList.contains("dragging")) return;
      event.preventDefault();
      target.classList.add("drop");
    });
    sidebar.addEventListener("dragleave", function (event) { var target = dropTarget(event); if (target) target.classList.remove("drop"); });
    sidebar.addEventListener("drop", function (event) {
      var target = dropTarget(event);
      if (!target) return;
      event.preventDefault();
      target.classList.remove("drop");
      move(target.getAttribute("data-category"), target.getAttribute("data-sub"));
    });

    // --- Folding, adding, renaming and deleting subcategories ------------------------------
    var OPEN = "caixa-index-open";
    function opened() { try { return JSON.parse(localStorage.getItem(OPEN) || "[]"); } catch (e) { return []; } }
    function remember(key, open) {
      var list = opened().filter(function (k) { return k !== key; });
      if (open) list.push(key);
      try { localStorage.setItem(OPEN, JSON.stringify(list)); } catch (e) { /* (from disk, not kept) */ }
    }
    function folding(button, open) {
      var list = document.querySelector('.sidebar .subs[data-for="' + button.getAttribute("data-fold") + '"]');
      button.setAttribute("aria-expanded", open ? "true" : "false");
      if (list) list.hidden = !open;
    }
    var keep = opened();
    Array.prototype.forEach.call(document.querySelectorAll(".sidebar .fold"), function (b) { folding(b, keep.indexOf(b.getAttribute("data-fold")) >= 0); });
    if (CAIXA) Array.prototype.forEach.call(document.querySelectorAll(".sidebar .add"), function (li) { li.hidden = false; });
    function removeButton(row, name) {
      var gone = document.createElement("button");
      gone.type = "button"; gone.className = "remove-sub"; gone.textContent = "×";
      gone.setAttribute("aria-label", "Delete " + name); gone.title = "Delete " + name;
      row.appendChild(gone);
    }
    if (CAIXA) Array.prototype.forEach.call(document.querySelectorAll(".sidebar .sub-row"), function (row) { removeButton(row, subName(row.querySelector("a"))); });
    function element(html) { var box = document.createElement("div"); box.innerHTML = html; return box.firstElementChild; }
    function escapeText(text) { var span = document.createElement("span"); span.textContent = text; return span.innerHTML; }
    function addedRow(category, parent, id, name) {
      var safe = escapeText(name), top = !parent, label = top ? "" : ' data-parent="' + parent + '"';
      var li = element("<li><div class=\"sub-row\">" + (top ? '<button type="button" class="fold" data-fold="sub-' + id + '" aria-expanded="false" aria-label="Subcategories of ' + safe + '"></button>' : "") +
        '<a href="#sub-' + id + '" data-view="sub-' + id + '" data-category="' + category + '" data-sub="' + id + '"' + label + ">" + safe + ' <span class="n">0</span></a></div>' +
        (top ? '<ul class="subs" data-for="sub-' + id + '" hidden><li class="add"><button type="button" class="add-sub" data-category="' + category + '" data-parent="' + id + '" aria-label="Add a subcategory to ' + safe + '">+</button></li></ul>' : "") + "</li>");
      removeButton(li.querySelector(".sub-row"), name);
      return li;
    }
    function placeRow(list, li, name) {
      var rows = Array.prototype.filter.call(list.children, function (c) { return !c.classList.contains("add"); });
      var before = rows.filter(function (c) { return subName(c.querySelector("a")).toLowerCase().localeCompare(name.toLowerCase()) > 0; })[0];
      list.insertBefore(li, before || list.querySelector(":scope > .add"));
    }
    function editor(labelText, value, done, cancel) {
      var field = document.createElement("input");
      field.type = "text"; field.className = "sub-edit"; field.value = value || "";
      field.setAttribute("aria-label", labelText);
      var finished = false;
      field.addEventListener("keydown", function (event) {
        if (event.key === "Enter") { event.preventDefault(); var typed = field.value.trim(); if (typed) { finished = true; done(typed); } }
        else if (event.key === "Escape") { event.preventDefault(); finished = true; cancel(); }
      });
      field.addEventListener("blur", function () { if (!finished) { finished = true; cancel(); } });
      return field;
    }
    sidebar.addEventListener("click", function (event) {
      var fold = event.target.closest(".fold");
      if (fold) {
        event.preventDefault();
        var open = fold.getAttribute("aria-expanded") !== "true";
        folding(fold, open);
        remember(fold.getAttribute("data-fold"), open);
        return;
      }
      var add = event.target.closest(".add-sub");
      if (add && CAIXA) {
        event.preventDefault();
        var li = add.parentNode, category = add.getAttribute("data-category"), parent = add.getAttribute("data-parent");
        var above = parent ? subName(subLink(parent)) : LABELS[category];
        var field = editor("New subcategory of " + above, "", function (typed) {
          say("Saving…");
          var params = { category: category, name: typed };
          if (parent) params.parent = Number(parent);
          rpc("people.subcategory.add", params).then(function (result) {
            li.replaceChild(add, field);
            placeRow(li.parentNode, addedRow(category, parent, String(result.id), typed), typed);
            say(typed + " added under " + above + ".");
          }, function (error) { li.replaceChild(add, field); say("Not saved: " + error.message); });
        }, function () { if (field.parentNode === li) li.replaceChild(add, field); });
        li.replaceChild(field, add);
        field.focus();
        return;
      }
      var gone = event.target.closest(".remove-sub");
      if (gone && CAIXA) {
        event.preventDefault();
        var link = gone.parentNode.querySelector("a[data-sub]");
        confirmDeleteSub(link);
      }
    });
    sidebar.addEventListener("dblclick", function (event) {
      var link = event.target.closest && event.target.closest("a[data-sub]");
      if (!link || !CAIXA) return;
      event.preventDefault();
      var row = link.parentNode, old = subName(link), id = link.getAttribute("data-sub");
      var field = editor("Rename " + old, old, function (typed) {
        say("Saving…");
        rpc("people.subcategory.rename", { id: Number(id), name: typed }).then(function () {
          row.replaceChild(link, field);
          link.firstChild.textContent = typed + " ";
          var li = row.parentNode;
          placeRow(li.parentNode, li, typed);
          if (view === "sub-" + id) title.textContent = typed;
          say(old + " renamed " + typed + ".");
        }, function (error) { row.replaceChild(link, field); say("Not saved: " + error.message); });
      }, function () { if (field.parentNode === row) row.replaceChild(link, field); });
      row.replaceChild(field, link);
      field.focus();
      field.select();
    });
    function confirmDeleteSub(link) {
      var name = subName(link), id = link.getAttribute("data-sub"), parent = link.getAttribute("data-parent");
      var category = link.getAttribute("data-category");
      var up = parent ? subName(subLink(parent)) : LABELS[category];
      dialog.querySelector("h2").textContent = "Delete the subcategory " + name + "?";
      dialog.querySelector("p").textContent = "The people in it" + (parent ? "" : " and in its own subcategories") + " move up to " + up + ". Nobody leaves the box.";
      asking = function () {
        say("Deleting…");
        rpc("people.subcategory.delete", { id: Number(id) }).then(function () {
          var li = link.closest("li"), removed = [id];
          Array.prototype.forEach.call(li.querySelectorAll("a[data-sub]"), function (a) { removed.push(a.getAttribute("data-sub")); });
          tiles.forEach(function (t) {
            if (removed.indexOf(t.getAttribute("data-sub")) < 0) return;
            if (parent) t.setAttribute("data-sub", parent); else t.removeAttribute("data-sub");
          });
          li.parentNode.removeChild(li);
          if (removed.some(function (r) { return view === "sub-" + r; })) show(parent ? "sub-" + parent : category);
          else update();
          say(name + " deleted. Its people are in " + up + ".");
        }, function (error) { say("Not deleted: " + error.message); });
      };
      if (dialog.showModal) dialog.showModal(); else if (window.confirm(dialog.querySelector("h2").textContent)) asking();
      dialog.querySelector("button.danger").focus();
    }
    // --- Drawing a box around people ------------------------------------------------------
    var content = document.querySelector(".content") || gallery.parentNode;
    var box = null, start = null, before = [], moved = false;
    function canPick(t) { return t.getAttribute("data-name") !== null ? true : view === "unrecognized"; }
    content.addEventListener("mousedown", function (event) {
      if (event.button !== 0 || !selecting(view)) return;
      if (event.target.closest(".cell, a, button, input, select, textarea, .dashboard, label")) return;
      event.preventDefault();  // (no text selection while drawing)
      start = { x: event.clientX, y: event.clientY };
      before = event.metaKey || event.ctrlKey ? selected() : [];
      moved = false;
    });
    document.addEventListener("mousemove", function (event) {
      if (!start) return;
      var left = Math.min(start.x, event.clientX), top = Math.min(start.y, event.clientY);
      var right = Math.max(start.x, event.clientX), bottom = Math.max(start.y, event.clientY);
      if (!moved && right - left < 4 && bottom - top < 4) return;
      moved = true;
      if (!box) { box = document.createElement("div"); box.className = "marquee"; document.body.appendChild(box); }
      box.style.left = left + "px"; box.style.top = top + "px";
      box.style.width = (right - left) + "px"; box.style.height = (bottom - top) + "px";
      shown().forEach(function (t) {
        var r = t.getBoundingClientRect();
        var touched = r.right >= left && r.left <= right && r.bottom >= top && r.top <= bottom;
        var on = (touched && canPick(t)) || before.indexOf(t) >= 0;
        t.classList.toggle("selected", on);
        t.setAttribute("aria-pressed", on ? "true" : "false");
      });
      update();
    });
    document.addEventListener("mouseup", function () {
      if (!start) return;
      if (!moved && !before.length) { clear(); update(); }  // a press on the empty space: nothing selected
      var last = selected();
      anchor = last.length ? last[last.length - 1] : null;
      if (box) { box.parentNode.removeChild(box); box = null; }
      start = null;
    });

    marks();
    show((location.hash || "#all").slice(1));
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
