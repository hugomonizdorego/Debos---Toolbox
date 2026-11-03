"""Visual design: palettes and the application stylesheet.

The look combines soft neumorphic cards (rounded, layered shadows), a
profile-style sidebar with a gradient banner, colourful dashboard tiles,
a launcher-like app grid with a big search bar and keyboard hints, and
blue gradient pill buttons.  Colours are generated from the palettes below
so light and dark themes stay consistent; nothing relies on CSS variables,
which keeps it compatible with GTK 4.6+.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

PALETTES = {
    "light": {
        "bg": "#EDF1F8", "bg2": "#E4EAF4", "surface": "#FFFFFF", "surface2": "#F4F7FC", "surface3": "#E9EEF7",
        "border": "rgba(28, 49, 94, 0.08)", "border2": "rgba(28, 49, 94, 0.14)",
        "text": "#17203A", "muted": "#66718C", "faint": "#98A2B8",
        "primary": "#3B7BFF", "primary2": "#2350E6", "primary_soft": "#E6EEFF", "on_primary": "#FFFFFF",
        "success": "#1FAF6A", "success_soft": "#DDF6EA", "warning": "#F29E2E", "warning_soft": "#FFF1DC",
        "danger": "#EE4A5C", "danger_soft": "#FFE4E8", "info": "#20A0E6", "info_soft": "#DFF3FF",
        "shadow": "rgba(34, 64, 128, 0.10)", "shadow2": "rgba(34, 64, 128, 0.05)", "shine": "rgba(255, 255, 255, 0.95)",
        "neu_dark": "rgba(158, 173, 199, 0.42)", "console_bg": "#0E1424",
    },
    "dark": {
        "bg": "#0C1220", "bg2": "#0F1628", "surface": "#141C2F", "surface2": "#1A2339", "surface3": "#212C46",
        "border": "rgba(255, 255, 255, 0.06)", "border2": "rgba(255, 255, 255, 0.11)",
        "text": "#E6EBF6", "muted": "#94A0BB", "faint": "#68758F",
        "primary": "#5B8DFF", "primary2": "#3A63F2", "primary_soft": "rgba(91, 141, 255, 0.16)", "on_primary": "#FFFFFF",
        "success": "#2FCB81", "success_soft": "rgba(47, 203, 129, 0.15)", "warning": "#F5AE45", "warning_soft": "rgba(245, 174, 69, 0.15)",
        "danger": "#FF5F70", "danger_soft": "rgba(255, 95, 112, 0.15)", "info": "#45B8F5", "info_soft": "rgba(69, 184, 245, 0.15)",
        "shadow": "rgba(0, 0, 0, 0.38)", "shadow2": "rgba(0, 0, 0, 0.22)", "shine": "rgba(255, 255, 255, 0.03)",
        "neu_dark": "rgba(0, 0, 0, 0.45)", "console_bg": "#080C16",
    },
}

# Colour pairs (light, dark shade) for dashboard tiles and app icons.
TILE_COLORS = {
    "orange": ("#FFA64D", "#F47F2A"), "green": ("#3DD68C", "#1EAE69"), "pink": ("#FF4F8B", "#E0266A"),
    "purple": ("#8A63E8", "#6A43CF"), "cyan": ("#22C3E6", "#0C9DC4"), "lime": ("#93CE4E", "#6DAE2E"),
    "violet": ("#B65BE0", "#9037C4"), "red": ("#FF6363", "#E23D3D"), "blue": ("#4D8DFF", "#2557E8"),
    "teal": ("#2CC6B0", "#139C88"), "amber": ("#FFC53D", "#F0A400"), "slate": ("#7C8BA8", "#5A6886"),
}

CSS = """
window.debos { background-color: @bg@; color: @text@; }
window.debos .content-bg { background-color: @bg@; }

/* header bar */
window.debos headerbar { background: @surface@; color: @text@; box-shadow: none; border-bottom: 1px solid @border@;
  min-height: 58px; padding: 0 10px; }
window.debos headerbar button { min-height: 34px; min-width: 34px; border-radius: 12px; }

/* search (launcher style) */
.search-wrap { background: @surface2@; border-radius: 16px; border: 1px solid @border@; padding: 0 6px 0 12px;
  min-height: 40px; }
.search-wrap:focus-within { border-color: @primary@; box-shadow: 0 0 0 3px @primary_soft@; }
window.debos .search-wrap entry, window.debos .search-wrap entry:focus-within, .search-wrap text { background: transparent;
  border: none; box-shadow: none; min-height: 38px; color: @text@; outline: none; }
