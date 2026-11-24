/* The documents' index: the filter box keeps the documents, and the authors, whose words hold every
   word typed (accents and case aside), and the year range hides the years outside it. Without this
   script everything shows. */
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
})();
