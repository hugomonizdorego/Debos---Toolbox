import os

from gi.repository import Gio

from .. import widgets as W
from ..core import tweaks
from ..core.tasks import Task
from ..core.util import run, shq
from .base import Page

ALTERNATIVES = [("x-terminal-emulator", "Default terminal (x-terminal-emulator)"), ("x-www-browser", "Default browser for scripts (x-www-browser)"),
                ("editor", "Default text editor in the terminal (editor)")]


def alternatives(name):
    code, text = run(["update-alternatives", "--query", name], timeout=10)
    current, options = None, []
    for line in text.splitlines():
        if line.startswith("Value:"):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("Alternative:"):
            options.append(line.split(":", 1)[1].strip())
    return current, options


class DefaultApps(Page):
    ID = "defaultapps"
    TITLE = "Default Apps"
    SUBTITLE = "Choose which apps open your files and links"
    ICON = "starred-symbolic"
    KEYWORDS = "default applications browser mail file manager editor viewer player terminal mime"

    def build(self):
        self.user_card = self.card("For your account", "Stored in ~/.config/mimeapps.list - no password needed.")
        self.sys_card = self.card("System-wide (Debian alternatives)", "Used by scripts and programs that call the generic commands.")

    def refresh(self):
        W.clear(self.user_card.body)
        for i, (rid, title, icon, mimes) in enumerate(tweaks.ROLES):
            apps = {}
            for mime in mimes[:1]:
                for app in Gio.AppInfo.get_all_for_type(mime):
                    apps.setdefault(app.get_id(), app)
            default = Gio.AppInfo.get_default_for_type(mimes[0], False)
            if not apps:
                continue
            row = W.hbox(12, "row last" if i == len(tweaks.ROLES) - 1 else "row")
            row.append(W.icon(icon, 22))
            lbl = W.label(title, "row-title")
            lbl.set_hexpand(True)
            row.append(lbl)
            options = [(aid, a.get_display_name()) for aid, a in sorted(apps.items(), key=lambda kv: kv[1].get_display_name().lower())]
            dd = W.dropdown(options, default.get_id() if default else None,
                            lambda aid, ms=mimes, ap=apps, t=title: aid and self._set_default(ap[aid], ms, t))
            dd.set_size_request(260, -1)
            row.append(dd)
            self.user_card.add(row)
        W.clear(self.sys_card.body)
        self.win.async_call(lambda: [(n, t) + alternatives(n) for n, t in ALTERNATIVES], self._fill_alternatives)

    def _set_default(self, app, mimes, title):
        try:
            for mime in mimes:
                app.set_as_default_for_type(mime)
            if mimes[0].startswith("x-scheme-handler/http"):
                app.set_as_default_for_type("x-scheme-handler/https")
            self.win.toast(f"{title}: {app.get_display_name()}", "ok")
        except Exception as exc:
            self.win.toast(str(exc), "err")

    def _fill_alternatives(self, res):
        if isinstance(res, Exception):
            return
        for i, (name, title, current, options) in enumerate(res):
            if not options:
                continue
            row = W.hbox(12, "row last" if i == len(res) - 1 else "row")
            lbl = W.label(title, "row-title")
            lbl.set_hexpand(True)
            row.append(lbl)
            dd = W.dropdown([(o, os.path.basename(o)) for o in options], current,
                            lambda o, n=name: o and self.win.run(Task(f"Set {n}", [("update-alternatives", f"update-alternatives --set {shq(n)} {shq(o)}")])))
            dd.set_size_request(260, -1)
            row.append(dd)
            self.sys_card.add(row)
