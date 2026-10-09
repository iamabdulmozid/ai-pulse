/* Shared navigation and native dialog keep the workspace usable without Alpine. */
(function () {
  var navTrigger = document.querySelector('.menu-toggle');
  window.kpToggleNav = function (open) {
    if (open === undefined) open = !document.body.classList.contains('nav-open');
    document.body.classList.toggle('nav-open', open);
    if (navTrigger) navTrigger.setAttribute('aria-expanded', String(open));
    var backdrop = document.querySelector('.nav-backdrop');
    if (backdrop) backdrop.hidden = !open;
    if (open) document.querySelector('.nav-item.active, .nav-item').focus();
    else if (navTrigger) navTrigger.focus();
  };
  var dialog = document.getElementById('assistant-dialog');
  window.kpOpenAssistant = function (question) {
    if (!dialog) return;
    if (document.body.classList.contains('nav-open')) window.kpToggleNav(false);
    if (!dialog.open) dialog.showModal();
    document.getElementById('panel-question').focus();
    if (question) window.kpPanelAsk(question);
  };
  window.kpPanelAsk = function (question) {
    if (!(question || '').trim()) return;
    var container = document.getElementById('panel-result');
    var welcome = container.querySelector('.panel-welcome');
    if (welcome) welcome.hidden = true;
    window.kpAsk(question, container);
  };
  window.addEventListener('kp-cmdk', function () { window.kpOpenAssistant(); });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && document.body.classList.contains('nav-open')) window.kpToggleNav(false);
    if (event.key === 'Tab' && document.body.classList.contains('nav-open')) {
      var items = Array.from(document.querySelectorAll('.side a, .side button'));
      var first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {event.preventDefault();last.focus();}
      else if (!event.shiftKey && document.activeElement === last) {event.preventDefault();first.focus();}
    }
  });
  if (dialog) dialog.addEventListener('click', function (event) {
    if (event.target === dialog && event.clientX < dialog.getBoundingClientRect().left) dialog.close();
  });
  document.querySelectorAll('.nav-item.active').forEach(function (link) { link.setAttribute('aria-current', 'page'); });
  document.querySelectorAll('.kbd').forEach(function (key) { key.textContent = /Mac/.test(navigator.platform) ? '⌘ K' : 'Ctrl K'; });
  // Confine wide data tables to their cards, including HTMX-loaded content.
  function wrapTables(root) {
    root.querySelectorAll('.card > .tbl, .card > div > .tbl').forEach(function (table) {
      if (table.parentElement.classList.contains('table-scroll') || table.parentElement.style.overflowX === 'auto') return;
      var wrap = document.createElement('div'); wrap.className = 'table-scroll';
      table.before(wrap); wrap.appendChild(table);
    });
  }
  wrapTables(document);
  document.body.addEventListener('htmx:afterSwap', function (event) {
    wrapTables(event.target);
    if (event.target.id === 'po-results') {
      var form = document.getElementById('po-filters'), link = document.getElementById('po-export');
      if (form && link) {
        var params = new URLSearchParams(new FormData(form));
        document.querySelectorAll('#po-results input[name=band]').forEach(function (input) {params.append('band',input.value);});
        link.href = link.href.split('?')[0] + '?' + params.toString();
      }
    }
  });
  document.body.addEventListener('htmx:responseError', function () {
    var status = document.getElementById('request-error');
    if (!status) {status = document.createElement('div');status.id = 'request-error';status.className = 'login-error';status.setAttribute('role', 'alert');document.querySelector('main').prepend(status);}
    status.textContent = 'This update could not be completed. Please try again or refresh the page.';
  });
})();
