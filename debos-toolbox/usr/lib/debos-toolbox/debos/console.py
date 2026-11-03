"""Task console: a queue of tasks executed one at a time.

Tasks run inside an embedded VTE terminal when gir1.2-vte-3.91 is available
(so apt prompts, debconf dialogs and password prompts work), otherwise in an
external terminal emulator.  Completion is detected through a status file
written by debos-launch, which works for both modes.
"""

import os
import shutil
import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

try:
    gi.require_version("Vte", "3.91")
    from gi.repository import Vte  # noqa: E402
except (ValueError, ImportError):
    Vte = None

from .core import tasks as T  # noqa: E402
from .core.util import LAUNCHER  # noqa: E402
from .i18n import _  # noqa: E402
from . import widgets as W  # noqa: E402

TERMINALS = [
    ("x-terminal-emulator", ["-e"]), ("gnome-terminal", ["--"]), ("kgx", ["--"]), ("ptyxis", ["--"]),
    ("konsole", ["-e"]), ("xfce4-terminal", ["-x"]), ("mate-terminal", ["-x"]), ("tilix", ["-e"]),
    ("terminator", ["-x"]), ("qterminal", ["-e"]), ("lxterminal", ["-e"]), ("kitty", []),
    ("alacritty", ["-e"]), ("foot", []), ("xterm", ["-e"]),
]


def external_terminal():
    for binary, args in TERMINALS:
        path = shutil.which(binary)
        if path:
            return [path] + args
    return None


