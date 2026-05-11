"""mia_map — supporting modules for build_norway_map.py.

Modules:
  parsers   — pure parsing helpers (DMS coordinates, year, WKT points).
  popups    — HTML row/popup builders shared across layer-add functions.
  templates — static template assets (layer_panel.js).

Code that already lives at scripts/regions.py and scripts/geo_utils.py is
intentionally *not* re-exported here; those are imported directly to keep
their use sites unambiguous.
"""
