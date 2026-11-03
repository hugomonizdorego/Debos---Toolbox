"""Reusable GTK 4 widgets for the Debos design (works on GTK 4.6 and newer)."""

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from .i18n import _  # noqa: E402
from .theme import TILE_COLORS  # noqa: E402

_FALLBACK = "application-x-executable-symbolic"


def has_icon(name):
    display = Gdk.Display.get_default()
    return bool(name) and display is not None and Gtk.IconTheme.get_for_display(display).has_icon(name)


def icon(names, size=16, css=None):
    """Gtk.Image for the first available icon name in names."""
    if isinstance(names, str):
        names = [names]
    chosen = next((n for n in names if has_icon(n)), None) or next((n for n in names if n), _FALLBACK)
    img = Gtk.Image.new_from_icon_name(chosen)
    img.set_pixel_size(size)
    if css:
        for c in css.split():
            img.add_css_class(c)
    return img


def label(text="", css=None, wrap=False, xalign=0.0, ellipsize=False, selectable=False, max_chars=None, markup=False):
    lbl = Gtk.Label()
    if markup:
        lbl.set_markup(text)
    else:
        lbl.set_text(text)
    lbl.set_xalign(xalign)
    if wrap:
        lbl.set_wrap(True)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if ellipsize:
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
    if max_chars:
        lbl.set_max_width_chars(max_chars)
    if selectable:
        lbl.set_selectable(True)
    for c in (css or "").split():
        lbl.add_css_class(c)
    return lbl


def hbox(spacing=8, css=None, *children):
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
    for c in (css or "").split():
        box.add_css_class(c)
    for child in children:
        box.append(child)
    return box


def vbox(spacing=8, css=None, *children):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    for c in (css or "").split():
        box.add_css_class(c)
    for child in children:
        box.append(child)
    return box


def placeholder(entry, text):
    """Set placeholder text on Gtk.Entry / Gtk.SearchEntry (SearchEntry gained the method only in GTK 4.10)."""
    if hasattr(entry, "set_placeholder_text"):
        entry.set_placeholder_text(text)
    else:
        entry.set_property("placeholder-text", text)


def search_entry(text):
    entry = Gtk.SearchEntry()
    placeholder(entry, text)
    return entry


def spacer():
    s = Gtk.Box()
    s.set_hexpand(True)
    return s


def clear(container):
    child = container.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        container.remove(child)
        child = nxt


def button(text="", icon_name=None, kind="", on_click=None, tooltip=None, small=False):
    btn = Gtk.Button()
    btn.add_css_class("pill")
    for k in kind.split():
        btn.add_css_class(k)
    if small:
        btn.add_css_class("small")
    if icon_name and text:
        box = hbox(6)
        box.append(icon(icon_name, 16))
        box.append(label(text))
        btn.set_child(box)
    elif icon_name:
        btn.set_child(icon(icon_name, 16))
    else:
        btn.set_label(text)
    if tooltip:
        btn.set_tooltip_text(tooltip)
    if on_click:
        btn.connect("clicked", lambda *_a: on_click())
    return btn


def icon_button(icon_name, tooltip, on_click=None, css="icon-btn"):
    btn = Gtk.Button()
    for c in css.split():
        btn.add_css_class(c)
    btn.set_child(icon(icon_name, 16))
    btn.set_tooltip_text(tooltip)
    if on_click:
        btn.connect("clicked", lambda *_a: on_click())
    return btn


def badge(text, kind="muted"):
    return label(text, f"badge {kind}")


class Card(Gtk.Box):
    def __init__(self, title=None, subtitle=None, header_extra=None, css="card", spacing=10):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        for c in css.split():
            self.add_css_class(c)
        if title or header_extra:
            head = hbox(10)
            texts = vbox(2)
            if title:
                texts.append(label(title, "card-title", wrap=True))
            if subtitle:
                texts.append(label(subtitle, "card-sub", wrap=True))
            texts.set_hexpand(True)
            head.append(texts)
            if header_extra is not None:
                if isinstance(header_extra, (list, tuple)):
                    for w in header_extra:
                        w.set_valign(Gtk.Align.CENTER)
                        head.append(w)
                else:
                    header_extra.set_valign(Gtk.Align.CENTER)
                    head.append(header_extra)
            self.append(head)
        self.body = vbox(6)
        self.append(self.body)

    def add(self, widget):
        self.body.append(widget)
        return widget