.search-wrap image.search-icon { color: @muted@; }
.kbd { border: 1px solid @border2@; border-radius: 7px; padding: 1px 7px; font-size: 0.78em; color: @muted@;
  background: @surface@; font-weight: 600; }

/* sidebar */
.sidebar { background: @surface@; border-right: 1px solid @border@; }
.profile { margin: 12px; border-radius: 22px; padding: 18px 16px 16px 16px;
  background-image: linear-gradient(118deg, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.0) 38%, rgba(255,255,255,0.10) 39%, rgba(255,255,255,0.0) 62%),
                    linear-gradient(135deg, #3B7BFF 0%, #5B4BF2 100%);
  color: #FFFFFF; box-shadow: 0 12px 26px rgba(59, 91, 255, 0.30); }
.profile .avatar { background: rgba(255,255,255,0.22); border-radius: 999px; min-width: 52px; min-height: 52px;
  font-weight: 800; font-size: 1.35em; color: #FFFFFF; border: 2px solid rgba(255,255,255,0.55); }
.profile .name { font-weight: 800; font-size: 1.08em; color: #FFFFFF; }
.profile .sub { color: rgba(255,255,255,0.82); font-size: 0.86em; }
.profile .badge-pill { background: rgba(255,255,255,0.20); color: #FFFFFF; border-radius: 999px; padding: 2px 10px;
  font-size: 0.80em; font-weight: 700; }
.nav-section { color: @faint@; font-size: 0.74em; font-weight: 800; letter-spacing: 1px; margin: 14px 22px 4px 22px; }
.nav-row { border-radius: 14px; margin: 1px 10px; padding: 9px 12px; color: @muted@; background: transparent;
  transition: all 120ms ease-out; }
.nav-row:hover { background: @surface2@; color: @text@; }
.nav-row image { color: @muted@; }
.nav-row.active { background-image: linear-gradient(135deg, @primary@, @primary2@); color: @on_primary@;
  box-shadow: 0 8px 18px rgba(59, 100, 255, 0.28); }
.nav-row.active image, .nav-row.active label { color: @on_primary@; }
.nav-row label { font-weight: 600; }
.nav-count { background: @danger@; color: #FFFFFF; border-radius: 999px; padding: 0 7px; font-size: 0.75em; font-weight: 800; }
.sidebar-footer { color: @faint@; font-size: 0.80em; margin: 10px 18px 14px 18px; }

/* page */
.page { padding: 22px 28px 28px 28px; }
.page-title { font-size: 1.75em; font-weight: 800; color: @text@; }
.page-subtitle { color: @muted@; }
.section-title { font-size: 1.05em; font-weight: 800; color: @text@; margin-top: 6px; }
.section-sub { color: @muted@; font-size: 0.9em; }

/* cards: soft neumorphic surfaces */
.card { background: @surface@; border-radius: 22px; border: 1px solid @border@; padding: 18px;
  box-shadow: 0 10px 28px @shadow@, 0 2px 6px @shadow2@; }
.card.flat { box-shadow: none; }
.card.soft { background: @surface2@; box-shadow: none; }
.card-title { font-weight: 800; font-size: 1.06em; color: @text@; }
.card-sub { color: @muted@; font-size: 0.9em; }
.neu { background: @surface@; border-radius: 22px; box-shadow: 8px 8px 20px @neu_dark@, -8px -8px 20px @shine@; }

/* coloured stat tiles */
.tile { border-radius: 20px; color: #FFFFFF; min-height: 92px; box-shadow: 0 10px 24px @shadow@; }
.tile .tile-icon { background: rgba(0, 0, 0, 0.13); border-radius: 20px 0 0 20px; min-width: 74px; }
.tile .tile-icon image { color: #FFFFFF; }
.tile .tile-title { font-size: 0.80em; font-weight: 800; letter-spacing: 0.6px; color: rgba(255,255,255,0.92); }
.tile .tile-value { font-size: 1.75em; font-weight: 800; color: #FFFFFF; }
.tile .tile-note { font-size: 0.78em; color: rgba(255,255,255,0.85); }
@TILES@

/* buttons */
button.pill { border-radius: 14px; padding: 8px 18px; font-weight: 700; border: none; box-shadow: none;
  background-image: none; background-color: @surface3@; color: @text@; transition: all 120ms ease-out; }
button.pill:hover { background-color: @border2@; }
button.pill.primary { background-image: linear-gradient(135deg, @primary@, @primary2@); color: @on_primary@;
  box-shadow: 0 8px 18px rgba(59, 100, 255, 0.30); }
button.pill.primary:hover { box-shadow: 0 10px 24px rgba(59, 100, 255, 0.42); }
button.pill.danger { background-image: linear-gradient(135deg, #FF6B7B, #E23650); color: #FFFFFF;
  box-shadow: 0 8px 18px rgba(226, 54, 80, 0.28); }
button.pill.success { background-image: linear-gradient(135deg, #3DD68C, #18A862); color: #FFFFFF;
  box-shadow: 0 8px 18px rgba(24, 168, 98, 0.26); }
button.pill.ghost { background: transparent; color: @primary@; }
button.pill.ghost:hover { background: @primary_soft@; }
button.pill:disabled { opacity: 0.45; box-shadow: none; }
button.pill.small { padding: 4px 12px; font-size: 0.9em; border-radius: 11px; }
button.icon-btn { border-radius: 12px; background: @surface2@; color: @text@; border: none; box-shadow: none;
  background-image: none; min-width: 36px; min-height: 36px; padding: 0; }
button.icon-btn:hover { background: @surface3@; }
button.icon-btn.active { background-image: linear-gradient(135deg, @primary@, @primary2@); color: #FFFFFF; }
.circle-action { border-radius: 999px; min-width: 56px; min-height: 56px; padding: 0; border: none;
  box-shadow: 0 10px 22px @shadow@; color: #FFFFFF; }
.circle-label { color: @muted@; font-size: 0.86em; font-weight: 600; }

/* chips */
button.chip, togglebutton.chip { border-radius: 999px; padding: 5px 15px; background: @surface@; color: @muted@;
  border: 1px solid @border@; box-shadow: none; background-image: none; font-weight: 700; }
button.chip:hover { color: @text@; background: @surface2@; }
button.chip:checked, togglebutton.chip:checked { background-image: linear-gradient(135deg, @primary@, @primary2@);
  color: #FFFFFF; border-color: transparent; }

/* badges */
.badge { border-radius: 999px; padding: 1px 9px; font-size: 0.76em; font-weight: 800; }
.badge.ok { background: @success_soft@; color: @success@; }
.badge.warn { background: @warning_soft@; color: @warning@; }
.badge.err { background: @danger_soft@; color: @danger@; }
.badge.info { background: @info_soft@; color: @info@; }
.badge.primary { background: @primary_soft@; color: @primary@; }
.badge.muted { background: @surface3@; color: @muted@; }

/* rows inside cards */
.row { padding: 10px 4px; border-bottom: 1px solid @border@; }
.row.last { border-bottom: none; }
.row-title { font-weight: 700; color: @text@; }
.row-sub { color: @muted@; font-size: 0.88em; }
.mono { font-family: monospace; font-size: 0.92em; }
.dim { color: @muted@; }
.ok-text { color: @success@; } .warn-text { color: @warning@; } .err-text { color: @danger@; } .accent-text { color: @primary@; }

/* severity markers */
.sev { border-radius: 14px; min-width: 40px; min-height: 40px; }
.sev.critical { background: @danger_soft@; color: @danger@; }
.sev.warning { background: @warning_soft@; color: @warning@; }
.sev.info { background: @info_soft@; color: @info@; }
.sev.tip { background: @success_soft@; color: @success@; }

/* app grid (launcher) */
flowboxchild { padding: 0; border-radius: 22px; background: transparent; }
flowboxchild:focus-visible { outline: 2px solid @primary@; outline-offset: 2px; }
.app-tile { background: @surface@; border-radius: 22px; border: 1px solid @border@; padding: 16px 12px 12px 12px;
  box-shadow: 0 8px 20px @shadow2@; transition: all 140ms ease-out; }
.app-tile:hover { box-shadow: 0 14px 30px @shadow@; border-color: @border2@; }
.app-tile.selected { border: 2px solid @primary@; box-shadow: 0 0 0 4px @primary_soft@, 0 14px 30px @shadow@; }
.app-tile .app-name { font-weight: 800; color: @text@; }
.app-tile .app-desc { color: @muted@; font-size: 0.82em; }
.app-icon { border-radius: 18px; min-width: 60px; min-height: 60px; color: #FFFFFF;
  box-shadow: inset 0 -3px 0 rgba(0,0,0,0.10), 0 8px 18px @shadow2@; }
.app-check { background-image: linear-gradient(135deg, @primary@, @primary2@); color: #FFFFFF; border-radius: 999px;
  min-width: 24px; min-height: 24px; box-shadow: 0 4px 10px rgba(59, 100, 255, 0.35); }
.selection-bar { background: @surface@; border-radius: 18px; padding: 10px 14px; border: 1px solid @border@;
  box-shadow: 0 -6px 24px @shadow@; }

/* inputs */
window.debos entry { border-radius: 12px; background: @surface2@; color: @text@; border: 1px solid @border@;
  box-shadow: none; min-height: 36px; }
window.debos entry:focus-within { border-color: @primary@; box-shadow: 0 0 0 3px @primary_soft@; }
window.debos textview, window.debos textview text { background: @surface2@; color: @text@; }
.editor { border-radius: 16px; border: 1px solid @border@; }
window.debos switch { background: @surface3@; border-radius: 999px; border: none; min-height: 26px; }
window.debos switch:checked { background-image: linear-gradient(135deg, @primary@, @primary2@); }
window.debos switch slider { background: #FFFFFF; border-radius: 999px; box-shadow: 0 2px 6px rgba(0,0,0,0.22); min-width: 22px; min-height: 22px; border: none; }
window.debos checkbutton check, window.debos checkbutton radio { border: 1.5px solid @border2@; background: @surface@; }
window.debos checkbutton check:checked, window.debos checkbutton radio:checked { background-color: @primary@; border-color: @primary@; color: #FFFFFF; }
window.debos dropdown > button, window.debos dropdown button.toggle { border-radius: 12px; background: @surface2@; border: 1px solid @border@; box-shadow: none; background-image: none; color: @text@; }
window.debos popover contents, window.debos popover.menu contents { background: @surface@; color: @text@; border-radius: 16px; border: 1px solid @border@; box-shadow: 0 12px 30px @shadow@; }
window.debos popover listview, window.debos popover list { background: transparent; color: @text@; }
window.debos progressbar trough { background: @surface3@; border-radius: 999px; min-height: 8px; border: none; }
window.debos progressbar progress { background-image: linear-gradient(90deg, @primary@, #7A5CFF); border-radius: 999px; min-height: 8px; min-width: 8px; border: none; }
window.debos scrollbar slider { background-color: @border2@; border-radius: 999px; min-width: 6px; }
window.debos scrollbar { background: transparent; border: none; }

/* segmented tabs */
.segmented { background: @surface2@; border-radius: 15px; padding: 4px; border: 1px solid @border@; }
.segmented button { border-radius: 11px; padding: 6px 16px; background: transparent; border: none; box-shadow: none;
  background-image: none; color: @muted@; font-weight: 700; }
.segmented button:checked { background: @surface@; color: @primary@; box-shadow: 0 4px 12px @shadow@; }

/* console drawer */
.console { background: @console_bg@; border-top-left-radius: 20px; border-top-right-radius: 20px;
  box-shadow: 0 -10px 30px @shadow@; }
.console-head { padding: 8px 12px 6px 16px; color: #DCE4F5; }
.console-head label { color: #DCE4F5; }
.console-head .console-title { font-weight: 800; }
.console-head button { background: rgba(255,255,255,0.07); color: #DCE4F5; border: none; border-radius: 10px;
  box-shadow: none; background-image: none; min-height: 30px; padding: 0 10px; }
.console-head button:hover { background: rgba(255,255,255,0.14); }
window.debos .console textview, window.debos .console textview text { background: @console_bg@; color: #D7E0F2; font-family: monospace; }
.console-head .badge.muted { background: rgba(255,255,255,0.10); color: #DCE4F5; }
.console-head .badge.info { background: rgba(69,184,245,0.22); color: #9ADCFF; }
.console-head .badge.ok { background: rgba(47,203,129,0.22); color: #8FF0BE; }
.console-head .badge.err { background: rgba(255,95,112,0.24); color: #FFB3BC; }
.chips-row button.chip { margin-right: 6px; }
.queue-chip { background: rgba(255,255,255,0.10); color: #DCE4F5; border-radius: 999px; padding: 1px 9px; font-size: 0.8em; }

/* hint bar */
.hintbar { background: @surface@; border-top: 1px solid @border@; padding: 5px 16px; color: @muted@; font-size: 0.86em; }

/* toasts */
.toast { background: #17203A; color: #FFFFFF; border-radius: 16px; padding: 10px 16px; margin: 18px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.25); }
.toast label { color: #FFFFFF; }
.toast.ok { background-image: linear-gradient(135deg, #22B573, #12925A); }
.toast.err { background-image: linear-gradient(135deg, #F0566A, #C9304A); }
.toast button { color: #FFFFFF; background: rgba(255,255,255,0.16); border: none; border-radius: 10px; box-shadow: none; background-image: none; }

/* dialogs */
window.debos-dialog { background-color: @surface@; color: @text@; border-radius: 22px; }
window.debos-dialog .dialog-title { font-size: 1.25em; font-weight: 800; }
window.debos-dialog .dialog-body { color: @muted@; }
window.debos-dialog textview, window.debos-dialog textview text { background: @surface2@; color: @text@; }

/* misc */
.empty { color: @muted@; padding: 30px; }
.empty .empty-title { font-weight: 800; font-size: 1.1em; color: @text@; }
.big-number { font-size: 2.1em; font-weight: 800; color: @text@; }
.kv-key { color: @muted@; } .kv-val { color: @text@; font-weight: 600; }
.status-dot { border-radius: 999px; min-width: 9px; min-height: 9px; }
.status-dot.ok { background: @success@; } .status-dot.warn { background: @warning@; } .status-dot.err { background: @danger@; } .status-dot.info { background: @info@; }
separator { background: @border@; min-height: 1px; }
"""


def _tiles_css():
    parts = []
    for name, (light, dark) in TILE_COLORS.items():
        parts.append(f".tile.{name}, .app-icon.{name}, .circle-action.{name} {{ background-image: linear-gradient(135deg, {light}, {dark}); }}")
    return "\n".join(parts)


def stylesheet(mode):
    pal = PALETTES["dark" if mode == "dark" else "light"]
    css = CSS.replace("@TILES@", _tiles_css())
    # longest keys first so @primary_soft@ is not caught by @primary@
    for key in sorted(pal, key=len, reverse=True):
        css = css.replace(f"@{key}@", pal[key])
    return css


_provider = None


def system_prefers_dark():
    """Ask the desktop portal (and GNOME settings as fallback) for the colour scheme."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                            "org.freedesktop.portal.Settings", "Read",
                            GLib.Variant("(ss)", ("org.freedesktop.appearance", "color-scheme")),
                            None, Gio.DBusCallFlags.NONE, 400, None)
        value = res.unpack()[0]
        while isinstance(value, GLib.Variant):
            value = value.unpack()
        return value == 1
    except Exception:
        pass
    try:
        src = Gio.SettingsSchemaSource.get_default()
        if src and src.lookup("org.gnome.desktop.interface", True):
            s = Gio.Settings.new("org.gnome.desktop.interface")
            if "color-scheme" in s.list_keys():
                return s.get_string("color-scheme") == "prefer-dark"
            return s.get_string("gtk-theme").lower().endswith("dark")
    except Exception:
        pass
    return False


def resolve_mode(setting):
    if setting in ("light", "dark"):
        return setting
    return "dark" if system_prefers_dark() else "light"


def apply(mode):
    """Install (or replace) the application stylesheet for 'light' or 'dark'."""
    global _provider
    display = Gdk.Display.get_default()
    settings = Gtk.Settings.get_default()
    if settings is not None:
        try:
            settings.set_property("gtk-application-prefer-dark-theme", mode == "dark")
        except TypeError:
            pass
    if _provider is not None:
        Gtk.StyleContext.remove_provider_for_display(display, _provider)
    provider = Gtk.CssProvider()
    css = stylesheet(mode)
    if hasattr(provider, "load_from_string"):          # GTK >= 4.12
        provider.load_from_string(css)
    else:
        try:
            provider.load_from_data(css.encode("utf-8"))
        except TypeError:                               # older PyGObject signature
            provider.load_from_data(css, -1)
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    _provider = provider


def use_adwaita_icons():
    """Pin the app's own icon theme to Adwaita so symbolic icons always exist.
    This only affects this application, not the desktop."""
    import os
    settings = Gtk.Settings.get_default()
    if settings is not None and os.path.exists("/usr/share/icons/Adwaita/index.theme"):
        settings.set_property("gtk-icon-theme-name", "Adwaita")
