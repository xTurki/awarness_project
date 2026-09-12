/* Times, shown and typed in the reader's own zone.
 *
 * The platform stores naive UTC in every column, which is right: a stored
 * moment must not depend on where the person who wrote it was sitting. But a
 * browser's `datetime-local` field speaks local wall time, and nothing was
 * translating between the two, so an instructor in Sydney typing 05:25 had
 * 05:25 UTC stored, and the test opened ten hours later than they meant.
 *
 * Only the browser knows the viewer's zone, so the conversion belongs here.
 * Three jobs, and each degrades to the old behaviour with no JavaScript at all:
 * a stored moment still renders, marked UTC, and a typed one is still read as
 * UTC, which is exactly what happened before this file existed.
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

  /* A naive value out of the database has no zone on it. Without the Z a
     browser reads it as local time, which is the very mistake being fixed. */
  function fromUtc(iso) {
    if (!iso) return null;
    var stamped = /Z$|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z";
    var d = new Date(stamped);
    return isNaN(d.getTime()) ? null : d;
  }

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  /* What a datetime-local input wants: local wall time, no zone. */
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

  /* 1. Every stored moment on the page, rewritten into the reader's zone. */
  function showLocalTimes(root) {
    root.querySelectorAll("time[data-utc]").forEach(function (el) {
      var d = fromUtc(el.getAttribute("data-utc"));
      if (!d) return;
      el.textContent = d.toLocaleString(undefined, readable);
      el.title = zoneName();
    });
  }

  /* 2. Date fields open on the local equivalent of what is stored, so an
        instructor edits the time they meant rather than its UTC shadow. */
  function fillLocalInputs(root) {
    root.querySelectorAll('input[type="datetime-local"][data-utc]').forEach(function (el) {
      var d = fromUtc(el.getAttribute("data-utc"));
      if (d) el.value = asInputValue(d);
      el.dataset.localised = "yes";
    });
  }

  /* 3. And on the way out, back to UTC, because the server stores naive UTC
        and has no way of knowing which zone the typing happened in. */
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

  /* 4. And say which zone that is, so nobody has to guess whose clock a page
        is speaking in. */
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
