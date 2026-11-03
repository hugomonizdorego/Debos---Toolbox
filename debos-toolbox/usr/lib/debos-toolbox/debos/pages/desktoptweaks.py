import os
import shutil
import subprocess
import time

from gi.repository import Gtk

from .. import widgets as W
from ..core import system, tweaks
from ..core.tasks import Task
from ..i18n import _
from .base import Page

THEME_PACKS = [
    ("papirus", "Papirus icons", "Colourful, complete icon theme.", "papirus-icon-theme"),
    ("arc", "Arc theme", "Flat GTK theme with transparent elements.", "arc-theme"),
    ("materia", "Materia theme", "Material Design GTK theme.", "materia-gtk-theme"),
    ("breeze", "Breeze for GTK", "KDE's Breeze look for GTK apps.", "breeze-gtk-theme"),
    ("numix", "Numix", "Modern flat theme and icons.", "numix-gtk-theme numix-icon-theme"),
    ("extra", "GNOME extra themes", "HighContrast and Adwaita-dark for GTK 2/3.", "gnome-themes-extra"),
    ("cursors", "Cursor themes", "Breeze and DMZ cursors.", "breeze-cursor-theme dmz-cursor-theme"),
    ("qt", "Qt apps follow GTK theme", "Make Qt applications match (qt5ct/qt6ct, Adwaita-Qt).", "qt5ct qt6ct adwaita-qt adwaita-qt6"),
    ("fonts", "Popular fonts", "Noto (all languages), emoji, Fira, JetBrains Mono, Liberation, Inter.",
     "fonts-noto fonts-noto-color-emoji fonts-firacode fonts-jetbrains-mono fonts-liberation2 fonts-inter"),
]


