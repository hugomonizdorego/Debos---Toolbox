import os
import re

from gi.repository import Gtk

from .. import widgets as W
from ..core import system, tweaks
from .base import Page


class Startup(Page):
    ID = "startup"
    TITLE = "Startup Apps"
    SUBTITLE = "Programs that start when you log in"
    ICON = "system-run-symbolic"
    KEYWORDS = "startup autostart login session boot programs"

    def build(self):
        self.add_action(W.button("Add program", "list-add-symbolic", "primary", self.add))
        self.show_all = False
        top = W.hbox(10)
        top.append(W.label("Switches change only your account (~/.config/autostart). System entries are disabled with a per-user override.", "dim", wrap=True))
        top.append(W.spacer())
        top.append(W.label("Show entries for other desktops", "dim"))
        sw = Gtk.Switch()
        sw.connect("notify::active", lambda w, _p: self._show_all(w.get_active()))
        top.append(sw)
        self.content.append(top)
        self.card_list = W.Card()
        self.content.append(self.card_list)

    def _show_all(self, on):
        self.show_all = on
        self.refresh()

    def refresh(self):
        body = self.card_list.body
        W.clear(body)
        names = system.session()["names"]
        entries = [e for e in tweaks.autostart_entries(names) if (self.show_all or e["relevant"]) and not e["no_display"] or
                   (self.show_all and e["no_display"])]
        if not entries:
            body.append(W.empty_state("system-run-symbolic", "No startup programs"))
            return
        for i, e in enumerate(entries):
            badges = [("system" if e["system_path"] else "yours", "muted" if e["system_path"] else "primary")]
            if not e["relevant"]:
                badges.append(("other desktop", "warn"))
            row = W.switch_row(e["name"], (e["comment"] + "\n" if e["comment"] else "") + e["exec"], e["enabled"],
                               lambda on, en=e: self._toggle(en, on), last=i == len(entries) - 1)
            ic = W.icon([e["icon"], "application-x-executable-symbolic"], 32)
            row.prepend(ic) if hasattr(row, "prepend") else row.insert_child_after(ic, None)
            for text, kind in badges:
                b = W.badge(text, kind)
                b.set_valign(Gtk.Align.CENTER)
                row.insert_child_after(b, row.get_first_child().get_next_sibling())
            if not e["system_path"]:
                rm = W.icon_button("user-trash-symbolic", "Delete this entry", lambda en=e: self._delete(en))
                rm.set_valign(Gtk.Align.CENTER)
                row.append(rm)
            body.append(row)

    def _toggle(self, entry, on):
        try:
            tweaks.set_autostart(entry, on)
            self.win.toast(f"{entry['name']}: {'enabled' if on else 'disabled'} at login", "ok")
            return True
        except OSError as exc:
            self.win.toast(str(exc), "err")
            return False

    def _delete(self, entry):
        def do():
            try:
                os.remove(entry["path"])
            except OSError:
                pass
            self.refresh()
        self.win.confirm("Delete startup entry?", entry["name"], do, "Delete", danger=True)

    def add(self):
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(10)
        name, cmd, delay = Gtk.Entry(), Gtk.Entry(), Gtk.SpinButton.new_with_range(0, 300, 5)
        name.set_placeholder_text("My program")
        cmd.set_placeholder_text("command --with-arguments")
        for i, (lbl, w) in enumerate((("Name", name), ("Command", cmd), ("Delay (seconds)", delay))):
            grid.attach(W.label(lbl, "row-title"), 0, i, 1, 1)
            w.set_hexpand(True)
            grid.attach(w, 1, i, 1, 1)

        def ok():
            n, c = name.get_text().strip(), cmd.get_text().strip()
            if not n or not c or not re.match(r"^[^\n]+$", c):
                self.win.toast("Name and command are required.", "err")
                return
            tweaks.add_autostart(n, c, int(delay.get_value()))
            self.refresh()
        W.Dialog(self.win, "Add startup program", "It will start every time you log in.", extra=grid,
                 buttons=(("Cancel", "", None), ("Add", "primary", ok))).present()
