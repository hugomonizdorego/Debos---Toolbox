import glob
import os
import shutil

from gi.repository import Gtk

from .. import widgets as W
from ..core import apt, catalog, system
from ..core.tasks import Task
from ..core.util import run, shq, safe_pkg
from ..i18n import _
from .base import Page


def installed_flatpaks():
    if not shutil.which("flatpak"):
        return set()
    return set(run(["flatpak", "list", "--app", "--columns=application"], timeout=20)[1].split())


def appstream_icons():
    """Map package names and Flatpak IDs to 64px icons from the AppStream caches."""
    icons = {}
    patterns = ["/var/cache/swcatalog/icons/*/64x64/*.png", "/var/lib/app-info/icons/*/64x64/*.png",
                "/var/lib/flatpak/appstream/*/*/active/icons/64x64/*.png"]
    for pat in patterns:
        for path in glob.glob(pat):
            base = os.path.basename(path)[:-4]
            key = base.split("_", 1)[0] if "/flatpak/" not in path else base
            icons.setdefault(key, path)
    return icons


def load_software_state():
    inst = apt.installed()
    cands = apt.candidates(catalog.all_packages())
    fps = installed_flatpaks()
    ex = catalog.extrepo_list() if shutil.which("extrepo") else None
    remotes = run(["flatpak", "remotes", "--columns=name"], timeout=10)[1] if shutil.which("flatpak") else ""
    return {"installed": inst, "candidates": cands, "flatpaks": fps, "extrepo": set(ex) if ex is not None else None,
            "icons": appstream_icons(), "flathub": "flathub" in remotes}


def app_installed(app, state):
    if app["check"] and app["check"] in state["installed"]:
        return True
    return any(m["type"] == "flatpak" and m["id"] in state["flatpaks"] for m in app["methods"])


class AppTile(Gtk.Overlay):
    def __init__(self, page, app, state, methods):
        super().__init__()
        self.page, self.app, self.methods = page, app, methods
        self.installed = app_installed(app, state)
        box = W.vbox(6, "app-tile")
        box.set_size_request(176, 182)
        icon_file = None
        for key in [app["check"]] + [m.get("id") for m in app["methods"] if m["type"] == "flatpak"]:
            if key and key in state["icons"]:
                icon_file = state["icons"][key]
                break
        box.append(W.AppIcon(app["color"], app["glyph"], app["icons"], icon_file, 60))
        box.append(W.label(app["name"], "app-name", xalign=0.5, ellipsize=True))
        desc = W.label(app["summary"], "app-desc", xalign=0.5, wrap=True)
        desc.set_lines(2) if hasattr(desc, "set_lines") else None
        desc.set_ellipsize(3)
        desc.set_max_width_chars(22)
        box.append(desc)
        if self.installed:
            chip = W.badge("✓ " + _("Installed"), "ok")
        elif methods:
            chip = W.badge(catalog.method_label(methods[0]).split(" (")[0], "primary")
        else:
            chip = W.badge(_("Not available"), "muted")
        chip.set_halign(Gtk.Align.CENTER)
        box.append(chip)
        self.box = box
        self.set_child(box)
        self.check = W.icon("object-select-symbolic", 14)
        holder = Gtk.Box()
        holder.add_css_class("app-check")
        holder.append(self.check)
        self.check.set_hexpand(True)
        self.check.set_halign(Gtk.Align.CENTER)
        holder.set_halign(Gtk.Align.END)
        holder.set_valign(Gtk.Align.START)
        holder.set_margin_top(8)
        holder.set_margin_end(8)
        holder.set_visible(False)
        holder.set_can_target(False)
        self.holder = holder
        self.add_overlay(holder)
        click = Gtk.GestureClick()
        click.connect("released", self._clicked)
        self.add_controller(click)
        self.set_tooltip_text(f"{app['name']} - {app['summary']}\nClick to select, double-click for details")
        if not methods and not self.installed:
            self.set_opacity(0.55)

    def _clicked(self, gesture, n_press, _x, _y):
        if n_press >= 2 or self.installed or not self.methods:
            self.page.details(self.app)
        else:
            self.page.toggle(self.app["id"])

    def set_selected(self, on):
        self.holder.set_visible(on)
        if on:
            self.box.add_css_class("selected")
        else:
            self.box.remove_css_class("selected")


