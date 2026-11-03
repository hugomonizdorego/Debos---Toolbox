"""Debos - Toolbox main application and window."""

import os
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, APP_NAME, VERSION  # noqa: E402
from . import theme, widgets as W  # noqa: E402
from .console import TaskConsole  # noqa: E402
from .core import system, tasks  # noqa: E402
from .core.util import Settings  # noqa: E402
from .i18n import LANGUAGES, _, set_language  # noqa: E402
from .pages import registry  # noqa: E402

NAV = [
    ("Overview", ["dashboard", "recommendations"]),
    ("Maintenance", ["cleaner", "updates", "repositories", "sources"]),
    ("Software", ["software", "uninstall", "desktops"]),
    ("System", ["kernels", "drivers", "network", "systemtweaks"]),
    ("Personalize", ["desktoptweaks", "startup", "defaultapps", "templates", "customizer"]),
    ("Info", ["about"]),
]


class DataHub:
    """Shares expensive, read-only data (package lists, hardware scans) between pages."""

    GROUPS = {
        "installed": {"packages"}, "candidates": {"packages", "sources"}, "upgrades": {"packages", "sources"},
        "kernels": {"packages", "kernels"}, "hardware": {"drivers", "packages"}, "flatpaks": {"packages", "flatpak"},
        "recommendations": {"packages", "sources", "kernels", "drivers", "cleaner", "tweaks", "flatpak"},
        "cleaner": {"cleaner", "packages", "kernels"}, "sources": {"sources"}, "desktops": {"packages", "desktops"},
        "extrepo": {"sources", "packages"},
    }

    def __init__(self):
        self.cache = {}
        self.waiting = {}

    def get(self, key, loader, callback, force=False):
        if not force and key in self.cache:
            value = self.cache[key]
            GLib.idle_add(lambda: (callback(value), False)[1])
            return
        if key in self.waiting:
            self.waiting[key].append(callback)
            return
        self.waiting[key] = [callback]

        def work():
            try:
                value = loader()
            except Exception as exc:  # never let a loader kill the UI
                import traceback
                traceback.print_exc()
                value = exc
            GLib.idle_add(self._deliver, key, value)
        threading.Thread(target=work, daemon=True).start()

    def _deliver(self, key, value):
        if not isinstance(value, Exception):
            self.cache[key] = value
        for cb in self.waiting.pop(key, []):
            try:
                cb(value)
            except Exception:
                import traceback
                traceback.print_exc()
        return False

    def invalidate(self, groups):
        for key in list(self.cache):
            base = key.split(":", 1)[0]
            if self.GROUPS.get(base, {"packages"}) & set(groups) or "all" in groups:
                del self.cache[key]


