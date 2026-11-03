import os
import stat

from .. import widgets as W
from ..core import tweaks
from .base import Page


class Templates(Page):
    ID = "templates"
    TITLE = "Templates & Scripts"
    SUBTITLE = "New-document templates and file manager scripts"
    ICON = "document-new-symbolic"
    KEYWORDS = "templates new document scripts nautilus nemo caja right click context menu"

    def build(self):
        self.tpl = self.card("New document templates", "They appear in your file manager under right-click > New Document.")
        self.scr = self.card("File manager scripts", "Right-click > Scripts in Files (Nautilus), Nemo and Caja.")

    def refresh(self):
        W.clear(self.tpl.body)
        d = tweaks.templates_dir()
        for i, (fname, title, content) in enumerate(tweaks.TEMPLATES):
            path = os.path.join(d, fname)
            self.tpl.add(W.switch_row(title, path, os.path.exists(path), lambda on, p=path, c=content: self._template(p, c, on),
                                      last=i == len(tweaks.TEMPLATES) - 1))
        W.clear(self.scr.body)
        dirs = tweaks.script_dirs()
        if not dirs:
            self.scr.add(W.empty_state("folder-symbolic", "No supported file manager found", "Install Files (Nautilus), Nemo or Caja."))
            return
        for fm, sdir in dirs:
            self.scr.add(W.label(fm, "section-title"))
            for i, (title, desc, body) in enumerate(tweaks.SCRIPTS):
                path = os.path.join(sdir, title)
                self.scr.add(W.switch_row(title, desc, os.path.exists(path), lambda on, p=path, b=body: self._script(p, b, on),
                                          last=i == len(tweaks.SCRIPTS) - 1))

    def _template(self, path, content, on):
        try:
            if on:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(content)
            elif os.path.exists(path):
                os.remove(path)
            return True
        except OSError as exc:
            self.win.toast(str(exc), "err")
            return False

    def _script(self, path, body, on):
        try:
            if on:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(body)
                os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            elif os.path.exists(path):
                os.remove(path)
            return True
        except OSError as exc:
            self.win.toast(str(exc), "err")
            return False
