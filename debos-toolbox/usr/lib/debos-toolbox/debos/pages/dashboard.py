import os
import shutil

from gi.repository import GLib, Gtk

from .. import theme, widgets as W
from ..core import apt, kernels, recommend, sources, system
from ..core.tasks import Task
from ..core.util import human_size, path_size
from ..i18n import _
from .base import Page


def load_recommendations(win):
    return recommend.collect(win.release, win.ctx.home, apt.installed())


class Dashboard(Page):
    ID = "dashboard"
    TITLE = "Dashboard"
    SUBTITLE = "Your system at a glance"
    ICON = "go-home-symbolic"
    KEYWORDS = "overview home status system information"

    def build(self):
        self.add_action(W.button(_("Update system"), "software-update-available-symbolic", "primary", self.update_system))
        grid = self.grid(columns=4, homogeneous=True, spacing=14)
        self.tiles = {}
        specs = [("updates", "orange", "software-update-available-symbolic", _("Updates"), lambda: self.win.navigate("updates")),
                 ("packages", "green", "package-x-generic-symbolic", _("Packages"), lambda: self.win.navigate("uninstall")),
                 ("reclaim", "pink", "user-trash-symbolic", _("Reclaimable"), lambda: self.win.navigate("cleaner")),
                 ("kernels", "purple", "computer-symbolic", _("Kernels"), lambda: self.win.navigate("kernels")),
                 ("repos", "cyan", "network-server-symbolic", _("Repositories"), lambda: self.win.navigate("repositories")),
                 ("recs", "lime", "starred-symbolic", "Suggestions", lambda: self.win.navigate("recommendations")),
                 ("uptime", "violet", "alarm-symbolic", _("Uptime"), None),
                 ("health", "red", "security-high-symbolic", _("Health"), lambda: self.win.navigate("recommendations"))]
        for key, color, icon, title, cb in specs:
            t = W.Tile(color, icon, title, "…", "", on_click=cb)
            self.tiles[key] = t
            self.grid_add(grid, t)

        row = W.hbox(16)
        self.content.append(row)
        pal = theme.PALETTES[theme.resolve_mode(self.win.settings.get("theme"))]
        self.donuts = {}
        for key, title, color in (("disk", _("Disk"), "blue"), ("mem", _("Memory"), "violet"), ("health", _("Health score"), "green")):
            card = W.Card(css="card neu")
            d = W.Donut(132, color, 0, None, track=pal["surface3"], text_color=pal["text"])
            d.set_halign(Gtk.Align.CENTER)
            card.add(d)
            lbl = W.label(title, "card-title", xalign=0.5)
            card.add(lbl)
            sub = W.label("", "card-sub", xalign=0.5, wrap=True)
            card.add(sub)
            card.set_size_request(190, -1)
            self.donuts[key] = (d, sub)
            row.append(card)
        cpu = W.Card(_("CPU activity"), "Last 2 minutes")
        cpu.set_hexpand(True)
        self.cpu_chart = W.LineChart(118, "blue", grid=pal["surface3"])
        cpu.add(self.cpu_chart)
        self.cpu_lbl = W.label("", "big-number")
        cpu.add(self.cpu_lbl)
        row.append(cpu)

        row2 = W.hbox(16)
        self.content.append(row2)
        self.info_card = W.Card(_("System information"))
        self.info_card.set_hexpand(True)
        row2.append(self.info_card)
        qa = W.Card(_("Quick actions"))
        qa.set_size_request(430, -1)
        # a fixed 4 x 2 grid: GtkFlowBox reports a minimum height larger than its natural
        # height in a vertical box on GTK >= 4.20 (one row per child)
        flow = Gtk.Grid()
        flow.set_row_spacing(14)
        flow.set_column_spacing(10)
        flow.set_column_homogeneous(True)
        for i, (color, icon, text, cb) in enumerate((
                ("blue", "software-update-available-symbolic", _("Update system"), self.update_system),
                ("pink", "user-trash-symbolic", _("Clean"), lambda: self.win.navigate("cleaner")),
                ("orange", "emblem-system-symbolic", _("Fix packages"), self.fix_packages),
                ("cyan", "network-server-symbolic", "Repo Doctor", self.repo_doctor),
                ("purple", "video-display-symbolic", _("Drivers"), lambda: self.win.navigate("drivers")),
                ("green", "system-software-install-symbolic", _("Software"), lambda: self.win.navigate("software")),
                ("violet", "computer-symbolic", _("Kernels"), lambda: self.win.navigate("kernels")),
                ("red", "system-reboot-symbolic", "Restart", self.reboot))):
            flow.attach(W.circle_action(color, icon, text, cb), i % 4, i // 4, 1, 1)
        qa.add(flow)
        row2.append(qa)

        self.recs_card = W.Card(_("Top recommendations"), None,
                                W.button(_("See all"), kind="ghost", on_click=lambda: self.win.navigate("recommendations")))
        self.content.append(self.recs_card)
        self._cpu_prev = system.cpu_times()
        self._timer = GLib.timeout_add_seconds(2, self._tick)

    # ---------------------------------------------------------------- data
    def refresh(self):
        self._fill_info()
        for t in self.tiles.values():
            t.set("…", "")
        self.win.async_call(self._gather, self._fill)
        self.win.data.get("recommendations", lambda: load_recommendations(self.win), self._fill_recs, force=self.loaded and False)

    def _gather(self):
        d = {}
        ups, _ok = apt.simulate_upgrade(True)
        d["updates"] = (len(ups), f"{sum(1 for u in ups if u['security'])} security")
        inst = apt.installed()
        fps = 0
        if shutil.which("flatpak"):
            from ..core.util import run
            fps = len(run(["flatpak", "list", "--app", "--columns=application"], timeout=20)[1].split())
        d["packages"] = (len(inst), f"{fps} Flatpak apps" if fps else "deb packages")
        inv = kernels.inventory()
        old = kernels.old_kernels(inv)
        reclaim = apt.apt_cache_size() + max(0, path_size("/var/log/journal") - 200 * 2 ** 20) + \
            path_size(os.path.join(self.win.ctx.home, ".cache/thumbnails")) + sum(k["size"] for k in old)
        d["reclaim"] = (human_size(reclaim), "cache, logs, old kernels")
        d["kernels"] = (len(inv["kernels"]), f"{len(old)} old" if old else "running " + inv["running"].split("-")[0])
        ents = [e for e in sources.parse_all() if e.enabled]
        third = len([e for e in ents if not e.is_official_debian()])
        d["repos"] = (len(ents), f"{third} third-party")
        d["uptime"] = (system.uptime_text(), "since boot")
        return d

    def _fill(self, d):
        if isinstance(d, Exception):
            return
        for key, (val, note) in d.items():
            self.tiles[key].set(val, note)

    def _fill_recs(self, recs):
        if isinstance(recs, Exception):
            return
        ignored = set(self.win.settings.get("ignored_recommendations") or [])
        recs = [r for r in recs if r["id"] not in ignored]
        score = recommend.health_score(recs)
        self.tiles["recs"].set(len(recs), "suggestions")
        self.tiles["health"].set(f"{score}%", "good" if score >= 80 else "needs attention")
        d, sub = self.donuts["health"]
        d.set_value(score, color="green" if score >= 80 else ("amber" if score >= 55 else "red"))
        sub.set_text(_("Everything looks good") if not recs else f"{len(recs)} suggestion(s)")
        self.win.set_nav_count("recommendations", len([r for r in recs if r["severity"] in ("critical", "warning")]))
        body = self.recs_card.body
        W.clear(body)
        if not recs:
            body.append(W.empty_state("object-select-symbolic", _("Everything looks good")))
            return
        from .recommendations import rec_row
        for i, r in enumerate(recs[:4]):
            body.append(rec_row(self.win, r, last=i == min(3, len(recs) - 1)))

    def _fill_info(self):
        W.clear(self.info_card.body)
        r = self.win.release
        cpu = system.cpu_info()
        s = system.session()
        sb = system.secure_boot_state()
        pairs = [
            ("System", r["pretty"]),
            ("Debian branch", system.BRANCH_LABEL.get(r["branch"], "Unknown") + (f" ({r['debian_codename']})" if r["debian_codename"] else "")),
            ("Kernel", os.uname().release),
            ("Processor", f"{cpu['model']} · {cpu['threads']} threads" + (f" · x86-64-v{cpu['x86_level']}" if cpu["x86_level"] else "")),
            ("Desktop", f"{s['desktop'] or 'unknown'} ({s['type']})"),
            ("Login screen", system.display_manager() or "none"),
            ("Boot", {"bios": "Legacy BIOS", "enabled": "UEFI, Secure Boot on", "disabled": "UEFI, Secure Boot off"}[sb]),
            ("Architecture", system.arch() + (f" · {system.virtualization()} VM" if system.virtualization() else "")),
        ]
        self.info_card.add(W.kv_grid(pairs))
        if system.reboot_required():
            row = W.hbox(8)
            row.append(W.badge("Restart required", "warn"))
            row.append(W.label("A new kernel or core library was installed.", "dim"))
            self.info_card.add(row)

    def _tick(self):
        if not self.get_mapped():
            return True
        idle, total = system.cpu_times()
        pi, pt = self._cpu_prev
        self._cpu_prev = (idle, total)
        if total > pt:
            usage = 100.0 * (1 - (idle - pi) / max(1, total - pt))
            self.cpu_chart.push(usage)
            self.cpu_lbl.set_text(f"{usage:.0f}%")
        mem = system.meminfo()
        if mem.get("MemTotal"):
            used = mem["MemTotal"] - mem.get("MemAvailable", 0)
            d, sub = self.donuts["mem"]
            d.set_value(100 * used / mem["MemTotal"])
            sub.set_text(f"{human_size(used)} of {human_size(mem['MemTotal'])}")
        du = shutil.disk_usage("/")
        d, sub = self.donuts["disk"]
        pct = 100 * du.used / max(1, du.total)
        d.set_value(pct, color="blue" if pct < 85 else "red")
        sub.set_text(f"{human_size(du.free)} free of {human_size(du.total)}")
        pal = theme.PALETTES[theme.resolve_mode(self.win.settings.get("theme"))]
        for dd, _s in self.donuts.values():
            dd.track, dd.text_color = pal["surface3"], pal["text"]
        self.cpu_chart.grid = pal["surface3"]
        return True

    # -------------------------------------------------------------- actions
    def update_system(self):
        self.win.run(Task("Update system", [
            ("Refreshing package lists", "apt_update"),
            ("Installing updates", "apt-get upgrade -y"),
            ("Flatpak updates", "if command -v flatpak >/dev/null; then flatpak update -y --noninteractive; fi"),
        ], refresh={"packages"}))

    def fix_packages(self):
        self.win.run(Task("Repair packages", [
            ("Configuring interrupted packages", "dpkg --configure -a"),
            ("Fixing broken dependencies", "apt-get --fix-broken install -y"),
            ("Checking the package database", "apt-get check"),
        ], refresh={"packages"}))

    def repo_doctor(self):
        self.win.run(Task("Repository Doctor", [("Repository Doctor", "debos_helper doctor")], refresh={"sources", "packages"}))

    def reboot(self):
        self.win.confirm("Restart now?", "Save your work first. Running tasks will be interrupted.",
                         lambda: GLib.spawn_command_line_async("systemctl reboot"), "Restart", danger=True)
