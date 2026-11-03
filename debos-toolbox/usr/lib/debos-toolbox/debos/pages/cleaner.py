import threading

from gi.repository import GLib, Gtk

from .. import theme, widgets as W
from ..core import cleaner
from ..core.tasks import Task
from ..core.util import human_size
from ..i18n import _
from .base import Page

SECTIONS = [("System", "System", "Needs administrator rights."),
            ("Personal", "Personal", "Your caches and history - no password needed."),
            ("Browsers", "Browsers", "Web caches. Close the browser before cleaning it.")]


class Cleaner(Page):
    ID = "cleaner"
    TITLE = "Cleaner"
    SUBTITLE = "Scan and free disk space safely"
    ICON = "user-trash-symbolic"
    KEYWORDS = "clean janitor cache junk disk space trash kernel autoremove thumbnails browser"

    def build(self):
        self.scan_btn = self.add_action(W.button(_("Scan"), "view-refresh-symbolic", "", self.refresh))
        self.clean_btn = self.add_action(W.button(_("Clean"), "edit-clear-all-symbolic", "primary", self.clean))
        top = W.hbox(16)
        self.content.append(top)
        pal = theme.PALETTES[theme.resolve_mode(self.win.settings.get("theme"))]
        dcard = W.Card(css="card neu")
        self.donut = W.Donut(150, "pink", 0, "…", track=pal["surface3"], text_color=pal["text"])
        self.donut.set_halign(Gtk.Align.CENTER)
        dcard.add(self.donut)
        dcard.add(W.label(_("Reclaimable"), "card-title", xalign=0.5))
        dcard.set_size_request(220, -1)
        top.append(dcard)
        info = W.Card("Janitor", "Inspired by Ubuntu Cleaner and Ubuntu Tweak's Janitor, adapted to Debian. "
                                 "Nothing is deleted until you press Clean, and every command is shown in the console.")
        info.set_hexpand(True)
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        info.add(self.progress)
        self.selected_lbl = W.label("", "big-number")
        info.add(self.selected_lbl)
        self.hint = W.label("", "dim", wrap=True)
        info.add(self.hint)
        top.append(info)
        self.checks = {}
        self.rows = {}
        self.results = {}
        self.section_cards = {}
        cols = W.hbox(16)
        self.content.append(cols)
        left, right = W.vbox(16), W.vbox(16)
        left.set_hexpand(True)
        right.set_hexpand(True)
        cols.append(left)
        cols.append(right)
        for sid, title, sub in SECTIONS:
            card = W.Card(title, sub)
            (left if sid == "System" else right).append(card)
            items = [i for i in cleaner.ITEMS if i.section == sid]
            for n, item in enumerate(items):
                row = W.check_row(item.title, item.desc, item.default, last=n == len(items) - 1,
                                  on_toggle=lambda _a: self._update_selected())
                size = W.badge("…", "muted")
                size.set_valign(Gtk.Align.CENTER)
                row.append(size)
                exp = Gtk.Expander(label="Details")
                exp.add_css_class("row-sub")
                det = W.label("", "mono dim", wrap=True, selectable=True)
                exp.set_child(det)
                exp.set_visible(False)
                row.texts.append(exp)
                card.add(row)
                self.checks[item.id] = row.check
                self.rows[item.id] = (row, size, exp, det)
            self.section_cards[sid] = card

    def refresh(self):
        self.scan_btn.set_sensitive(False)
        self.clean_btn.set_sensitive(False)
        self.progress.set_fraction(0)
        self.progress.set_text("Scanning…")
        home = self.win.ctx.home

        def progress(frac, title):
            GLib.idle_add(self._progress, frac, title)

        def work():
            res = cleaner.scan_all(home, progress)
            GLib.idle_add(self._done, res)
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, frac, title):
        self.progress.set_fraction(frac)
        self.progress.set_text(f"{title}…")
        return False

    def _done(self, results):
        self.results = results
        self.scan_btn.set_sensitive(True)
        self.clean_btn.set_sensitive(True)
        self.progress.set_fraction(1)
        self.progress.set_text("Scan complete")
        total = 0
        for item in cleaner.ITEMS:
            r = results.get(item.id) or {}
            row, size, exp, det = self.rows[item.id]
            if r.get("unknown_size"):
                size.set_text("auto")
                size.set_css_classes(["badge", "info"])
            elif r.get("size"):
                size.set_text(human_size(r["size"]))
                size.set_css_classes(["badge", "primary"])
                total += r["size"]
            elif r.get("count"):
                size.set_text(f"{r['count']} item(s)")
                size.set_css_classes(["badge", "primary"])
            else:
                size.set_text("clean")
                size.set_css_classes(["badge", "ok"])
            if r.get("warning"):
                size.set_text(r["warning"])
                size.set_css_classes(["badge", "warn"])
                row.check.set_active(False)
            details = r.get("details") or []
            exp.set_visible(bool(details))
            det.set_text("\n".join(details[:60]) + ("\n…" if len(details) > 60 else ""))
            nothing = not r.get("size") and not r.get("count") and not r.get("unknown_size")
            row.set_sensitive(not nothing and not r.get("skip"))
        self.donut.set_value(min(100, total / (5 * 2 ** 30) * 100), human_size(total, 0) if total else "0 B")
        self._update_selected()
        return False

    def _selected(self):
        sel = []
        for item in cleaner.ITEMS:
            chk = self.checks[item.id]
            r = self.results.get(item.id)
            row = self.rows[item.id][0]
            if r and chk.get_active() and row.get_sensitive():
                sel.append((item, r))
        return sel

    def _update_selected(self):
        sel = self._selected()
        size = sum(r.get("size", 0) for _i, r in sel)
        self.selected_lbl.set_text(f"{human_size(size)} selected" if self.results else "")
        root = any(i.root for i, _r in sel)
        self.hint.set_text(("Administrator password required for system items." if root else
                            "Only personal items selected: no password needed.") if sel else "Select items to clean.")

    def clean(self):
        sel = self._selected()
        if not sel:
            self.win.toast(_("Nothing selected."))
            return
        steps, root = cleaner.clean_steps(sel)
        steps.append(("Free space now", "df -h / | tail -n 1"))
        names = "\n• ".join(i.title for i, _r in sel)
        # the page rescans automatically when the task finishes (refresh group "cleaner")
        self.win.run(Task("Clean system", steps, root=root, refresh={"cleaner", "packages", "kernels"}),
                     confirm=f"Remove these items?\n• {names}")
