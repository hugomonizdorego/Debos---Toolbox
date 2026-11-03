"""Base class for pages: header (title, subtitle, actions) and scrollable content."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from .. import widgets as W  # noqa: E402
from ..i18n import _  # noqa: E402


class Page(Gtk.Box):
    ID = ""
    TITLE = ""
    SUBTITLE = ""
    ICON = "applications-system-symbolic"
    KEYWORDS = ""
    SCROLL = True

    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.win = win
        self.built = False
        self.loaded = False
        self.add_css_class("content-bg")

    # ------------------------------------------------------------ lifecycle
    def ensure_built(self):
        if self.built:
            return
        self.built = True
        outer = W.vbox(16, "page")
        head = W.hbox(12)
        texts = W.vbox(2)
        texts.set_hexpand(True)
        texts.append(W.label(_(self.TITLE), "page-title"))
        texts.append(W.label(_(self.SUBTITLE), "page-subtitle", wrap=True))
        head.append(texts)
        self.actions = W.hbox(8)
        self.actions.set_valign(Gtk.Align.CENTER)
        head.append(self.actions)
        outer.append(head)
        self.content = W.vbox(16)
        self.content.set_vexpand(True)
        outer.append(self.content)
        if self.SCROLL:
            self.append(W.scrolled(outer))
        else:
            outer.set_vexpand(True)
            self.append(outer)
        self.build()

    def build(self):
        """Create the widgets of the page (called once, lazily)."""

    def on_show(self):
        """Called every time the page becomes visible."""
        if not self.loaded:
            self.loaded = True
            self.refresh()

    def refresh(self):
        """Reload data shown on the page."""

    def on_data_changed(self, groups):
        """Called after a task finished; groups is a set like {'packages', 'sources'}."""
        if self.built and self.loaded:
            self.refresh()

    # -------------------------------------------------------------- helpers
    def add_action(self, widget):
        self.actions.append(widget)
        return widget

    def section(self, title, subtitle=None, parent=None):
        box = W.vbox(2)
        box.append(W.label(title, "section-title"))
        if subtitle:
            box.append(W.label(subtitle, "section-sub", wrap=True))
        (parent or self.content).append(box)
        return box

    def card(self, title=None, subtitle=None, header_extra=None, parent=None, css="card"):
        c = W.Card(title, subtitle, header_extra, css=css)
        (parent or self.content).append(c)
        return c

    def grid(self, columns=2, parent=None, homogeneous=True, spacing=16):
        g = Gtk.Grid()
        g.set_column_spacing(spacing)
        g.set_row_spacing(spacing)
        g.set_column_homogeneous(homogeneous)
        g.columns = columns
        g.count = 0
        (parent or self.content).append(g)
        return g

    @staticmethod
    def grid_add(g, widget, span=1):
        col = g.count % g.columns
        row = g.count // g.columns
        widget.set_hexpand(True)
        g.attach(widget, col, row, span, 1)
        g.count += span

    def loading(self, container, text=None):
        W.clear(container)
        box = W.hbox(10)
        sp = Gtk.Spinner()
        sp.start()
        box.append(sp)
        box.append(W.label(text or _("Loading…"), "dim"))
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        container.append(box)