class Software(Page):
    ID = "software"
    TITLE = "Software Center"
    SUBTITLE = "Install apps from Debian, vendors and Flathub"
    ICON = "system-software-install-symbolic"
    KEYWORDS = "install apps applications software store browser flatpak flathub deb vendor"
    SCROLL = False

    def build(self):
        self.selected = []
        self.choice = {}
        self.category = "popular"
        self.state = None
        bar = W.hbox(10)
        self.chips = W.Chips([(k, _(t)) for k, t, _i in catalog.CATEGORIES] + [("installed", _("Installed")), ("all", "All")],
                             self._category, active="popular")
        self.chips.set_hexpand(True)
        bar.append(self.chips)
        self.filter = W.search_entry("Filter apps (Enter searches all Debian packages)")
        self.filter.set_size_request(300, -1)
        self.filter.connect("search-changed", lambda *_a: self.render())
        self.filter.connect("activate", lambda *_a: self.search_everything(self.filter.get_text().strip()))
        bar.append(self.filter)
        self.content.append(bar)

        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_homogeneous(True)
        self.flow.set_max_children_per_line(8)
        self.flow.set_min_children_per_line(2)
        self.flow.set_row_spacing(16)
        self.flow.set_column_spacing(16)
        self.flow.set_valign(Gtk.Align.START)
        inner = W.vbox(16)
        inner.append(self.flow)
        self.extra = W.vbox(16)
        inner.append(self.extra)
        sw = W.scrolled(inner)
        self.content.append(sw)

        self.selbar = Gtk.Revealer()
        self.selbar.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        sb = W.hbox(12, "selection-bar")
        self.sel_lbl = W.label("", "row-title")
        self.sel_lbl.set_hexpand(True)
        sb.append(self.sel_lbl)
        sb.append(W.button(_("Clear selection"), kind="ghost", on_click=self.clear))
        sb.append(W.button(_("Install"), "system-software-install-symbolic", "primary", self.install_selected))
        self.selbar.set_child(sb)
        self.content.append(self.selbar)
        self.tiles = {}

    def refresh(self):
        W.clear(self.flow)
        self.loading(self.extra, "Checking which apps are available for your Debian release…")
        self.win.data.get("software", load_software_state, self._loaded)

    def on_data_changed(self, groups):
        self.win.data.invalidate({"packages"})
        self.win.data.cache.pop("software", None)
        super().on_data_changed(groups)

    def _loaded(self, state):
        if isinstance(state, Exception):
            W.clear(self.extra)
            self.extra.append(W.empty_state("dialog-error-symbolic", "Could not read the package lists", str(state)))
            return
        self.state = state
        W.clear(self.extra)
        if not state["flathub"] and shutil.which("flatpak") is None:
            self.extra.append(W.label("Tip: Flatpak apps install Flatpak and Flathub automatically.", "dim"))
        self.render()

    def _category(self, key):
        self.category = key
        if self.state:
            self.render()

    def methods_for(self, app):
        return catalog.available_methods(app, self.state["candidates"], self.state["extrepo"], self.win.release.get("arch") or system.arch())

    def render(self):
        if not self.state:
            return
        W.clear(self.flow)
        self.tiles = {}
        q = self.filter.get_text().strip().lower()
        arch = system.arch()
        self.win.release.setdefault("arch", arch)
        for app in catalog.APPS:
            if q:
                if q not in (app["name"] + " " + app["summary"] + " " + app["id"]).lower():
                    continue
            elif self.category == "popular" and not app["popular"]:
                continue
            elif self.category == "installed" and not app_installed(app, self.state):
                continue
            elif self.category not in ("popular", "installed", "all") and app["category"] != self.category:
                continue
            tile = AppTile(self, app, self.state, self.methods_for(app))
            tile.set_selected(app["id"] in self.selected)
            self.tiles[app["id"]] = tile
            self.flow.insert(tile, -1)
        if not self.tiles:
            self.flow.insert(W.empty_state("system-search-symbolic", "No matching apps",
                                           "Press Enter to search all Debian packages and Flathub."), -1)
        self._update_bar()

    def toggle(self, aid):
        if aid in self.selected:
            self.selected.remove(aid)
        else:
            self.selected.append(aid)
        if aid in self.tiles:
            self.tiles[aid].set_selected(aid in self.selected)
        self._update_bar()

    def clear(self):
        for aid in list(self.selected):
            self.toggle(aid)

    def _update_bar(self):
        n = len(self.selected)
        self.selbar.set_reveal_child(n > 0)
        self.sel_lbl.set_text(f"{n} app{'s' if n != 1 else ''} selected: " + ", ".join(catalog.APP_INDEX[a]["name"] for a in self.selected[:6]))

    def chosen_method(self, app):
        methods = self.methods_for(app)
        want = self.choice.get(app["id"])
        for m in methods:
            if m is want:
                return m
        return methods[0] if methods else None

    def install_selected(self):
        steps, names = [], []
        for aid in self.selected:
            app = catalog.APP_INDEX[aid]
            m = self.chosen_method(app)
            if m is None:
                continue
            steps += catalog.install_steps(app, m)
            names.append(f"{app['name']} - {catalog.method_label(m)}")
        if not steps:
            return
        steps.insert(0, ("Refreshing package lists", "apt_update || true"))
        self.selected = []
        self.render()
        self.win.run(Task(f"Install {len(names)} app(s)", steps, refresh={"packages", "flatpak", "sources"}),
                     confirm="Install:\n• " + "\n• ".join(names))

    def details(self, app):
        methods = self.methods_for(app) if self.state else []
        installed = self.state and app_installed(app, self.state)
        box = W.vbox(10)
        top = W.hbox(14)
        top.append(W.AppIcon(app["color"], app["glyph"], app["icons"], None, 64))
        t = W.vbox(2)
        t.append(W.label(app["name"], "card-title"))
        t.append(W.label(app["summary"], "dim", wrap=True))
        if installed:
            t.append(W.badge("✓ " + _("Installed"), "ok"))
        top.append(t)
        box.append(top)
        group = None
        radios = []
        if methods:
            box.append(W.label("Install from", "row-title"))
            for m in methods:
                rb = Gtk.CheckButton(label=catalog.method_label(m))
                if group:
                    rb.set_group(group)
                else:
                    group = rb
                rb.set_active(m is self.chosen_method(app))
                radios.append((rb, m))
                box.append(rb)
            box.append(W.label("Debian packages are preferred: they get security updates with the rest of the system. "
                               "Vendor repositories are added with their signing key via Signed-By.", "dim", wrap=True))
        else:
            box.append(W.label("This app is not available for your Debian release or architecture.", "warn-text", wrap=True))

        def pick():
            for rb, m in radios:
                if rb.get_active():
                    self.choice[app["id"]] = m
                    return m
            return None

        def install():
            m = pick()
            if m:
                self.win.run(Task(f"Install {app['name']}", [("Refreshing package lists", "apt_update || true")] +
                                  catalog.install_steps(app, m), refresh={"packages", "flatpak", "sources"},
                                  stop_on_error=True))

        def remove():
            steps = catalog.remove_steps(app, self.state["installed"], self.state["flatpaks"])
            if steps:
                self.win.run(Task(f"Remove {app['name']}", steps, refresh={"packages", "flatpak"}),
                             confirm="apt will show what it removes and asks before continuing.")

        buttons = [("Close", "", None)]
        if installed:
            buttons.append((_("Remove"), "danger", remove))
        if methods:
            buttons.append((_("Install") if not installed else "Reinstall / other source", "primary", install))
        W.Dialog(self.win, app["name"], "", extra=box, buttons=tuple(buttons), width=520).present()

    # ------------------------------------------------- search everything
    def search_everything(self, query):
        if len(query) < 2:
            return
        W.clear(self.extra)
        card = W.Card(f"Debian packages matching '{query}'")
        self.extra.append(card)
        self.loading(card.body)
        fcard = None
        if shutil.which("flatpak"):
            fcard = W.Card(f"Flathub apps matching '{query}'")
            self.extra.append(fcard)
            self.loading(fcard.body)
            self.win.async_call(lambda: run(["flatpak", "search", "--columns=application,name,description", query], timeout=60)[1],
                                lambda text: self._flathub_results(fcard, text))
        self.win.async_call(lambda: apt.search(query), lambda res: self._apt_results(card, res))

    def _apt_results(self, card, res):
        W.clear(card.body)
        if isinstance(res, Exception) or not res:
            card.add(W.label("No packages found.", "dim"))
            return
        inst = self.state["installed"] if self.state else {}
        for i, (name, desc) in enumerate(res[:60]):
            btn = W.badge("✓ installed", "ok") if name in inst else W.button(_("Install"), kind="primary", small=True,
                                                                             on_click=lambda n=name: self._install_pkg(n))
            card.add(W.action_row(name, desc, [btn], last=i == min(59, len(res) - 1)))

    def _flathub_results(self, card, text):
        W.clear(card.body)
        rows = [l.split("\t") for l in (text or "").splitlines() if "\t" in l]
        if isinstance(text, Exception) or not rows:
            card.add(W.label("No Flathub results (is Flathub configured?).", "dim"))
            return
        for i, parts in enumerate(rows[:40]):
            appid, name = parts[0], parts[1] if len(parts) > 1 else parts[0]
            desc = parts[2] if len(parts) > 2 else ""
            card.add(W.action_row(name, f"{desc}\n{appid}", [W.button(_("Install"), kind="primary", small=True,
                                                                         on_click=lambda a=appid: self._install_flatpak(a))],
                                  last=i == min(39, len(rows) - 1)))

    def _install_pkg(self, name):
        if not safe_pkg(name):
            return
        self.win.run(Task(f"Install {name}", [("Installing", f"apt_install {shq(name)}")], refresh={"packages"}))

    def _install_flatpak(self, appid):
        self.win.run(Task(f"Install {appid}", [("Setting up Flathub", ["ensure_pkg flatpak",
                                                                      "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"]),
                                               ("Installing", f"flatpak install -y --noninteractive flathub {shq(appid)}")],
                          refresh={"flatpak"}))