class DesktopTweaks(Page):
    ID = "desktoptweaks"
    TITLE = "Desktop Tweaks"
    SUBTITLE = "Appearance, windows, input and privacy settings"
    ICON = "preferences-desktop-appearance-symbolic"
    KEYWORDS = "theme icons cursor font scaling buttons titlebar workspace touchpad tap night light hidden files clock battery dark accent tweak"

    def build(self):
        self.de_names = system.session()["names"]
        de = system.session()["desktop"] or "unknown desktop"
        self.content.append(W.label(f"Settings for your current desktop ({de}). Changes apply instantly with your own rights - "
                                    "no password needed. Ideas from Ubuntu Tweak, adapted to Debian desktops.", "dim", wrap=True))
        self.sections_box = W.vbox(16)
        self.content.append(self.sections_box)
        packs = self.card("Themes, icons and fonts from Debian", "Install, then pick them above.")
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(3)
        flow.set_min_children_per_line(2)
        flow.set_homogeneous(True)
        flow.set_row_spacing(12)
        flow.set_column_spacing(12)
        for _k, title, desc, pkgs in THEME_PACKS:
            c = W.Card(css="card soft")
            c.add(W.label(title, "row-title"))
            c.add(W.label(desc, "row-sub", wrap=True, max_chars=30))
            c.add(W.button(_("Install"), kind="primary", small=True, on_click=lambda t=title, p=pkgs: self.win.run(
                Task(f"Install {t}", [("Installing", f"apt_install_available {p}")], refresh={"packages", "tweaks"}))))
            flow.insert(c, -1)
        packs.add(flow)
        bk = self.card("Backup and restore desktop settings",
                       "Saves all dconf settings (GNOME, Cinnamon, MATE, Budgie and GTK apps) to a file you can restore later or on another computer.")
        row = W.hbox(8)
        row.append(W.button("Back up now", "document-save-symbolic", "primary", self.backup))
        row.append(W.button("Restore from file…", "document-open-symbolic", "", self.restore))
        row.append(W.button("Reset desktop settings", "edit-clear-all-symbolic", "danger", self.reset))
        bk.add(row)
        self.bk_status = W.label("", "dim", wrap=True)
        bk.add(self.bk_status)

    def refresh(self):
        W.clear(self.sections_box)
        try:
            items = tweaks.for_desktop(self.de_names)
        except Exception as exc:
            self.sections_box.append(W.empty_state("dialog-error-symbolic", "Could not read desktop settings", str(exc)))
            return
        if not items:
            self.sections_box.append(W.empty_state("preferences-desktop-appearance-symbolic", "No supported settings found",
                                                   "Desktop tweaks support GNOME, Budgie, Cinnamon, MATE and Xfce. For KDE Plasma use System Settings."))
            return
        order = []
        for t in items:
            if t.section not in order:
                order.append(t.section)
        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_max_children_per_line(2)
        grid.set_min_children_per_line(1)
        grid.set_homogeneous(False)
        grid.set_row_spacing(16)
        grid.set_column_spacing(16)
        grid.set_valign(Gtk.Align.START)
        self.sections_box.append(grid)
        for sec in order:
            card = W.Card(sec)
            group = [t for t in items if t.section == sec]
            for i, t in enumerate(group):
                card.add(self._row(t, last=i == len(group) - 1))
            card.set_size_request(440, -1)
            grid.insert(card, -1)

    def _row(self, t, last):
        try:
            value = t.get()
        except Exception:
            value = None
        if t.kind == "bool":
            return W.switch_row(t.title, t.desc, bool(value), lambda on, tw=t: self._set(tw, on), last=last)
        choices = t.choices()
        keys = [k for k, _l in choices]
        if value not in keys and value is not None:
            choices = [(value, f"{value} (current)")] + choices
        row = W.hbox(12, "row last" if last else "row")
        texts = W.vbox(2)
        texts.set_hexpand(True)
        texts.append(W.label(t.title, "row-title", wrap=True))
        if t.desc:
            texts.append(W.label(t.desc, "row-sub", wrap=True))
        row.append(texts)
        dd = W.dropdown([(k, str(l)) for k, l in choices], value, lambda v, tw=t: v is not None and self._set(tw, v))
        dd.set_valign(Gtk.Align.CENTER)
        dd.set_size_request(200, -1)
        row.append(dd)
        return row

    def _set(self, t, value):
        try:
            ok = t.set(value)
        except Exception as exc:
            self.win.toast(f"{t.title}: {exc}", "err")
            return False
        if ok:
            self.win.toast(f"{t.title}: applied", "ok")
        return ok

    def backup(self):
        if not shutil.which("dconf"):
            self.win.toast("dconf is not installed (package dconf-cli).", "err")
            return
        docs = os.path.join(self.win.ctx.home, "Documents")
        os.makedirs(docs, exist_ok=True)
        path = os.path.join(docs, f"debos-desktop-settings-{time.strftime('%Y%m%d-%H%M%S')}.ini")
        try:
            data = subprocess.run(["dconf", "dump", "/"], capture_output=True, text=True, timeout=30).stdout
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(data)
            self.bk_status.set_text(f"Saved {len(data.splitlines())} lines to {path}")
            self.win.toast("Desktop settings backed up", "ok")
        except Exception as exc:
            self.win.toast(f"Backup failed: {exc}", "err")

    def restore(self):
        def chosen(path):
            if not path:
                return
            try:
                with open(path, encoding="utf-8") as fh:
                    data = fh.read()
                r = subprocess.run(["dconf", "load", "/"], input=data, text=True, capture_output=True, timeout=60)
                if r.returncode == 0:
                    self.win.toast("Desktop settings restored", "ok")
                    self.refresh()
                else:
                    self.win.toast(r.stderr.strip() or "Restore failed", "err")
            except Exception as exc:
                self.win.toast(f"Restore failed: {exc}", "err")
        pick_file(self.win, "Choose a settings backup", chosen, os.path.join(self.win.ctx.home, "Documents"))

    def reset(self):
        def do():
            for path in ("/org/gnome/desktop/", "/org/gnome/mutter/", "/org/gnome/shell/", "/org/cinnamon/", "/org/mate/"):
                subprocess.run(["dconf", "reset", "-f", path], capture_output=True)
            self.win.toast("Desktop settings were reset to their defaults", "ok")
            self.refresh()
        self.win.confirm("Reset desktop settings?", "GNOME, Cinnamon and MATE settings return to their defaults. Make a backup first.",
                         do, "Reset", danger=True)


def pick_file(win, title, callback, folder=None):
    """File chooser that works on GTK 4.6 (FileChooserNative) and 4.10+ (FileDialog)."""
    from gi.repository import Gio
    if hasattr(Gtk, "FileDialog"):
        dlg = Gtk.FileDialog()
        dlg.set_title(title)
        if folder and os.path.isdir(folder):
            dlg.set_initial_folder(Gio.File.new_for_path(folder))

        def done(d, res):
            try:
                f = d.open_finish(res)
                callback(f.get_path() if f else None)
            except Exception:
                callback(None)
        dlg.open(win, None, done)
        return
    dlg = Gtk.FileChooserNative.new(title, win, Gtk.FileChooserAction.OPEN, "_Open", "_Cancel")
    if folder and os.path.isdir(folder):
        dlg.set_current_folder(Gio.File.new_for_path(folder))

    def resp(d, r):
        callback(d.get_file().get_path() if r == Gtk.ResponseType.ACCEPT and d.get_file() else None)
        d.destroy()
    dlg.connect("response", resp)
    dlg.show()
    win._file_dialog = dlg
