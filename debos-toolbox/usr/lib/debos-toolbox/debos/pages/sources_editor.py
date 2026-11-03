import os
import re

from gi.repository import Gtk

from .. import widgets as W
from ..core import sources
from ..core.tasks import Task
from ..core.util import read_file, runtime_dir, shq
from .base import Page


class SourcesEditor(Page):
    ID = "sources"
    TITLE = "APT Sources"
    SUBTITLE = "Edit APT source files directly"
    ICON = "document-edit-symbolic"
    KEYWORDS = "sources.list debian.sources deb822 edit editor apt"

    def build(self):
        self.add_action(W.button("Validate", "object-select-symbolic", "", self.validate))
        self.add_action(W.button("Save", "document-save-symbolic", "primary", self.save))
        card = W.Card()
        self.content.append(card)
        row = W.hbox(10)
        row.append(W.label("File", "row-title"))
        self.files = W.dropdown([(f, f) for f in self.file_list()], self.default_file(), self._file_changed)
        self.files.set_hexpand(True)
        row.append(self.files)
        self.new_entry = Gtk.Entry()
        self.new_entry.set_placeholder_text("new-file.sources")
        self.new_entry.set_width_chars(18)
        row.append(self.new_entry)
        row.append(W.button("New file", "document-new-symbolic", "", self.new_file))
        card.add(row)
        self.text = Gtk.TextView()
        self.text.set_monospace(True)
        self.text.set_left_margin(14)
        self.text.set_top_margin(12)
        self.text.set_bottom_margin(12)
        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(420)
        sw.set_child(self.text)
        sw.add_css_class("editor")
        card.add(sw)
        self.status = W.label("", "dim", wrap=True)
        card.add(self.status)
        self.path = self.default_file()
        self.text.get_buffer().connect("changed", lambda *_a: self.validate(quiet=True))

    @staticmethod
    def file_list():
        files = sources.source_files()
        if "/etc/apt/sources.list.d/debian.sources" not in files:
            files.append("/etc/apt/sources.list.d/debian.sources")
        return files

    def default_file(self):
        return "/etc/apt/sources.list.d/debian.sources" if os.path.exists("/etc/apt/sources.list.d/debian.sources") else \
            (self.file_list() or ["/etc/apt/sources.list"])[0]

    def refresh(self):
        self.load(self.path)

    def _file_changed(self, path):
        if path:
            self.load(path)

    def load(self, path):
        self.path = path
        text = read_file(path, None)
        if text is None:
            text = f"# {path} does not exist yet. Write deb822 stanzas here and press Save.\n"
        self.text.get_buffer().set_text(text)
        self.validate(quiet=True)

    def load_text(self, path, text):
        self.ensure_built()
        self.path = path
        if path in self.files.keys:
            self.files.set_selected(self.files.keys.index(path))
        self.text.get_buffer().set_text(text)
        self.status.set_text("Generated content loaded - review it and press Save.")

    def new_file(self):
        name = self.new_entry.get_text().strip()
        if not re.match(r"^[A-Za-z0-9._-]+\.(list|sources)$", name):
            self.win.toast("File names must end in .list or .sources", "err")
            return
        self.path = os.path.join(sources.SOURCES_DIR, name)
        self.text.get_buffer().set_text("Types: deb\nURIs: \nSuites: \nComponents: main\nSigned-By: \n")
        self.status.set_text(f"New file {self.path} - not saved yet.")

    def content_text(self):
        buf = self.text.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def validate(self, quiet=False):
        text = self.content_text()
        entries = sources.parse_file(self.path, text)
        problems = []
        if self.path.endswith(".sources"):
            for e in entries:
                if not e.types or not e.uris or not e.suites:
                    problems.append(f"stanza {e.index + 1}: Types, URIs and Suites are required")
                elif not e.components and not any(s.endswith("/") for s in e.suites):
                    problems.append(f"stanza {e.index + 1}: Components missing")
        else:
            for n, line in enumerate(text.splitlines(), 1):
                s = line.strip()
                if s and not s.startswith("#") and not re.match(r"^(deb|deb-src)\s", s):
                    problems.append(f"line {n}: not a deb/deb-src line")
        msg = f"{len(entries)} repository entr{'y' if len(entries) == 1 else 'ies'}"
        if problems:
            msg += " · problems: " + "; ".join(problems[:5])
            self.status.set_css_classes(["err-text"])
        else:
            msg += " · syntax looks fine"
            self.status.set_css_classes(["dim"])
        self.status.set_text(f"{self.path}: {msg}")
        if not quiet:
            self.win.toast(msg, "err" if problems else "ok")
        return not problems

    def save(self):
        path = self.path
        if not re.match(r"^/etc/apt/(sources\.list|sources\.list\.d/[A-Za-z0-9._-]+\.(list|sources))$", path):
            self.win.toast("Only files inside /etc/apt can be saved here.", "err")
            return
        text = self.content_text()
        if not text.endswith("\n"):
            text += "\n"
        tmp = os.path.join(runtime_dir(), "sources-edit.txt")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.win.run(Task(f"Save {os.path.basename(path)}", [
            ("Backing up APT configuration", "backup_apt_sources"),
            ("Saving", [f"install -D -m 0644 {shq(tmp)} {shq(path)}", f"rm -f {shq(tmp)}"]),
            ("Checking with apt-get update", "apt_update")], refresh={"sources", "packages"}),
            confirm=None if self.validate(quiet=True) else "The file has syntax problems. Save anyway?")
