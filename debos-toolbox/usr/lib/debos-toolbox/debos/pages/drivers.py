from gi.repository import Gtk

from .. import widgets as W
from ..core import apt, drivers, system
from ..core.tasks import Task
from ..core.util import shq
from ..i18n import _
from .base import Page

CAT_INFO = {"gpu": ("Graphics", "video-display-symbolic", "blue"), "wifi": ("Wi-Fi", "network-wireless-symbolic", "cyan"),
            "ethernet": ("Ethernet", "network-wired-symbolic", "teal"), "audio": ("Audio", "audio-card-symbolic", "pink"),
            "wireless": ("Wireless", "bluetooth-symbolic", "violet"), "storage": ("Storage", "drive-harddisk-symbolic", "slate"),
            "usb": ("USB controllers", "media-removable-symbolic", "slate")}


def load_hardware(win):
    inst = apt.installed()
    cpu = system.cpu_info()
    res = drivers.scan(inst, cpu["vendor"], system.virtualization(), system.secure_boot_state())
    res["isenkram"] = drivers.isenkram_suggestions()
    res["installed"] = inst
    res["cpu"] = cpu
    return res


class Drivers(Page):
    ID = "drivers"
    TITLE = "Drivers"
    SUBTITLE = "Detect hardware and install the right drivers"
    ICON = "video-display-symbolic"
    KEYWORDS = "driver nvidia amd intel gpu wifi firmware bluetooth microcode printer hardware isenkram"

    def build(self):
        self.add_action(W.button(_("Install") + " selected", "system-software-install-symbolic", "primary", self.install))
        self.hw = W.vbox(16)
        self.content.append(self.hw)
        self.recs_card = self.card("Recommended drivers and firmware",
                                   "Detected from your PCI devices, CPU and the Debian hardware database. contrib, non-free and "
                                   "non-free-firmware are enabled automatically when a package needs them.")
        tools = self.card("Tools")
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(4)
        for text, steps in (
                ("nvidia-detect", [("nvidia-detect", ["ensure_pkg nvidia-detect", "nvidia-detect || true"])]),
                ("Find missing firmware", [("isenkram", ["apt_install isenkram-cli", "isenkram-autoinstall-firmware || true",
                                                         "echo; info 'Packages suggested for this hardware:'; isenkram-lookup || true"])]),
                ("Hardware report (inxi)", [("inxi", ["ensure_pkg inxi", "inxi -Fxxz"])]),
                ("GPU / Vulkan info", [("Tools", ["apt_install_available mesa-utils vulkan-tools vainfo", "glxinfo -B || true",
                                                  "vulkaninfo --summary 2>/dev/null || true", "vainfo 2>/dev/null || true"])]),
                ("Firmware updates (fwupd)", [("fwupd", ["ensure_pkg fwupd", "fwupdmgr refresh --force || true", "fwupdmgr get-updates || true",
                                                         "fwupdmgr update || true"])]),
                ("Enable 32-bit (i386)", [("multiarch", ["dpkg --add-architecture i386", "apt_update"])]),
                ("Kernel messages", [("dmesg", "dmesg --level=err,warn | tail -n 80 || true")])):
            flow.insert(W.button(text, kind="", small=True, on_click=lambda t=text, s=steps: self.win.run(Task(t, s, refresh={"drivers", "packages"}))), -1)
        tools.add(flow)

    def refresh(self):
        self.loading(self.hw, "Scanning hardware…")
        self.loading(self.recs_card.body)
        self.win.data.get("hardware", lambda: load_hardware(self.win), self._fill)

    def on_data_changed(self, groups):
        self.win.data.cache.pop("hardware", None)
        super().on_data_changed(groups)

    def _fill(self, res):
        W.clear(self.hw)
        W.clear(self.recs_card.body)
        if isinstance(res, Exception):
            self.hw.append(W.empty_state("dialog-error-symbolic", "Hardware scan failed", str(res)))
            return
        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_max_children_per_line(3)
        grid.set_min_children_per_line(1)
        grid.set_homogeneous(True)
        grid.set_row_spacing(16)
        grid.set_column_spacing(16)
        self.hw.append(grid)
        cpu = res["cpu"]
        c = W.Card(css="card")
        head = W.hbox(12)
        head.append(W.AppIcon("orange", "computer-symbolic", (), None, 46))
        head.append(W.label("Processor", "card-title"))
        c.add(head)
        c.add(W.label(cpu["model"], "row-title", wrap=True))
        c.add(W.label(f"{cpu['threads']} threads · {cpu['vendor'].upper() or 'unknown'}" + (f" · x86-64-v{cpu['x86_level']}" if cpu["x86_level"] else ""), "dim"))
        grid.insert(c, -1)
        for cat in ("gpu", "wifi", "ethernet", "audio", "wireless"):
            devs = [d for d in res["devices"] if d["category"] == cat]
            if not devs:
                continue
            title, icon, color = CAT_INFO[cat]
            c = W.Card(css="card")
            head = W.hbox(12)
            head.append(W.AppIcon(color, icon, (), None, 46))
            head.append(W.label(title, "card-title"))
            c.add(head)
            for d in devs:
                c.add(W.label(f"{d['vendor']} {d['name']}", "row-title", wrap=True))
                drv = d["driver"]
                row = W.hbox(6)
                row.append(W.badge(f"driver: {drv}" if drv else "no driver", "ok" if drv else "err"))
                row.append(W.label(f"[{d['vendor_id']}:{d['device_id']}]", "dim mono"))
                c.add(row)
            grid.insert(c, -1)

        self.checks = []
        recs = res["recs"]
        body = self.recs_card.body
        if not recs:
            body.append(W.empty_state("object-select-symbolic", "No additional drivers needed"))
        for i, r in enumerate(recs):
            installed = r["status"] == "installed"
            badges = [("✓ " + _("Installed"), "ok")] if installed else [(_("Recommended"), "warn")]
            if r["nonfree"] and not installed:
                badges.append(("non-free", "muted"))
            row = W.check_row(r["title"], r["detail"] + (f"\nPackages: {' '.join(r['packages'])}" if r["packages"] else ""),
                              not installed and r["category"] in ("gpu", "network", "audio", "cpu"), badges, last=i == len(recs) - 1)
            if installed and not r.get("script"):
                row.check.set_active(False)
                row.check.set_sensitive(False)
            self.checks.append((row.check, r))
            body.append(row)
        isk = res.get("isenkram")
        if isk:
            missing = [p for p in isk if p not in res["installed"]]
            if missing:
                body.append(W.action_row("Debian hardware database (isenkram)", "Suggested for your devices: " + ", ".join(missing),
                                         [W.button(_("Install"), kind="primary", small=True, on_click=lambda m=missing: self.win.run(Task(
                                             "Install isenkram suggestions", [("Enable components", "enable_components"), ("Refresh", "apt_update"),
                                                                              ("Install", f"apt_install_available {' '.join(shq(p) for p in m)}")],
                                             refresh={"drivers", "packages"})))], "starred-symbolic", "tip"))

    def install(self):
        chosen = [r for chk, r in getattr(self, "checks", []) if chk.get_active()]
        if not chosen:
            self.win.toast(_("Nothing selected."))
            return
        steps = [("Enabling contrib, non-free and non-free-firmware", "enable_components"), ("Refreshing package lists", "apt_update")]
        for r in chosen:
            if r.get("script"):
                steps.append((r["title"], r["script"]))
            elif r["packages"]:
                steps.append((r["title"], f"apt_install_available {' '.join(shq(p) for p in r['packages'])}"))
        steps.append(("Finished", "ok 'Restart the computer to load new drivers and firmware.'"))
        self.win.run(Task("Install drivers", steps, refresh={"drivers", "packages"}),
                     confirm="Install:\n• " + "\n• ".join(r["title"] for r in chosen))