def run_async(work, done):
    """Run work() in a thread and deliver the result to done() on the GTK main loop."""
    def runner():
        try:
            result = work()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            result = exc
        GLib.idle_add(lambda: (done(result), False)[1])
    threading.Thread(target=runner, daemon=True).start()


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app, start_page="dashboard"):
        super().__init__(application=app)
        self.app = app
        self.settings = app.settings
        self.add_css_class("debos")
        self.set_title(f"{APP_NAME} {VERSION}")
        self.set_default_size(1280, 820)
        self.set_size_request(960, 600)
        self.set_icon_name("debos-toolbox")
        self.ctx = tasks.Context()
        self.release = self.ctx.release
        self.data = DataHub()
        self.pages = {}
        self.nav_rows = {}
        self.nav_counts = {}
        self.current = None
        self._before_search = "dashboard"

        self._build_header()
        root = W.hbox(0)
        root.append(self._build_sidebar())

        main = W.vbox(0)
        main.set_hexpand(True)
        main.add_css_class("content-bg")
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack.set_vexpand(True)
        for pid, cls in registry.PAGES.items():
            page = cls(self)
            self.pages[pid] = page
            self.stack.add_named(page, pid)

        self.console = TaskConsole(self)
        self.console.on_state_changed = self._update_console_button
        self.console.set_visible(False)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_start_child(self.stack)
        self.paned.set_end_child(self.console)
        self.paned.set_resize_start_child(True)
        self.paned.set_resize_end_child(False)
        self.paned.set_shrink_end_child(False)
        self.paned.set_vexpand(True)

        overlay = Gtk.Overlay()
        overlay.set_child(self.paned)
        self.toaster = W.Toaster()
        overlay.add_overlay(self.toaster)
        main.append(overlay)
        main.append(self._build_hintbar())
        root.append(main)
        self.set_child(root)

        self._install_shortcuts()
        self.navigate(start_page)

    # ---------------------------------------------------------------- header
    def _build_header(self):
        header = Gtk.HeaderBar()
        wrap = W.hbox(8, "search-wrap")
        wrap.set_size_request(520, -1)
        wrap.append(W.icon("system-search-symbolic", 16, "search-icon"))
        self.search = Gtk.Entry()
        self.search.set_placeholder_text(_("Search apps, settings or run a command"))
        self.search.set_hexpand(True)
        self.search.connect("changed", self._on_search_changed)
        self.search.connect("activate", self._on_search_activate)
        wrap.append(self.search)
        hint = W.label("Ctrl F", "kbd")
        hint.set_valign(Gtk.Align.CENTER)
        wrap.append(hint)
        header.set_title_widget(wrap)

        self.menu_btn = Gtk.MenuButton()
        self.menu_btn.set_icon_name("open-menu-symbolic")
        self.menu_btn.add_css_class("icon-btn")
        self.menu_btn.set_popover(self._build_menu())
        header.pack_end(self.menu_btn)

        self.theme_btn = W.icon_button(self._theme_icon(), _("Theme"), self.toggle_theme)
        header.pack_end(self.theme_btn)

        bell = Gtk.Overlay()
        self.bell_btn = W.icon_button("alarm-symbolic", _("Recommendations"), lambda: self.navigate("recommendations"))
        bell.set_child(self.bell_btn)
        self.bell_count = W.label("", "nav-count")
        self.bell_count.set_halign(Gtk.Align.END)
        self.bell_count.set_valign(Gtk.Align.START)
        self.bell_count.set_visible(False)
        self.bell_count.set_can_target(False)
        bell.add_overlay(self.bell_count)
        header.pack_end(bell)

        con = Gtk.Overlay()
        self.console_btn = W.icon_button("utilities-terminal-symbolic", _("Console") + " (Ctrl+J)",
                                         lambda: self.show_console(not self.console.get_visible()))
        con.set_child(self.console_btn)
        self.console_spinner = Gtk.Spinner()
        self.console_spinner.set_halign(Gtk.Align.END)
        self.console_spinner.set_valign(Gtk.Align.START)
        self.console_spinner.set_size_request(12, 12)
        self.console_spinner.set_can_target(False)
        con.add_overlay(self.console_spinner)
        header.pack_end(con)

        refresh = W.icon_button("view-refresh-symbolic", _("Refresh") + " (Ctrl+R)", self.refresh_current)
        header.pack_start(refresh)
        self.set_titlebar(header)

    def _build_menu(self):
        pop = Gtk.Popover()
        box = W.vbox(8)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.append(W.label(_("Language"), "row-sub"))
        lang = W.dropdown(list(LANGUAGES.items()), self.settings.get("language"), self.set_language)
        box.append(lang)
        box.append(W.label(_("Theme"), "row-sub"))
        box.append(W.dropdown([("system", _("System theme")), ("light", _("Light")), ("dark", _("Dark"))],
                              self.settings.get("theme"), self.set_theme))
        box.append(Gtk.Separator())
        for text, cb in ((_("About"), lambda: self.navigate("about")),
                         (_("Console") + "  (Ctrl+J)", lambda: self.show_console(True)),
                         ("Quit  (Ctrl+Q)", self.app.quit)):
            b = W.button(text, kind="ghost", on_click=lambda c=cb: (pop.popdown(), c()))
            b.set_halign(Gtk.Align.FILL)
            box.append(b)
        pop.set_child(box)
        return pop

    # --------------------------------------------------------------- sidebar
    def _build_sidebar(self):
        side = W.vbox(0, "sidebar")
        side.set_size_request(262, -1)
        profile = W.vbox(10, "profile")
        top = W.hbox(12)
        avatar = Gtk.Overlay()
        face = os.path.join(self.ctx.home, ".face")
        initial = W.label((self.ctx.user[:1] or "?").upper(), "avatar", xalign=0.5)
        initial.set_size_request(52, 52)
        avatar.set_child(initial)
        if os.path.isfile(face):
            pic = Gtk.Picture.new_for_filename(face)
            pic.set_size_request(52, 52)
            if hasattr(pic, "set_content_fit"):
                pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.add_css_class("avatar")
            pic.set_overflow(Gtk.Overflow.HIDDEN)
            avatar.add_overlay(pic)
        top.append(avatar)
        who = W.vbox(2)
        who.set_valign(Gtk.Align.CENTER)
        who.append(W.label(self.ctx.user, "name", ellipsize=True))
        who.append(W.label(os.uname().nodename, "sub", ellipsize=True))
        top.append(who)
        profile.append(top)
        profile.append(W.label(system.release_badge(self.release), "badge-pill", ellipsize=True))
        side.append(profile)

        nav = W.vbox(0)
        for section, ids in NAV:
            nav.append(W.label(_(section).upper(), "nav-section"))
            for pid in ids:
                cls = registry.PAGES[pid]
                row = W.hbox(12, "nav-row")
                row.append(W.icon(cls.ICON, 17))
                lbl = W.label(_(cls.TITLE), ellipsize=True)
                lbl.set_hexpand(True)
                row.append(lbl)
                count = W.label("", "nav-count")
                count.set_visible(False)
                row.append(count)
                click = Gtk.GestureClick()
                click.connect("released", lambda *_a, p=pid: self.navigate(p))
                row.add_controller(click)
                self.nav_rows[pid] = row
                self.nav_counts[pid] = count
                nav.append(row)
        side.append(W.scrolled(nav))
        side.append(W.label(f"{APP_NAME} {VERSION}", "sidebar-footer"))
        return side

    def _build_hintbar(self):
        bar = W.hbox(14, "hintbar")
        for keys, text in (("Ctrl F", _("Search")), ("Ctrl R", _("Refresh")), ("Ctrl J", _("Console")), ("Esc", _("Close"))):
            bar.append(W.label(keys, "kbd"))
            bar.append(W.label(text))
        bar.append(W.spacer())
        r = self.release
        self.status_lbl = W.label(f"{system.release_badge(r)} · {system.arch()} · {self.ctx.user}")
        bar.append(self.status_lbl)
        return bar

    # ------------------------------------------------------------ navigation
    def navigate(self, pid):
        if pid not in self.pages:
            return
        if pid != "search":
            self._before_search = pid
        for key, row in self.nav_rows.items():
            if key == pid:
                row.add_css_class("active")
            else:
                row.remove_css_class("active")
        page = self.pages[pid]
        page.ensure_built()
        self.stack.set_visible_child_name(pid)
        self.current = pid
        page.on_show()

    def refresh_current(self):
        page = self.pages.get(self.current)
        if page and page.built:
            self.data.invalidate({"all"})
            page.refresh()
            self.toast(_("Refresh") + ": " + _(page.TITLE))

    def set_nav_count(self, pid, count):
        lbl = self.nav_counts.get(pid)
        if lbl is None:
            return
        lbl.set_visible(bool(count))
        lbl.set_text(str(count) if count else "")
        if pid == "recommendations":
            self.bell_count.set_visible(bool(count))
            self.bell_count.set_text(str(count) if count else "")

    # ---------------------------------------------------------------- search
    def _on_search_changed(self, entry):
        text = entry.get_text().strip()
        if text:
            if self.current != "search":
                self.navigate("search")
            self.pages["search"].search(text)
        elif self.current == "search":
            self.navigate(self._before_search)

    def _on_search_activate(self, _entry):
        if self.current == "search":
            self.pages["search"].activate_first()

    # -------------------------------------------------------------- shortcuts
    def _install_shortcuts(self):
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

    def _on_key(self, _ctrl, keyval, _code, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self.search.grab_focus()
            return True
        if ctrl and keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self.refresh_current()
            return True
        if ctrl and keyval in (Gdk.KEY_j, Gdk.KEY_J):
            self.show_console(not self.console.get_visible())
            return True
        if ctrl and keyval in (Gdk.KEY_q, Gdk.KEY_Q):
            self.app.quit()
            return True
        if keyval == Gdk.KEY_Escape and self.search.get_text():
            self.search.set_text("")
            return True
        return False

    # -------------------------------------------------------------- console
    def show_console(self, visible=True):
        self.console.set_visible(visible)
        if visible:
            height = self.get_height() or 820
            pos = max(240, height - 330)
            if self.paned.get_position() <= 0 or self.paned.get_position() > height - 160:
                self.paned.set_position(pos)
        self._update_console_button()

    def _update_console_button(self):
        busy = self.console.busy()
        if busy:
            self.console_spinner.start()
        else:
            self.console_spinner.stop()
        if self.console.get_visible():
            self.console_btn.add_css_class("active")
        else:
            self.console_btn.remove_css_class("active")

    # ----------------------------------------------------------------- tasks
    def run(self, task, confirm=None, danger=False, extra=None):
        """Queue a task, optionally after a confirmation dialog that can show the script."""
        if confirm:
            script = tasks.build_script(task, self.ctx)
            kind = "danger" if danger else "primary"
            dlg = W.Dialog(self, task.title, confirm, details=script, extra=extra,
                           buttons=(("Cancel", "", None), ("Run", kind, lambda: self.console.enqueue(task))))
            dlg.present()
            return
        self.console.enqueue(task)

    def task_finished(self, task, success):
        groups = set(task.refresh) | ({"packages"} if task.root else set())
        self.data.invalidate(groups or {"packages"})
        for pid, page in self.pages.items():
            if not page.built:
                continue
            if pid == self.current:
                page.on_data_changed(groups)
            else:
                page.loaded = False
        if success:
            self.toast(f"{_('Task finished')}: {task.title}", "ok")
        elif task.state == "cancelled":
            self.toast(f"{task.title}: cancelled", "")
        else:
            self.toast(f"{_('Task failed')}: {task.title}", "err", action=(_("Console"), lambda: self.show_console(True)))

    def confirm(self, title, body, on_ok, ok_label="Continue", danger=False):
        W.Dialog(self, title, body, buttons=(("Cancel", "", None), (ok_label, "danger" if danger else "primary", on_ok))).present()

    def info(self, title, body):
        W.Dialog(self, title, body).present()

    def toast(self, text, kind="", action=None):
        self.toaster.show(text, kind, action)

    def async_call(self, work, done):
        run_async(work, done)

    # ------------------------------------------------------------- settings
    def _theme_icon(self):
        return "weather-clear-symbolic" if theme.resolve_mode(self.settings.get("theme")) == "dark" else "weather-clear-night-symbolic"

    def toggle_theme(self):
        mode = theme.resolve_mode(self.settings.get("theme"))
        self.set_theme("light" if mode == "dark" else "dark")

    def set_theme(self, value):
        if not value:
            return
        self.settings.set("theme", value)
        theme.apply(theme.resolve_mode(value))
        self.theme_btn.set_child(W.icon(self._theme_icon(), 16))
        for page in self.pages.values():
            if page.built:
                page.queue_draw()

    def set_language(self, code):
        if not code or code == self.settings.get("language"):
            return
        self.settings.set("language", code)
        set_language(code)
        if self.console.busy():
            self.toast("The language changes after the running task finishes and Debos is restarted.")
            return
        current = self.current if self.current != "search" else "dashboard"
        new = MainWindow(self.app, start_page=current)
        new.present()
        self.destroy()


class DebosApp(Gtk.Application):
    def __init__(self, start_page="dashboard"):
        flags = getattr(Gio.ApplicationFlags, "DEFAULT_FLAGS", Gio.ApplicationFlags.FLAGS_NONE)
        super().__init__(application_id=APP_ID, flags=flags)
        self.settings = Settings()
        self.start_page = start_page
        set_language(self.settings.get("language"))

    def do_startup(self):
        Gtk.Application.do_startup(self)
        GLib.set_application_name(APP_NAME)
        theme.use_adwaita_icons()
        theme.apply(theme.resolve_mode(self.settings.get("theme")))
        Gtk.Window.set_default_icon_name("debos-toolbox")

    def do_activate(self):
        win = self.props.active_window
        if win is None:
            win = MainWindow(self, self.start_page)
        win.present()