class TaskConsole(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = window
        self.queue = []
        self.current = None
        self.history = []
        self._poll = None
        self._status_path = None
        self.on_state_changed = None   # callback() for header indicators
        self.add_css_class("console")

        head = W.hbox(8, "console-head")
        self.spinner = Gtk.Spinner()
        head.append(self.spinner)
        self.title = W.label(_("Console"), "console-title", ellipsize=True)
        self.title.set_hexpand(True)
        head.append(self.title)
        self.queue_lbl = W.label("", "queue-chip")
        self.queue_lbl.set_visible(False)
        head.append(self.queue_lbl)
        self.state_lbl = W.label("", "badge muted")
        head.append(self.state_lbl)
        self.stop_btn = Gtk.Button(label=_("Stop"))
        self.stop_btn.set_tooltip_text("Send Ctrl+C to the running task")
        self.stop_btn.connect("clicked", lambda *_a: self.stop())
        self.stop_btn.set_sensitive(False)
        head.append(self.stop_btn)
        copy_btn = Gtk.Button(label=_("Copy log"))
        copy_btn.connect("clicked", lambda *_a: self.copy_text())
        head.append(copy_btn)
        hide_btn = Gtk.Button(label=_("Hide"))
        hide_btn.connect("clicked", lambda *_a: self.win.show_console(False))
        head.append(hide_btn)
        self.append(head)

        if Vte is not None:
            self.term = Vte.Terminal()
            self.term.set_vexpand(True)
            self.term.set_scrollback_lines(20000)
            font = Pango.FontDescription.from_string(f"Monospace {self.win.settings.get('console_font_size')}")
            self.term.set_font(font)
            self._style_terminal()
            self.term.connect("child-exited", self._on_child_exited)
            frame = Gtk.ScrolledWindow()
            frame.set_child(self.term)
            frame.set_vexpand(True)
            frame.set_margin_start(10)
            frame.set_margin_end(10)
            frame.set_margin_bottom(8)
            self.append(frame)
            self.feed("\x1b[1;35mDebos console\x1b[0m - tasks run here; password prompts and questions appear in this window.\r\n")
        else:
            self.term = None
            self.text = Gtk.TextView()
            self.text.set_editable(False)
            self.text.set_monospace(True)
            self.text.set_left_margin(12)
            sw = Gtk.ScrolledWindow()
            sw.set_child(self.text)
            sw.set_vexpand(True)
            sw.set_margin_start(10)
            sw.set_margin_end(10)
            sw.set_margin_bottom(8)
            self.append(sw)
            self.log("The embedded console needs the package gir1.2-vte-3.91.\n"
                     "Tasks open in an external terminal window instead; their status is shown here.\n")

    # ------------------------------------------------------------------ UI
    def _style_terminal(self):
        from gi.repository import Gdk

        def rgba(text):
            c = Gdk.RGBA()
            c.parse(text)
            return c
        palette = [rgba(c) for c in ("#1B2235", "#FF5F70", "#2FCB81", "#F5AE45", "#5B8DFF", "#B65BE0", "#22C3E6", "#D7E0F2",
                                     "#4A5675", "#FF7B8A", "#4FE09A", "#FFC56A", "#86A9FF", "#CC80F0", "#5BD8F2", "#FFFFFF")]
        try:
            self.term.set_colors(rgba("#D7E0F2"), rgba("#080C16"), palette)
        except TypeError:
            pass

    def feed(self, text):
        if self.term is not None:
            self.term.feed(text.replace("\n", "\r\n").encode("utf-8") if "\r\n" not in text else text.encode("utf-8"))
        else:
            self.log(text)

    def log(self, text):
        buf = self.text.get_buffer()
        buf.insert(buf.get_end_iter(), text)

    def copy_text(self):
        if self.term is not None:
            self.term.select_all()
            try:
                self.term.copy_clipboard_format(Vte.Format.TEXT)
            except Exception:
                self.term.copy_clipboard()
            self.term.unselect_all()
        else:
            buf = self.text.get_buffer()
            self.get_clipboard().set(buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False))
        self.win.toast("Console output copied to the clipboard")

    def _update_header(self):
        n = len(self.queue)
        self.queue_lbl.set_visible(n > 0)
        self.queue_lbl.set_text(f"{n} {_('Queued').lower()}")
        running = self.current is not None
        self.stop_btn.set_sensitive(running and self.term is not None)
        if running:
            self.spinner.start()
            self.title.set_text(self.current.title)
            self.state_lbl.set_text(_("Running"))
            self.state_lbl.set_css_classes(["badge", "info"])
        else:
            self.spinner.stop()
            last = self.history[-1] if self.history else None
            if last:
                self.title.set_text(last.title)
                ok = last.state == "done"
                self.state_lbl.set_text(_("Done") if ok else _("Failed"))
                self.state_lbl.set_css_classes(["badge", "ok" if ok else "err"])
            else:
                self.state_lbl.set_text(_("Ready"))
                self.state_lbl.set_css_classes(["badge", "muted"])
        if self.on_state_changed:
            self.on_state_changed()

    # --------------------------------------------------------------- queue
    def busy(self):
        return self.current is not None or bool(self.queue)

    def enqueue(self, task):
        self.queue.append(task)
        self._update_header()
        if self.current is None:
            self._next()

    def _next(self):
        if self.current is not None or not self.queue:
            self._update_header()
            return
        task = self.queue.pop(0)
        self.current = task
        task.state = "running"
        self._update_header()
        self.win.show_console(True)
        try:
            script, status = T.write_script(task, self.win.ctx)
        except OSError as exc:
            self._finish(task, False, f"Could not write the task script: {exc}")
            return
        self._status_path = status
        mode = "root" if task.root else "user"
        env = dict(os.environ)
        env["DEBOS_PRIV"] = self.win.settings.get("privilege") or "auto"
        env.setdefault("TERM", "xterm-256color")
        argv = ["/bin/bash", LAUNCHER, mode, script, status]
        if self.term is not None:
            self.feed(f"\r\n\x1b[1;34m▶ {task.title}\x1b[0m\r\n")
            envv = [f"{k}={v}" for k, v in env.items()]
            try:
                self.term.spawn_async(Vte.PtyFlags.DEFAULT, os.path.expanduser("~"), argv + ["0"], envv,
                                      GLib.SpawnFlags.DEFAULT, None, None, -1, None, self._spawned, task)
            except TypeError:
                # very old VTE bindings without the user_data argument
                self.term.spawn_async(Vte.PtyFlags.DEFAULT, os.path.expanduser("~"), argv + ["0"], envv,
                                      GLib.SpawnFlags.DEFAULT, None, None, -1, None, None)
        else:
            term = external_terminal()
            if not term:
                self._finish(task, False, "No terminal emulator found. Install gir1.2-vte-3.91 or xterm.")
                return
            self.log(f"\n▶ {task.title} (running in an external terminal)\n")
            try:
                subprocess.Popen(term + argv + ["1"], env=env, start_new_session=True)
            except OSError as exc:
                self._finish(task, False, f"Could not start the terminal: {exc}")
                return
        self._poll = GLib.timeout_add(700, self._poll_status)

    def _spawned(self, _term, pid, error, *user_data):
        if error is not None or (pid is not None and pid < 0):
            task = self.current
            if task is not None:
                self._finish(task, False, f"Could not start the task: {error}")

    def _poll_status(self):
        if self.current is None or not self._status_path:
            self._poll = None
            return False
        if os.path.exists(self._status_path):
            try:
                with open(self._status_path) as fh:
                    code = int((fh.read().strip() or "1"))
            except (OSError, ValueError):
                code = 1
            try:
                os.remove(self._status_path)
            except OSError:
                pass
            self._poll = None
            self._finish(self.current, code == 0, None, code)
            return False
        return True

    def _on_child_exited(self, _term, status):
        # the status file is authoritative; give the poller a moment to see it
        GLib.timeout_add(300, self._poll_status)

    def _finish(self, task, success, message=None, code=None):
        if self._poll:
            GLib.source_remove(self._poll)
            self._poll = None
        task.state = "done" if success else ("cancelled" if code in (126, 130) else "failed")
        task.exit_code = code
        self.current = None
        self.history.append(task)
        if message:
            self.feed(f"\r\n\x1b[1;31m{message}\x1b[0m\r\n")
        self._update_header()
        try:
            if task.on_done:
                task.on_done(task, success)
        finally:
            self.win.task_finished(task, success)
            GLib.idle_add(lambda: (self._next(), False)[1])

    def stop(self):
        if self.current is not None and self.term is not None:
            self.term.feed_child(b"\x03")
