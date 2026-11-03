import os
import urllib.parse
import webbrowser

from gi.repository import Gtk

from .. import APP_NAME, AUTHOR, AUTHOR_MAIL, BUILD, DONATE, HOMEPAGE, ISSUES, VERSION, widgets as W
from ..core import system
from ..i18n import LANGUAGES, _
from .base import Page

ICON_FILES = ["/usr/share/icons/hicolor/256x256/apps/debos-toolbox.png", "/usr/share/pixmaps/debos-toolbox.png",
              os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "share", "pixmaps", "debos-toolbox.png")]

LICENSE = """Debos - Toolbox is free software: you can redistribute it and/or modify it under the terms of the GNU General
Public License version 3 or later. The original author (Hugo Moniz do Rego) must be credited in derivative works.

Linux® is the registered trademark of Linus Torvalds. Debian is a registered trademark of Software in the Public Interest,
Inc. Third-party software installed by this tool comes from its vendors under their own licenses.

Feature ideas for the Cleaner (Janitor) and the Desktop Tweaks, Startup Apps, Default Apps and Templates pages come from
Ubuntu Cleaner (Gerard Puig, GPL-3) and Ubuntu Tweak (Tualatrix Chou, GPL-2+); they were reimplemented for Debian.

AI assistance disclosure: developed with the help of AI tools (Google Gemini, Microsoft Copilot and Anthropic Claude).
The software is provided "as is", without warranty. Always keep backups of your data."""


class About(Page):
    ID = "about"
    TITLE = "About"
    SUBTITLE = "Version, credits and settings"
    ICON = "help-about-symbolic"
    KEYWORDS = "about version license credits settings language theme donate feedback"

    def build(self):
        top = W.Card(css="card")
        self.content.append(top)
        head = W.hbox(18)
        icon = next((p for p in ICON_FILES if os.path.exists(p)), None)
        if icon:
            pic = Gtk.Picture.new_for_filename(os.path.abspath(icon))
            pic.set_size_request(96, 96)
            head.append(pic)
        t = W.vbox(4)
        t.append(W.label(APP_NAME, "page-title"))
        t.append(W.label(f"Version {VERSION} · build {BUILD}", "accent-text"))
        t.append(W.label(f"By {AUTHOR} · Timor-Leste", "dim"))
        t.append(W.label("The all-in-one toolbox for Debian Stable, Testing, Sid and LMDE: cleaning, repairs, updates, "
                         "repositories, software, desktops, kernels, drivers, network and personalization.", wrap=True))
        head.append(t)
        top.add(head)
        links = W.hbox(8)
        for text, url, kind in (("Project page", HOMEPAGE, "primary"), ("Report a problem", ISSUES, ""), ("Debian", "https://www.debian.org/", ""),
                                ("FDSL - TL", "https://www.fdsl.tl/", ""), ("Donate (PayPal)", DONATE, "success")):
            links.append(W.button(text, kind=kind, on_click=lambda u=url: webbrowser.open(u)))
        top.add(links)

        settings = self.card(_("Settings"))
        s = self.win.settings
        settings.add(self._dd_row("Language", list(LANGUAGES.items()), s.get("language"), self.win.set_language))
        settings.add(self._dd_row("Theme", [("system", _("System theme")), ("light", _("Light")), ("dark", _("Dark"))], s.get("theme"), self.win.set_theme))
        settings.add(self._dd_row("Administrator rights via", [("auto", "Automatic (pkexec, then sudo, then su)"), ("pkexec", "pkexec (polkit)"),
                                                                ("sudo", "sudo"), ("su", "su (root password)")], s.get("privilege"),
                                  lambda v: v and s.set("privilege", v)))
        self.autostart = os.path.join(self.win.ctx.home, ".config/autostart/debos-toolbox-monitor.desktop")
        settings.add(W.switch_row("Health monitor at login", "Notifies you about broken packages, pending updates and low disk space.",
                                  os.path.exists(self.autostart), self._autostart, last=True))

        fb = self.card("Feedback", "Opens your e-mail program with a pre-filled message.")
        self.fb_text = Gtk.TextView()
        self.fb_text.set_wrap_mode(2)
        self.fb_text.set_left_margin(10)
        self.fb_text.set_top_margin(8)
        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(110)
        sw.set_child(self.fb_text)
        sw.add_css_class("editor")
        fb.add(sw)
        fb.add(W.button("Send feedback", "mail-send-symbolic", "primary", self.feedback))

        lic = self.card("License and credits")
        lic.add(W.label(LICENSE, "dim", wrap=True, selectable=True))

    def _dd_row(self, title, options, active, cb):
        row = W.hbox(12, "row")
        lbl = W.label(title, "row-title")
        lbl.set_hexpand(True)
        row.append(lbl)
        dd = W.dropdown(options, active, cb)
        dd.set_size_request(300, -1)
        row.append(dd)
        return row

    def _autostart(self, on):
        try:
            if on:
                os.makedirs(os.path.dirname(self.autostart), exist_ok=True)
                with open(self.autostart, "w", encoding="utf-8") as fh:
                    fh.write("[Desktop Entry]\nType=Application\nName=Debos Health Monitor\nExec=debos-toolbox --startup\n"
                             "Icon=debos-toolbox\nX-GNOME-Autostart-Delay=60\nNoDisplay=true\nComment=Checks system health at login\n")
            elif os.path.exists(self.autostart):
                os.remove(self.autostart)
            return True
        except OSError as exc:
            self.win.toast(str(exc), "err")
            return False

    def feedback(self):
        buf = self.fb_text.get_buffer()
        msg = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
        if not msg:
            self.win.toast("Write a message first.")
            return
        body = urllib.parse.quote(f"{msg}\n\n--\n{APP_NAME} {VERSION}\n{system.release_badge(self.win.release)}\n{os.uname().release}")
        webbrowser.open(f"mailto:{AUTHOR_MAIL}?subject={urllib.parse.quote(APP_NAME + ' ' + VERSION + ' feedback')}&body={body}")