class Tile(Gtk.Box):
    """Colourful stat tile with a darker icon block (dashboard)."""

    def __init__(self, color, icon_name, title, value="…", note="", on_click=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add_css_class("tile")
        self.add_css_class(color)
        block = Gtk.Box()
        block.add_css_class("tile-icon")
        block.set_hexpand(False)
        ic = icon(icon_name, 30)
        ic.set_hexpand(True)
        ic.set_vexpand(True)
        ic.set_halign(Gtk.Align.CENTER)
        ic.set_valign(Gtk.Align.CENTER)
        block.append(ic)
        self.append(block)
        texts = vbox(1)
        texts.set_margin_start(14)
        texts.set_margin_end(12)
        texts.set_valign(Gtk.Align.CENTER)
        texts.set_hexpand(True)
        self.title_lbl = label(title.upper(), "tile-title", ellipsize=True)
        self.value_lbl = label(value, "tile-value", ellipsize=True)
        self.note_lbl = label(note, "tile-note", ellipsize=True)
        texts.append(self.title_lbl)
        texts.append(self.value_lbl)
        texts.append(self.note_lbl)
        self.append(texts)
        if on_click:
            self.set_cursor_from_name("pointer") if hasattr(self, "set_cursor_from_name") else None
            click = Gtk.GestureClick()
            click.connect("released", lambda *_a: on_click())
            self.add_controller(click)

    def set(self, value, note=None):
        self.value_lbl.set_text(str(value))
        if note is not None:
            self.note_lbl.set_text(note)


def _hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


class Donut(Gtk.DrawingArea):
    """Neumorphic progress ring with a centred percentage."""

    def __init__(self, size=132, color="blue", value=0.0, center_text=None, track="#E4EAF4", text_color="#17203A"):
        super().__init__()
        self.set_content_width(size)
        self.set_content_height(size)
        self.value = value
        self.color = color
        self.center_text = center_text
        self.track = track
        self.text_color = text_color
        self.set_draw_func(self._draw)

    def set_value(self, value, center_text=None, color=None):
        self.value = max(0.0, min(100.0, float(value)))
        self.center_text = center_text
        if color:
            self.color = color
        self.queue_draw()

    def _draw(self, _area, cr, width, height):
        size = min(width, height)
        cx, cy = width / 2, height / 2
        line = size * 0.11
        radius = size / 2 - line / 2 - 3
        cr.set_line_width(line)
        cr.set_line_cap(1)  # round
        cr.set_source_rgb(*_hex_to_rgb(self.track))
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.stroke()
        light, dark = TILE_COLORS.get(self.color, TILE_COLORS["blue"])
        try:
            import cairo
            grad = cairo.LinearGradient(0, 0, width, height)
            grad.add_color_stop_rgb(0, *_hex_to_rgb(light))
            grad.add_color_stop_rgb(1, *_hex_to_rgb(dark))
            cr.set_source(grad)
        except Exception:
            cr.set_source_rgb(*_hex_to_rgb(light))
        if self.value > 0:
            start = -math.pi / 2
            cr.arc(cx, cy, radius, start, start + 2 * math.pi * self.value / 100.0)
            cr.stroke()
        text = self.center_text if self.center_text is not None else f"{self.value:.0f}%"
        cr.set_source_rgb(*_hex_to_rgb(self.text_color))
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(size * 0.18)
        ext = cr.text_extents(text)
        cr.move_to(cx - ext.width / 2 - ext.x_bearing, cy - ext.height / 2 - ext.y_bearing)
        cr.show_text(text)


class LineChart(Gtk.DrawingArea):
    """Smooth area chart (CPU history) in the style of the reference designs."""

    def __init__(self, height=110, color="blue", maximum=100.0, grid="#E4EAF4"):
        super().__init__()
        self.set_content_height(height)
        self.set_hexpand(True)
        self.points = []
        self.color = color
        self.maximum = maximum
        self.grid = grid
        self.set_draw_func(self._draw)

    def push(self, value, keep=60):
        self.points.append(float(value))
        self.points = self.points[-keep:]
        self.queue_draw()

    def _draw(self, _area, cr, width, height):
        pad = 6
        cr.set_line_width(1)
        cr.set_source_rgb(*_hex_to_rgb(self.grid))
        for i in range(1, 4):
            y = pad + (height - 2 * pad) * i / 4
            cr.move_to(pad, y)
            cr.line_to(width - pad, y)
        cr.stroke()
        pts = self.points
        if len(pts) < 2:
            return
        step = (width - 2 * pad) / (60 - 1)
        start_x = width - pad - step * (len(pts) - 1)
        coords = [(start_x + i * step, height - pad - (height - 2 * pad) * min(v, self.maximum) / self.maximum)
                  for i, v in enumerate(pts)]
        light, dark = TILE_COLORS.get(self.color, TILE_COLORS["blue"])

        def path():
            cr.move_to(*coords[0])
            for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
                mx = (x0 + x1) / 2
                cr.curve_to(mx, y0, mx, y1, x1, y1)

        try:
            import cairo
            path()
            cr.line_to(coords[-1][0], height - pad)
            cr.line_to(coords[0][0], height - pad)
            cr.close_path()
            grad = cairo.LinearGradient(0, 0, 0, height)
            r, g, b = _hex_to_rgb(light)
            grad.add_color_stop_rgba(0, r, g, b, 0.35)
            grad.add_color_stop_rgba(1, r, g, b, 0.02)
            cr.set_source(grad)
            cr.fill()
        except Exception:
            pass
        path()
        cr.set_line_width(2.6)
        cr.set_source_rgb(*_hex_to_rgb(dark))
        cr.stroke()
        x, y = coords[-1]
        cr.set_source_rgb(*_hex_to_rgb(dark))
        cr.arc(x, y, 4.5, 0, 2 * math.pi)
        cr.fill()


class AppIcon(Gtk.Box):
    """Rounded coloured square with a symbolic glyph, or the real app icon if available."""

    def __init__(self, color="blue", glyph="application-x-executable-symbolic", real_icons=(), image_file=None, size=60):
        super().__init__()
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        real = next((n for n in real_icons if n and has_icon(n)), None)
        if image_file:
            pic = Gtk.Picture.new_for_filename(image_file)
            pic.set_size_request(size, size)
            if hasattr(pic, "set_content_fit"):
                pic.set_content_fit(Gtk.ContentFit.CONTAIN)
            self.append(pic)
        elif real:
            self.append(icon(real, size))
        else:
            self.add_css_class("app-icon")
            self.add_css_class(color)
            self.set_size_request(size, size)
            self.set_hexpand(False)
            self.set_vexpand(False)
            g = icon(glyph, int(size * 0.46))
            g.set_hexpand(True)
            g.set_vexpand(True)
            g.set_halign(Gtk.Align.CENTER)
            g.set_valign(Gtk.Align.CENTER)
            self.append(g)


def circle_action(color, icon_name, text, on_click):
    box = vbox(6)
    box.set_halign(Gtk.Align.CENTER)
    btn = Gtk.Button()
    btn.add_css_class("circle-action")
    btn.add_css_class(color)
    btn.set_child(icon(icon_name, 22))
    btn.set_halign(Gtk.Align.CENTER)
    btn.set_tooltip_text(text)
    btn.connect("clicked", lambda *_a: on_click())
    box.append(btn)
    box.append(label(text, "circle-label", xalign=0.5))
    return box


class Segmented(Gtk.Box):
    """Segmented control built from grouped toggle buttons."""

    def __init__(self, options, on_change, active=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.add_css_class("segmented")
        self.buttons = {}
        group = None
        for key, text in options:
            b = Gtk.ToggleButton(label=text)
            if group is not None:
                b.set_group(group)
            else:
                group = b
            self.buttons[key] = b
            self.append(b)
        first = active if active in self.buttons else options[0][0]
        self.buttons[first].set_active(True)
        # connect after the initial selection so construction does not fire callbacks
        for key, b in self.buttons.items():
            b.connect("toggled", self._toggled, key, on_change)

    def _toggled(self, btn, key, cb):
        if btn.get_active():
            cb(key)

    def set_active(self, key):
        if key in self.buttons:
            self.buttons[key].set_active(True)


class Chips(Gtk.ScrolledWindow):
    """A single row of pill toggle buttons (scrolls horizontally when narrow)."""

    def __init__(self, options, on_change, active=None):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.set_propagate_natural_height(True)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.add_css_class("chips-row")
        self.buttons = {}
        group = None
        for key, text in options:
            b = Gtk.ToggleButton(label=text)
            b.add_css_class("chip")
            if group is not None:
                b.set_group(group)
            else:
                group = b
            self.buttons[key] = b
            row.append(b)
        self.buttons[active if active in self.buttons else options[0][0]].set_active(True)
        for key, b in self.buttons.items():
            b.connect("toggled", lambda btn, k=key: btn.get_active() and on_change(k))
        self.set_child(row)


def switch_row(title, subtitle=None, active=False, on_toggle=None, sensitive=True, extra=None, last=False):
    """Row with title/subtitle and a switch. on_toggle(new_state) -> bool (False reverts)."""
    row = hbox(12, "row last" if last else "row")
    texts = vbox(2)
    texts.set_hexpand(True)
    texts.append(label(title, "row-title", wrap=True))
    if subtitle:
        texts.append(label(subtitle, "row-sub", wrap=True))
    row.append(texts)
    if extra is not None:
        extra.set_valign(Gtk.Align.CENTER)
        row.append(extra)
    sw = Gtk.Switch()
    sw.set_active(bool(active))
    sw.set_valign(Gtk.Align.CENTER)
    sw.set_sensitive(sensitive)
    if on_toggle:
        def changed(widget, _pspec):
            if getattr(widget, "_debos_lock", False):
                return
            ok = on_toggle(widget.get_active())
            if ok is False:
                widget._debos_lock = True
                widget.set_active(not widget.get_active())
                widget._debos_lock = False
        sw.connect("notify::active", changed)
    row.append(sw)
    row.switch = sw
    return row


def check_row(title, subtitle=None, active=False, badges=(), on_toggle=None, last=False):
    row = hbox(10, "row last" if last else "row")
    chk = Gtk.CheckButton()
    chk.set_active(bool(active))
    chk.set_valign(Gtk.Align.START)
    row.append(chk)
    texts = vbox(2)
    texts.set_hexpand(True)
    top = hbox(8)
    top.append(label(title, "row-title", wrap=True))
    for text, kind in badges:
        b = badge(text, kind)
        b.set_valign(Gtk.Align.CENTER)
        top.append(b)
    texts.append(top)
    if subtitle:
        texts.append(label(subtitle, "row-sub", wrap=True))
    row.append(texts)
    # clicking anywhere on the text toggles the check button
    click = Gtk.GestureClick()
    click.connect("released", lambda *_a: chk.set_active(not chk.get_active()))
    texts.add_controller(click)
    if on_toggle:
        chk.connect("toggled", lambda w: on_toggle(w.get_active()))
    row.check = chk
    row.top = top
    row.texts = texts
    return row


def action_row(title, subtitle=None, widgets=(), icon_name=None, icon_css=None, last=False, title_badges=()):
    row = hbox(12, "row last" if last else "row")
    if icon_name:
        holder = Gtk.Box()
        holder.add_css_class("sev")
        for c in (icon_css or "info").split():
            holder.add_css_class(c)
        ic = icon(icon_name, 20)
        ic.set_hexpand(True)
        ic.set_vexpand(True)
        ic.set_halign(Gtk.Align.CENTER)
        ic.set_valign(Gtk.Align.CENTER)
        holder.append(ic)
        holder.set_valign(Gtk.Align.CENTER)
        holder.set_hexpand(False)
        holder.set_size_request(40, 40)
        row.append(holder)
    texts = vbox(2)
    texts.set_hexpand(True)
    top = hbox(8)
    top.append(label(title, "row-title", wrap=True))
    for text, kind in title_badges:
        b = badge(text, kind)
        b.set_valign(Gtk.Align.CENTER)
        top.append(b)
    texts.append(top)
    if subtitle:
        texts.append(label(subtitle, "row-sub", wrap=True, selectable=False))
    row.append(texts)
    for w in widgets:
        w.set_valign(Gtk.Align.CENTER)
        row.append(w)
    row.texts = texts
    row.top = top
    return row


def kv_grid(pairs):
    grid = Gtk.Grid()
    grid.set_column_spacing(18)
    grid.set_row_spacing(7)
    for i, (k, v) in enumerate(pairs):
        grid.attach(label(k, "kv-key"), 0, i, 1, 1)
        val = label(v, "kv-val", wrap=True, selectable=True)
        val.set_hexpand(True)
        # a sensible minimum width: otherwise the label may be squeezed to one character
        # per line while GTK computes the minimum height (min > natural warnings on GTK >= 4.20)
        val.set_width_chars(min(len(v), 18) if v else 1)
        grid.attach(val, 1, i, 1, 1)
    return grid


def empty_state(icon_name, title, text=""):
    box = vbox(6, "empty")
    box.set_halign(Gtk.Align.CENTER)
    box.append(icon(icon_name, 48, "dim"))
    box.append(label(title, "empty-title", xalign=0.5))
    if text:
        box.append(label(text, "dim", wrap=True, xalign=0.5, max_chars=60))
    return box


def scrolled(child, vexpand=True):
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.set_vexpand(vexpand)
    sw.set_child(child)
    return sw


def dropdown(options, active=None, on_change=None):
    """options: list of (key, text). Returns Gtk.DropDown with .keys list."""
    keys = [k for k, _t in options]
    dd = Gtk.DropDown.new_from_strings([t for _k, t in options])
    dd.keys = keys
    if active in keys:
        dd.set_selected(keys.index(active))
    if on_change:
        dd.connect("notify::selected", lambda w, _p: on_change(w.keys[w.get_selected()] if w.get_selected() < len(w.keys) else None))
    return dd


def dd_value(dd):
    i = dd.get_selected()
    return dd.keys[i] if 0 <= i < len(dd.keys) else None


class Dialog(Gtk.Window):
    """Modal dialog in the app style (works on all GTK 4 versions)."""

    def __init__(self, parent, title, body="", details=None, buttons=(("Close", "", None),), width=520, extra=None):
        super().__init__()
        self.add_css_class("debos-dialog")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title(title)
        self.set_default_size(width, -1)
        self.set_resizable(True)
        box = vbox(12)
        box.set_margin_top(22)
        box.set_margin_bottom(18)
        box.set_margin_start(22)
        box.set_margin_end(22)
        box.append(label(title, "dialog-title", wrap=True))
        if body:
            box.append(label(body, "dialog-body", wrap=True, max_chars=70))
        if extra is not None:
            box.append(extra)
        if details:
            exp = Gtk.Expander(label=_("Show script"))
            tv = Gtk.TextView()
            tv.set_editable(False)
            tv.set_monospace(True)
            tv.get_buffer().set_text(details)
            tv.set_left_margin(10)
            tv.set_top_margin(8)
            sw = Gtk.ScrolledWindow()
            sw.set_min_content_height(240)
            sw.set_child(tv)
            sw.add_css_class("editor")
            exp.set_child(sw)
            box.append(exp)
        row = hbox(8)
        row.set_halign(Gtk.Align.END)
        row.set_margin_top(6)
        for text, kind, cb in buttons:
            b = button(_(text), kind=kind)
            b.connect("clicked", self._on_button, cb)
            row.append(b)
        box.append(row)
        self.set_child(box)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

    def _on_button(self, _btn, cb):
        self.close()
        if cb:
            GLib.idle_add(lambda: (cb(), False)[1])

    def _on_key(self, _ctrl, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False


class Toaster(Gtk.Revealer):
    """Bottom toast notification."""

    def __init__(self):
        super().__init__()
        self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)
        self.box = hbox(12, "toast")
        self.icon = icon("dialog-information-symbolic", 18)
        self.msg = label("", wrap=True, max_chars=70)
        self.action_btn = Gtk.Button()
        self.action_btn.set_visible(False)
        self.action_btn.connect("clicked", self._on_action)
        self.box.append(self.icon)
        self.box.append(self.msg)
        self.box.append(self.action_btn)
        self.set_child(self.box)
        self._timeout = None
        self._action = None
        self.set_can_target(True)

    def show(self, text, kind="", action=None, seconds=5):
        for c in ("ok", "err"):
            self.box.remove_css_class(c)
        if kind:
            self.box.add_css_class(kind)
        self.icon.set_from_icon_name({"ok": "object-select-symbolic", "err": "dialog-error-symbolic"}.get(kind, "dialog-information-symbolic"))
        self.msg.set_text(text)
        if action:
            self.action_btn.set_label(action[0])
            self._action = action[1]
            self.action_btn.set_visible(True)
        else:
            self.action_btn.set_visible(False)
            self._action = None
        self.set_reveal_child(True)
        if self._timeout:
            GLib.source_remove(self._timeout)
        self._timeout = GLib.timeout_add_seconds(seconds, self._hide)

    def _hide(self):
        self.set_reveal_child(False)
        self._timeout = None
        return False

    def _on_action(self, _b):
        self._hide()
        if self._action:
            self._action()
