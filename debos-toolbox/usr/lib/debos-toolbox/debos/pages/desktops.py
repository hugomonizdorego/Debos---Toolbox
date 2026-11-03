from gi.repository import Gtk

from .. import widgets as W
from ..core import apt, desktops as D, system
from ..core.tasks import Task
from ..i18n import _
from .base import Page


def load_state():
    inst = apt.installed()
    cands = apt.candidates(D.all_candidate_packages())
    names, sess = D.current_info()
    return {"installed": inst, "candidates": cands, "sessions": D.session_files(), "current": names, "session": sess,
            "dm": system.display_manager()}


class Desktops(Page):
    ID = "desktops"
    TITLE = "Desktops & WMs"
    SUBTITLE = "Desktop environments, window managers and login managers"
    ICON = "video-display-symbolic"
    KEYWORDS = "desktop environment window manager wm dm display manager login gnome kde xfce cinnamon mate lxqt i3 sway hyprland gdm sddm lightdm greetd"

    def build(self):
        self.show_unavailable = False
        self.seg = W.Segmented([("de", "Desktop environments"), ("wm", "Window managers"), ("dm", "Login managers")], self._tab)
        self.seg.set_halign(Gtk.Align.START)
        top = W.hbox(12)
        top.append(self.seg)
        top.append(W.spacer())
        sw = Gtk.Switch()
        sw.connect("notify::active", lambda w, _p: self._toggle_unavail(w.get_active()))
        top.append(W.label("Show unavailable", "dim"))
        top.append(sw)
        self.content.append(top)
        self.body = W.vbox(16)
        self.content.append(self.body)
        self.tab = "de"
        self.state = None

    def _toggle_unavail(self, on):
        self.show_unavailable = on
        self.render()

    def _tab(self, key):
        self.tab = key
        self.render()

    def refresh(self):
        self.loading(self.body, "Checking which desktops are packaged for your Debian release…")
        self.win.data.get("desktops", load_state, self._loaded)

    def on_data_changed(self, groups):
        self.win.data.cache.pop("desktops", None)
        super().on_data_changed(groups)

    def _loaded(self, state):
        if isinstance(state, Exception):
            W.clear(self.body)
            self.body.append(W.empty_state("dialog-error-symbolic", "Could not read package information", str(state)))
            return
        self.state = state
        self.render()

    def render(self):
        if not self.state:
            return
        W.clear(self.body)
        {"de": self._render_de, "wm": self._render_wm, "dm": self._render_dm}[self.tab]()

    def _status_badges(self, installed, current, available):
        b = []
        if current:
            b.append(("● " + _("Current"), "primary"))
        if installed:
            b.append(("✓ " + _("Installed"), "ok"))
        if not available and not installed:
            b.append((_("Not available"), "muted"))
        return b

    def _render_de(self):
        st = self.state
        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_max_children_per_line(3)
        grid.set_min_children_per_line(1)
        grid.set_homogeneous(True)
        grid.set_row_spacing(16)
        grid.set_column_spacing(16)
        self.body.append(grid)
        shown = 0
        for d in D.DESKTOPS:
            installed, current = D.status(d, st["installed"], st["sessions"], st["current"], st["session"])
            variants = D.available_variants(d, st["candidates"])
            if not variants and not installed and not self.show_unavailable:
                continue
            shown += 1
            card = W.Card(css="card")
            head = W.hbox(12)
            head.append(W.AppIcon(d["color"], "video-display-symbolic", (), None, 52))
            t = W.vbox(3)
            t.append(W.label(d["name"], "card-title"))
            bb = W.hbox(6)
            for text, kind in self._status_badges(installed, current, bool(variants)):
                bb.append(W.badge(text, kind))
            t.append(bb)
            head.append(t)
            card.add(head)
            card.add(W.label(d["desc"], "dim", wrap=True))
            row = W.hbox(8)
            if variants:
                dd = W.dropdown([(k, l) for k, l, _p in variants], variants[0][0])
                dd.set_hexpand(True)
                row.append(dd)
                row.append(W.button(_("Install") if not installed else "Add", kind="primary", small=True,
                                    on_click=lambda de=d, w=dd, v=variants: self.install_de(de, w, v)))
            if installed and not current:
                row.append(W.button(_("Remove"), kind="danger", small=True, on_click=lambda de=d: self.remove_de(de)))
            elif current:
                row.append(W.label("in use", "dim"))
            card.add(row)
            grid.insert(card, -1)
        if not shown:
            self.body.append(W.empty_state("video-display-symbolic", "No desktops found"))

    def install_de(self, d, dd, variants):
        key = W.dd_value(dd)
        pkgs = next(p for k, _l, p in variants if k == key)
        dm = d.get("dm")
        steps = D.install_de_steps(d, pkgs)
        extra = ""
        if dm and not any(x["packages"].split()[0] in self.state["installed"] for x in D.DMS):
            extra = f"\nNo login manager is installed; {dm} will be installed too."
            steps.insert(0, ("Installing a login manager", f"apt_install {dm}"))
        self.win.run(Task(f"Install {d['name']}", [("Refreshing package lists", "apt_update || true")] + steps,
                          refresh={"packages", "desktops"}),
                     confirm=f"Install {d['name']} ({key}): {pkgs}.{extra}\nLog out and choose it on the login screen afterwards.")

    def remove_de(self, d):
        steps = D.remove_de_steps(d, self.state["installed"])
        if not steps:
            self.win.toast("Nothing to remove.")
            return
        self.win.run(Task(f"Remove {d['name']}", steps, refresh={"packages", "desktops"}),
                     confirm=f"Remove {d['name']}? apt lists every package before removing anything - read it carefully.",
                     danger=True)

    def _render_wm(self):
        st = self.state
        card = W.Card("Window managers packaged in Debian",
                      "Install one, log out and pick it from the session menu of the login screen. Wayland compositors work best with GDM, SDDM or greetd.")
        self.body.append(card)
        rows = []
        for w in D.WMS:
            installed, current = D.status(w, st["installed"], st["sessions"], st["current"], st["session"])
            avail = D.wm_available(w, st["candidates"])
            if not avail and not installed and not self.show_unavailable:
                continue
            rows.append((w, installed, current, avail))
        for i, (w, installed, current, avail) in enumerate(rows):
            btns = []
            if avail and not installed:
                btns.append(W.button(_("Install"), kind="primary", small=True, on_click=lambda x=w: self.install_wm(x)))
            if installed and not current:
                btns.append(W.button(_("Remove"), kind="danger", small=True, on_click=lambda x=w: self.remove_wm(x)))
            badges = [(w["type"], "muted")] + self._status_badges(installed, current, avail)
            card.add(W.action_row(w["name"], w["desc"] + f"  ·  {w['packages']}", btns, "view-grid-symbolic",
                                  "info" if not installed else "tip", last=i == len(rows) - 1, title_badges=badges))

    def install_wm(self, w):
        self.win.run(Task(f"Install {w['name']}", [("Refreshing package lists", "apt_update || true")] + D.install_wm_steps(w),
                          refresh={"packages", "desktops"}))

    def remove_wm(self, w):
        steps = D.remove_wm_steps(w, self.state["installed"])
        if steps:
            self.win.run(Task(f"Remove {w['name']}", steps, refresh={"packages", "desktops"}),
                         confirm=f"Remove {w['name']}?")

    def _render_dm(self):
        st = self.state
        active = st["dm"]
        card = W.Card("Login managers (display managers)", f"Active now: {active or 'none'}. Only one is used at a time; switching takes effect after a restart.")
        self.body.append(card)
        rows = []
        for dm in D.DMS:
            installed = D.dm_installed(dm, st["installed"])
            avail = D.dm_available(dm, st["candidates"])
            if not avail and not installed and not self.show_unavailable:
                continue
            is_active = active == dm["unit"] or active == dm["binary"] or (active == "gdm3" and dm["id"] == "gdm3")
            if dm.get("greeter") and is_active:
                # several LightDM greeters: mark the configured one only
                is_active = dm["greeter"] in self._lightdm_greeter()
            rows.append((dm, installed, is_active, avail))
        for i, (dm, installed, is_active, avail) in enumerate(rows):
            btns = []
            if not is_active and (avail or installed):
                btns.append(W.button("Use this" if installed else "Install and use", kind="primary", small=True,
                                     on_click=lambda x=dm: self.switch_dm(x)))
            if installed and not is_active:
                btns.append(W.button(_("Remove"), kind="danger", small=True, on_click=lambda x=dm: self.remove_dm(x)))
            badges = []
            if is_active:
                badges.append(("● Active", "primary"))
            if installed:
                badges.append(("✓ " + _("Installed"), "ok"))
            elif not avail:
                badges.append((_("Not available"), "muted"))
            card.add(W.action_row(dm["name"], dm["desc"], btns, "system-lock-screen-symbolic", "info", last=i == len(rows) - 1,
                                  title_badges=badges))

    @staticmethod
    def _lightdm_greeter():
        from ..core.util import read_file
        import glob
        text = read_file("/etc/lightdm/lightdm.conf")
        for f in sorted(glob.glob("/etc/lightdm/lightdm.conf.d/*.conf")):
            text += "\n" + read_file(f)
        found = [l.split("=", 1)[1].strip() for l in text.splitlines() if l.strip().startswith("greeter-session=")]
        return found[-1] if found else "lightdm-gtk-greeter"

    def switch_dm(self, dm):
        self.win.run(Task(f"Switch login manager to {dm['name']}", D.switch_dm_steps(dm), refresh={"packages", "desktops"},
                          stop_on_error=True),
                     confirm=f"Install and use {dm['name']} as the login screen? Restart the computer afterwards.")

    def remove_dm(self, dm):
        pkg = dm["packages"].split()[-1]
        self.win.run(Task(f"Remove {dm['name']}", [("Removing", [f"apt-get purge {pkg}", "apt-get autoremove --purge"])],
                          refresh={"packages", "desktops"}), confirm=f"Remove {dm['name']}?")
