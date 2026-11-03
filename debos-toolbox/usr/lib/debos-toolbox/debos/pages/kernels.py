import os
import re
import shutil

from gi.repository import Gtk

from .. import widgets as W
from ..core import kernels as K, system
from ..core.tasks import Task
from ..core.util import human_size
from ..i18n import _
from .base import Page

XANMOD = [
    ("linux-xanmod-x64v2", "XanMod MAIN (x64v2)", "For CPUs from about 2009-2013 (Nehalem, Bulldozer).", 2),
    ("linux-xanmod-x64v3", "XanMod MAIN (x64v3)", "For modern CPUs (Haswell and newer, all Ryzen).", 3),
    ("linux-xanmod-edge-x64v3", "XanMod EDGE (x64v3)", "Newest mainline-based XanMod.", 3),
    ("linux-xanmod-lts-x64v3", "XanMod LTS (x64v3)", "Long-term support XanMod.", 3),
    ("linux-xanmod-rt-x64v3", "XanMod RT (x64v3)", "PREEMPT_RT real-time kernel for audio and low latency.", 3),
]


class Kernels(Page):
    ID = "kernels"
    TITLE = "Kernels"
    SUBTITLE = "Install optimized kernels, build from kernel.org, remove old ones"
    ICON = "computer-symbolic"
    KEYWORDS = "kernel linux xanmod liquorix libre mainline kernel.org compile build backports remove old grub"

    def build(self):
        self.add_action(W.button("Update GRUB", "view-refresh-symbolic", "", lambda: self.win.run(Task(
            "Update GRUB", [("update-grub", "update-grub")]))))
        self.seg = W.Segmented([("installed", "Installed"), ("install", "Install"), ("build", "Build from kernel.org")], self._tab)
        self.seg.set_halign(Gtk.Align.START)
        self.content.append(self.seg)
        self.stack = Gtk.Stack()
        self.content.append(self.stack)
        self.installed_box = W.vbox(16)
        self.install_box = W.vbox(16)
        self.build_box = W.vbox(16)
        self.stack.add_named(self.installed_box, "installed")
        self.stack.add_named(self.install_box, "install")
        self.stack.add_named(self.build_box, "build")
        self.cpu = system.cpu_info()
        self.sb = system.secure_boot_state()
        self._build_install()
        self._build_build()

    def _tab(self, key):
        self.stack.set_visible_child_name(key)

    # ------------------------------------------------------------ installed
    def refresh(self):
        self.loading(self.installed_box, "Reading installed kernels…")
        self.win.data.get("kernels", K.inventory, self._fill_installed, force=True)

    def _fill_installed(self, inv):
        box = self.installed_box
        W.clear(box)
        if isinstance(inv, Exception):
            box.append(W.empty_state("dialog-error-symbolic", "Could not read kernels", str(inv)))
            return
        self.inv = inv
        manual = [k for k in inv["kernels"] if not k["managed"]]
        if manual:
            box.append(W.action_row("Kernels installed outside APT were found",
                                    "Older versions of Debos built kernels with 'make install'. They are listed below as 'Manual install' "
                                    "and can be removed here safely.", [], "dialog-warning-symbolic", "warning"))
        card = W.Card("Installed kernels", f"Running: {inv['running']}. The running kernel can't be removed; keep at least one fallback.",
                      [W.button("Remove old kernels", kind="", small=True, on_click=self.remove_old),
                       W.button("Remove selected", kind="danger", small=True, on_click=self.remove_selected)])
        box.append(card)
        self.kchecks = {}
        ks = inv["kernels"]
        if not ks:
            card.add(W.empty_state("computer-symbolic", "No kernels found"))
        metas = {m["package"] for m in inv["metas"]}
        for i, k in enumerate(ks):
            badges = [(k["kind"], "primary" if k["managed"] else "warn")]
            if k["running"]:
                badges.append(("● running", "ok"))
            if k["newest"] and not k["running"]:
                badges.append(("newest", "info"))
            sub = f"{human_size(k['size'])} · " + (f"package {k['package']} {k['pkg_version']}" if k["managed"] else "not managed by APT: " + ", ".join(k["files"][:3]))
            if k["headers"]:
                sub += " · headers installed"
            row = W.check_row(k["version"], sub, False, badges, last=i == len(ks) - 1)
            if k["running"]:
                row.check.set_sensitive(False)
            self.kchecks[k["version"]] = (row.check, k)
            card.add(row)
        mcard = W.Card("Kernel meta-packages", "They pull in new kernel versions automatically. Removing them stops kernel updates.")
        if inv["metas"]:
            for i, m in enumerate(inv["metas"]):
                mcard.add(W.action_row(m["package"], m["version"], [], "package-x-generic-symbolic", "info", last=i == len(inv["metas"]) - 1))
        else:
            mcard.add(W.action_row("No kernel meta-package installed",
                                   "Without linux-image-" + system.arch() + " you will not receive Debian kernel updates.",
                                   [W.button("Install", kind="primary", small=True, on_click=lambda: self.win.run(Task(
                                       "Install the Debian kernel", K.debian_steps(), refresh={"kernels", "packages"})))],
                                   "dialog-warning-symbolic", "warning"))
        box.append(mcard)
        del metas

    def _remove(self, chosen):
        chosen = [k for k in chosen if not k["running"]]
        if not chosen:
            self.win.toast(_("Nothing selected."))
            return
        remaining = [k for k in self.inv["kernels"] if k not in chosen]
        warn = "" if any(k["managed"] or not k["running"] for k in remaining) and len(remaining) > 1 else \
            "\n\nOnly the running kernel will remain - consider keeping one fallback kernel."
        meta_warn = ""
        newest_debian = next((k for k in self.inv["kernels"] if k["kind"] == "Debian"), None)
        if newest_debian in chosen:
            meta_warn = "\n\nYou are removing the newest Debian kernel: apt will also remove linux-image-" + system.arch() + \
                        " and kernel updates stop until you reinstall it."
        self.win.run(Task(f"Remove {len(chosen)} kernel(s)", K.remove_steps(chosen), refresh={"kernels", "packages", "cleaner"}),
                     confirm="Remove:\n• " + "\n• ".join(f"{k['version']} ({k['kind']})" for k in chosen) + warn + meta_warn,
                     danger=bool(meta_warn))

    def remove_selected(self):
        self._remove([k for chk, k in self.kchecks.values() if chk.get_active()])

    def remove_old(self):
        self._remove(K.old_kernels(self.inv))

    # --------------------------------------------------------------- install
    def _build_install(self):
        box = self.install_box
        lvl = self.cpu["x86_level"]
        intro = f"Your CPU: {self.cpu['model']} · " + (f"x86-64-v{lvl}" if lvl else system.arch())
        if self.sb == "enabled":
            intro += ". Secure Boot is ON: only Debian's own kernels are signed; XanMod, Liquorix, Linux-libre and self-built kernels will not boot unless you disable Secure Boot."
        box.append(W.label(intro, "dim", wrap=True))
        deb = W.Card("Debian kernels", "Signed for Secure Boot and updated together with your system.")
        rel = self.win.release
        rows = [("Debian standard kernel", f"linux-image-{system.arch()} - the default, newest kernel of your release.",
                 lambda: self.win.run(Task("Install the Debian kernel", K.debian_steps(), refresh={"kernels", "packages"})), True),
                ("Debian real-time kernel", "PREEMPT_RT kernel from Debian for audio production and robotics.",
                 lambda: self.win.run(Task("Install the Debian RT kernel", K.debian_steps("rt-"), refresh={"kernels", "packages"})), True),
                ("Backports kernel", f"Newer kernel from {rel['debian_codename']}-backports (Stable only) for recent hardware.",
                 lambda: self.win.run(Task("Install the backports kernel", K.backports_steps(), refresh={"kernels", "packages", "sources"}, stop_on_error=True)),
                 rel["branch"] in ("stable", "oldstable"))]
        for i, (title, sub, cb, ok) in enumerate(rows):
            btn = W.button(_("Install"), kind="primary", small=True, on_click=cb)
            btn.set_sensitive(ok)
            deb.add(W.action_row(title, sub, [btn], "computer-symbolic", "tip", last=i == len(rows) - 1,
                                 title_badges=[] if ok else [("Stable only", "muted")]))
        box.append(deb)
        x = W.Card("XanMod", "Performance-tuned kernels for desktop, gaming and multimedia (amd64). Repository: deb.xanmod.org.")
        for i, (pkg, title, sub, need) in enumerate(XANMOD):
            badges = []
            if lvl and lvl < need:
                badges.append(("CPU not supported", "err"))
            elif pkg == "linux-xanmod-x64v3" and lvl >= 3 or pkg == "linux-xanmod-x64v2" and lvl == 2:
                badges.append((_("Recommended"), "ok"))
            btn = W.button(_("Install"), kind="primary", small=True,
                           on_click=lambda p=pkg: self.win.run(Task(f"Install {p}", K.xanmod_steps(p), refresh={"kernels", "packages", "sources"}, stop_on_error=True)))
            btn.set_sensitive(system.arch() == "amd64" and (not lvl or lvl >= need))
            x.add(W.action_row(title, sub, [btn], "power-profile-performance-symbolic", "info", last=i == len(XANMOD) - 1, title_badges=badges))
        box.append(x)
        o = W.Card("Other kernels")
        o.add(W.action_row("Liquorix", "Low-latency kernel tuned for desktop responsiveness and gaming (amd64). Uses extrepo when available.",
                           [W.button(_("Install"), kind="primary", small=True,
                                     on_click=lambda: self.win.run(Task("Install Liquorix", K.liquorix_steps(), refresh={"kernels", "packages", "sources"}, stop_on_error=True)))],
                           "applications-games-symbolic", "info"))
        o.add(W.action_row("Linux-libre", "100% free kernel without firmware blobs, from the FSFLA freesh repository. Some Wi-Fi and GPUs will stop working.",
                           [W.button("LTS", small=True, on_click=lambda: self.win.run(Task("Install Linux-libre LTS", K.libre_steps(True), refresh={"kernels", "packages"}))),
                            W.button(_("Install"), kind="primary", small=True,
                                     on_click=lambda: self.win.run(Task("Install Linux-libre", K.libre_steps(), refresh={"kernels", "packages"})))],
                           "security-high-symbolic", "info", last=True))
        box.append(o)

    # ----------------------------------------------------------------- build
    def _build_build(self):
        box = self.build_box
        card = W.Card("Build a kernel from kernel.org",
                      "Downloads the official source, checks its signature, configures it from your running kernel and builds real Debian "
                      "packages (bindeb-pkg). The result can be updated and removed with APT like any other kernel.")
        box.append(card)
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(14)
        r = 0
        grid.attach(W.label("Release", "row-title"), 0, r, 1, 1)
        self.b_release = W.dropdown([("stable", "Latest stable"), ("longterm", "Latest longterm (LTS)"), ("custom", "Specific version…")], "stable",
                                    lambda v: self.b_version.set_sensitive(v == "custom"))
        grid.attach(self.b_release, 1, r, 1, 1)
        self.b_version = Gtk.Entry()
        self.b_version.set_placeholder_text("e.g. 6.12.10")
        self.b_version.set_sensitive(False)
        grid.attach(self.b_version, 2, r, 1, 1)
        r += 1
        grid.attach(W.label("Configuration", "row-title"), 0, r, 1, 1)
        self.b_config = W.dropdown([("running", "Copy the running kernel's configuration (recommended)"), ("defconfig", "Upstream defaults")], "running")
        grid.attach(self.b_config, 1, r, 2, 1)
        r += 1
        grid.attach(W.label("Name suffix", "row-title"), 0, r, 1, 1)
        self.b_suffix = Gtk.Entry()
        self.b_suffix.set_text("-debos")
        grid.attach(self.b_suffix, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Parallel jobs", "row-title"), 0, r, 1, 1)
        self.b_jobs = Gtk.SpinButton.new_with_range(1, max(1, os.cpu_count() or 1), 1)
        self.b_jobs.set_value(os.cpu_count() or 1)
        grid.attach(self.b_jobs, 1, r, 1, 1)
        card.add(grid)
        self.b_local = W.switch_row("Fast build: only modules that are loaded now (localmodconfig)",
                                    "Builds in a fraction of the time, but hardware that is not plugged in now may not work later.", False)
        self.b_keep = W.switch_row("Keep the source tree", "Useful for rebuilding; needs several GB.", False, last=True)
        card.add(self.b_local)
        card.add(self.b_keep)
        free = shutil.disk_usage("/var/tmp").free if os.path.isdir("/var/tmp") else 0
        card.add(W.label(f"Free space in /var/tmp: {human_size(free)} (needs about 20 GB, 8 GB for a fast build). "
                         f"Expect 30 minutes to several hours with {os.cpu_count()} threads.", "dim", wrap=True))
        card.add(W.button("Build and install", "applications-engineering-symbolic", "primary", self.build_kernel))

    def build_kernel(self):
        rel = W.dd_value(self.b_release)
        ver = self.b_version.get_text().strip() if rel == "custom" else ""
        if rel == "custom" and not re.match(r"^\d+\.\d+(\.\d+)?$", ver):
            self.win.toast("Enter a version like 6.12 or 6.12.10", "err")
            return
        suffix = self.b_suffix.get_text().strip() or "-debos"
        if not suffix.startswith("-"):
            suffix = "-" + suffix
        try:
            steps = K.mainline_steps(moniker="longterm" if rel == "longterm" else "stable", version=ver,
                                     config=W.dd_value(self.b_config), localmod=self.b_local.switch.get_active(),
                                     suffix=suffix.lower(), jobs=int(self.b_jobs.get_value()), keep_source=self.b_keep.switch.get_active())
        except ValueError as exc:
            self.win.toast(str(exc), "err")
            return
        msg = "This downloads about 150 MB and compiles the kernel. You can keep using the computer; the console shows the progress."
        if self.sb == "enabled":
            msg += "\n\nSecure Boot is ON: the new kernel is unsigned and will not boot until you disable Secure Boot."
        self.win.run(Task("Build kernel from kernel.org", steps, refresh={"kernels", "packages", "cleaner"}, stop_on_error=True), confirm=msg)
