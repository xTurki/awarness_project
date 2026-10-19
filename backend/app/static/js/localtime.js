/* Convert between UTC (stored on the server) and the user's local time.
 * Without JavaScript, times are shown and entered in UTC.
 */
(function () {
  "use strict";

  function zoneName() {
    try {
      return new Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch (e) {
      return "";
    }
  }

  /* Parse a UTC value from the server (adds "Z" if missing). */
  function fromUtc(iso) {
    if (!iso) return null;
    var stamped = /Z$|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z";
    var d = new Date(stamped);
    return isNaN(d.getTime()) ? null : d;
  }

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  /* Format for a datetime-local input. */
  function asInputValue(d) {
    return (
      d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      "T" + pad(d.getHours()) + ":" + pad(d.getMinutes())
    );
  }

  var readable = {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  };

  /* Show <time data-utc> elements in local time. */
  function showLocalTimes(root) {
    root.querySelectorAll("time[data-utc]").forEach(function (el) {
      var d = fromUtc(el.getAttribute("data-utc"));
      if (!d) return;
      el.textContent = d.toLocaleString(undefined, readable);
      el.title = zoneName();
    });
  }

  /* Fill datetime-local inputs with local time. */
  function fillLocalInputs(root) {
    root.querySelectorAll('input[type="datetime-local"][data-utc]').forEach(function (el) {
      var d = fromUtc(el.getAttribute("data-utc"));
      if (d) el.value = asInputValue(d);
      el.dataset.localised = "yes";
    });
  }

  /* Convert inputs back to UTC on submit. */
  function convertOnSubmit(form) {
    form.addEventListener("submit", function () {
      form.querySelectorAll('input[type="datetime-local"][data-utc]').forEach(function (el) {
        if (!el.value || el.dataset.localised !== "yes") return;
        var d = new Date(el.value); // a value with no zone parses as local
        if (isNaN(d.getTime())) return;
        el.value = d.toISOString().slice(0, 16);
      });
    });
  }

  /* Show the user's time zone name. */
  function nameTheZone(root) {
    var name = zoneName();
    if (!name) return;
    root.querySelectorAll("[data-timezone]").forEach(function (el) {
      el.textContent = name.replace(/_/g, " ");
    });
  }

  function start() {
    nameTheZone(document);
    showLocalTimes(document);
    fillLocalInputs(document);
    document.querySelectorAll("form").forEach(convertOnSubmit);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
