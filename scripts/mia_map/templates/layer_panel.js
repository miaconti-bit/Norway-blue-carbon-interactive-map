// Dynamic legend / source-panel script for the Folium overlay control.
//
// Wired in by attach_layer_panels() in build_norway_map.py: the literal
// __SOURCE_LINKS_JSON__ token is replaced server-side with a JSON object
// mapping layer name → list of {label, url, note} link entries. Everything
// else is plain JavaScript and can be edited in any JS-aware editor.

(function () {
  const sourceLinksByLayer = __SOURCE_LINKS_JSON__;
  const activeLayers = new Set();

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function nameOfInput(input) {
    const label = input.parentElement;
    if (label && label.dataset && label.dataset.fullName) return label.dataset.fullName;
    const span = label && label.querySelector('span');
    return span ? span.textContent.replace(/^\s+|\s+$/g, '') : '';
  }

  function renderPanels() {
    const legend = document.getElementById('dynamic-legend');
    const sourcePanel = document.getElementById('source-panel');
    if (!legend || !sourcePanel) return;
    const entries = Array.prototype.slice.call(legend.querySelectorAll('[data-layer]'));
    let visibleCount = 0;
    entries.forEach(function (entry) {
      const layerName = entry.getAttribute('data-layer');
      const isActive = activeLayers.has(layerName);
      const isToggleable = entry.hasAttribute('data-toggleable');
      entry.style.display = (isActive || isToggleable) ? '' : 'none';
      if (isActive || isToggleable) visibleCount += 1;
    });
    const empty = legend.querySelector('[data-empty-legend]');
    if (empty) empty.style.display = visibleCount ? 'none' : '';
    const orderedActive = Array.from(activeLayers).filter(function (name) {
      return (sourceLinksByLayer[name] || []).length > 0;
    });
    if (!orderedActive.length) {
      sourcePanel.style.display = 'none';
      sourcePanel.innerHTML = '';
      return;
    }
    sourcePanel.style.display = '';
    const blocks = orderedActive.map(function (layerName) {
      const links = sourceLinksByLayer[layerName] || [];
      if (!links.length) return '';
      const primary = links[0];
      const extras = links.slice(1);
      let html = '<div style="margin:8px 0 4px;border-top:1px solid #eee;padding-top:6px">' +
        '<div style="font-weight:700;font-size:11px;color:#0a58ca;text-transform:uppercase;letter-spacing:.02em;line-height:1.3">' + esc(layerName) + '</div>' +
        '<div style="font-size:11.5px;line-height:1.45;margin-top:3px">' +
        esc(primary.label) +
        ' <a href="' + esc(primary.url) + '" target="_blank" rel="noopener noreferrer"' +
        ' style="color:#0a58ca;text-decoration:none;font-weight:700;white-space:nowrap;margin-left:4px">(Source)</a>' +
        '</div>';
      if (primary.note) {
        html += '<div style="font-size:11px;color:#666;line-height:1.35">' + esc(primary.note) + '</div>';
      }
      if (extras.length) {
        html += '<div style="font-size:11px;color:#666;margin-top:3px">Also: ' +
          extras.map(function (link) {
            return '<a href="' + esc(link.url) + '" target="_blank" rel="noopener noreferrer"' +
              ' style="color:#0a58ca;text-decoration:none">' + esc(link.label) + '</a>';
          }).join(' &middot; ') + '</div>';
      }
      html += '</div>';
      return html;
    }).filter(Boolean).join('');
    sourcePanel.innerHTML = '<div style="font-weight:700;font-size:13px;margin-bottom:2px">Sources for active layers</div>' +
      '<div style="font-size:10.5px;color:#888;margin-bottom:4px">Click <b>(Source)</b> to open the dataset / publication.</div>' +
      blocks;
  }

  function findOverlayInputs() {
    const overlayContainer = document.querySelector('.leaflet-control-layers-overlays');
    if (!overlayContainer) return [];
    return Array.prototype.slice.call(overlayContainer.querySelectorAll('input[type="checkbox"]'));
  }

  function syncFromInputs(inputs) {
    activeLayers.clear();
    inputs.forEach(function (input) {
      if (input.checked) activeLayers.add(nameOfInput(input));
    });
  }

  function removeColocationFromControl() {
    var overlayContainer = document.querySelector('.leaflet-control-layers-overlays');
    if (!overlayContainer) return;
    var labels = Array.prototype.slice.call(overlayContainer.querySelectorAll('label'));
    labels.forEach(function (label) {
      var span = label.querySelector('span');
      var text = (label.dataset.fullName || (span ? span.textContent : '')).replace(/^\s+|\s+$/g, '');
      if (text.indexOf('Co-location: ') === 0) {
        if (label.parentNode) label.parentNode.removeChild(label);
      }
    });
  }

  function init() {
    var overlayContainer = document.querySelector('.leaflet-control-layers-overlays');
    var inputs = findOverlayInputs();
    if (!overlayContainer || !inputs.length) { setTimeout(init, 100); return; }
    inputs.forEach(function (input) {
      input.addEventListener('change', function () {
        syncFromInputs(inputs);
        renderPanels();
      });
    });
    removeColocationFromControl();
    syncFromInputs(inputs);
    renderPanels();
  }

  if (document.readyState === 'complete') {
    init();
  } else {
    window.addEventListener('load', init);
  }
})();
