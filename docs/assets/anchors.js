// Adds a hover-revealed "chain link" anchor to each section heading, so any
// heading can be linked directly. Runs deferred (DOM is already parsed).
(function () {
  var ICON = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">' +
    '<path fill="currentColor" d="M7.775 3.275a.75.75 0 0 0 1.06 1.06l1.25-1.25a2 2 0 1 1 2.83 2.83' +
    'l-2.5 2.5a2 2 0 0 1-2.83 0 .75.75 0 0 0-1.06 1.06 3.5 3.5 0 0 0 4.95 0l2.5-2.5a3.5 3.5 0 0 0-4.95-4.95' +
    'l-1.25 1.25Zm-4.69 9.64a2 2 0 0 1 0-2.83l2.5-2.5a2 2 0 0 1 2.83 0 .75.75 0 0 0 1.06-1.06 3.5 3.5 0 0 0-4.95 0' +
    'l-2.5 2.5a3.5 3.5 0 0 0 4.95 4.95l1.25-1.25a.75.75 0 0 0-1.06-1.06l-1.25 1.25a2 2 0 0 1-2.83 0Z"></path></svg>';

  function slugify(text) {
    return text.trim().toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-+|-+$/g, '') || 'section';
  }

  var headings = document.querySelectorAll('.post-content h2, .post-content h3, .post-content h4');
  headings.forEach(function (h) {
    if (!h.id) {
      var base = slugify(h.textContent), id = base, n = 1;
      while (document.getElementById(id)) { id = base + '-' + (++n); }
      h.id = id;
    }
    var a = document.createElement('a');
    a.className = 'heading-anchor';
    a.href = '#' + h.id;
    a.setAttribute('aria-label', 'Copy link to this section');
    a.innerHTML = ICON;
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var url = location.origin + location.pathname + '#' + h.id;
      copy(url).then(function () { flash(a); });
    });
    h.appendChild(a);
  });

  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve) {
      var t = document.createElement('textarea');
      t.value = text;
      t.setAttribute('readonly', '');
      t.style.position = 'absolute';
      t.style.left = '-9999px';
      document.body.appendChild(t);
      t.select();
      try { document.execCommand('copy'); } catch (err) { /* ignore */ }
      document.body.removeChild(t);
      resolve();
    });
  }

  function flash(a) {
    a.classList.add('is-copied');
    setTimeout(function () { a.classList.remove('is-copied'); }, 1100);
  }
})();
