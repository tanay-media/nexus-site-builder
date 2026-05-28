document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".faq-question").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var answer = btn.nextElementSibling;
      if (!answer || !answer.classList.contains("faq-answer")) return;
      var open = answer.style.display === "block";
      answer.style.display = open ? "none" : "block";
      btn.setAttribute("aria-expanded", open ? "false" : "true");
    });
  });

  var progress = document.querySelector(".arch-reading-progress");
  function updateProgress() {
    if (!progress) return;
    var scrollTop = window.scrollY || document.documentElement.scrollTop;
    var height = document.documentElement.scrollHeight - window.innerHeight;
    var pct = height > 0 ? Math.min(100, (scrollTop / height) * 100) : 0;
    progress.style.width = pct + "%";
  }
  window.addEventListener("scroll", updateProgress, { passive: true });
  updateProgress();

  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      var targetId = a.getAttribute("href");
      if (!targetId || targetId === "#") return;
      var el = document.querySelector(targetId);
      if (!el) return;
      e.preventDefault();
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  var navToggle = document.querySelector(".arch-nav-toggle");
  if (navToggle) {
    navToggle.addEventListener("click", function () {
      document.body.classList.toggle("arch-nav-mobile-open");
    });
  }

  var tocLinks = Array.from(document.querySelectorAll(".arch-toc-link"));
  function updateSpy() {
    if (!tocLinks.length) return;
    var current = null;
    tocLinks.forEach(function (link) {
      var id = (link.getAttribute("href") || "").replace(/^#/, "");
      if (!id) return;
      var section = document.getElementById(id);
      if (!section) return;
      if (section.getBoundingClientRect().top <= 140) current = link;
    });
    tocLinks.forEach(function (l) { l.classList.remove("active"); });
    if (current) current.classList.add("active");
  }
  window.addEventListener("scroll", updateSpy, { passive: true });
  updateSpy();
});
