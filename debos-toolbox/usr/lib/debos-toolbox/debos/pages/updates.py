
from gi.repository import Gtk

from .. import APP_NAME, VERSION, widgets as W
from ..core import apt, sources, system
from ..core.tasks import Task
from ..core.util import run
from ..i18n import _
from .base import Page

MIRRORS = [("http://deb.debian.org/debian", "deb.debian.org (worldwide CDN, recommended)"),
           ("https://deb.debian.org/debian", "deb.debian.org over HTTPS"),
           ("http://kartolo.sby.datautama.net.id/debian", "Indonesia (Surabaya)"),
           ("http://ftp.us.debian.org/debian", "United States"), ("http://ftp.de.debian.org/debian", "Germany"),
           ("http://ftp.jp.debian.org/debian", "Japan"), ("http://ftp.au.debian.org/debian", "Australia"),
           ("http://ftp.br.debian.org/debian", "Brazil"), ("http://ftp.pt.debian.org/debian", "Portugal")]


def official_style():
    """Detect how the official sources are written: (uses_alias, components, deb_src, backports, mirror)."""
    ents = [e for e in sources.parse_all() if e.enabled and e.is_official_debian() and not e.is_cdrom()]
    suites = {s for e in ents for s in e.suites}
    comps = []
    for e in ents:
        for c in e.components:
            if c not in comps:
                comps.append(c)
    mirror = next((e.uri.rstrip("/") for e in ents if "security" not in e.uri), sources.DEBIAN_MIRROR)
    return {"alias": bool(suites & {"stable", "testing", "oldstable"}), "components": comps or ["main"],
            "deb_src": any("deb-src" in e.types for e in ents), "backports": any(s.endswith("-backports") for s in suites),
            "mirror": mirror}


class Updates(Page):
    ID = "updates"
    TITLE = "Updates & Release"
    SUBTITLE = "Keep Debian up to date, switch Stable / Testing / Sid"
    ICON = "software-update-available-symbolic"
    KEYWORDS = "upgrade update dist-upgrade full-upgrade stable testing sid unstable release branch security flatpak firmware"

    def build(self):
        self.add_action(W.button("Check for updates", "view-refresh-symbolic", "", self.check))
        self.add_action(W.button(_("Upgrade"), "software-update-available-symbolic", "primary", self.upgrade))
        row = W.hbox(16)
        self.content.append(row)
        self.status = W.Card("Status")
        self.status.set_hexpand(True)
        row.append(self.status)
        auto = W.Card("Automatic maintenance", "Applied immediately with administrator rights.")
        auto.set_size_request(420, -1)
        self.auto_box = auto.body
        row.append(auto)

        self.list_card = self.card("Available updates", None,
                                   [W.button("Full upgrade", kind="", small=True, on_click=self.full_upgrade),
                                    W.button("Flatpak", kind="", small=True, on_click=self.flatpak_update),
                                    W.button("Firmware", kind="", small=True, on_click=self.firmware_update)])
        self.list_box = self.list_card.body

        self._build_branch()

    def _build_branch(self):
        r = self.win.release
        card = self.card("Debian release and branch",
                         "Upgrading Stable → Testing → Sid is supported by Debian; downgrading is not. "
                         "A clean deb822 debian.sources is generated; third-party repositories are not touched.")
        self.branch = r["branch"] if r["branch"] in ("stable", "testing", "sid") else "stable"
        info = W.hbox(10)
        info.append(W.label("Current:", "dim"))
        info.append(W.badge(system.release_badge(r), "primary"))
        card.add(info)
        if r["branch"] in ("oldstable", "oldoldstable"):
            up = W.action_row(f"Upgrade to Debian {system.DEBIAN_RELEASES[system.STABLE]} ({system.STABLE})",
                              "Debian's recommended path: fully upgrade the current release, then switch the sources to the "
                              "new codename and run a full upgrade. Make a Timeshift snapshot or backup first.",
                              [W.button("Start upgrade", kind="primary", small=True, on_click=self.release_upgrade)],
                              "software-update-available-symbolic", "warning")
            card.add(up)
        seg = W.Segmented([("stable", f"Stable ({system.STABLE})"), ("testing", f"Testing ({system.TESTING})"), ("sid", "Unstable (sid)")],
                          self._on_branch, active=self.branch)
        seg.set_halign(Gtk.Align.START)
        card.add(seg)
        style = official_style()
        self.opt_alias = W.switch_row("Follow the rolling name (stable / testing)",
                                      "With the alias, the system moves to the next release automatically.", style["alias"],
                                      lambda v: self._preview())
        self.opt_nonfree = W.switch_row("contrib, non-free and non-free-firmware",
                                        "Needed for most firmware, NVIDIA drivers, Steam and codecs.",
                                        "contrib" in style["components"] or "non-free" in style["components"], lambda v: self._preview())
        self.opt_src = W.switch_row("Source packages (deb-src)", None, style["deb_src"], lambda v: self._preview())
        self.opt_bpo = W.switch_row("Backports (Stable only)", "Newer kernels and software rebuilt for Stable.", style["backports"],
                                    lambda v: self._preview(), last=True)
        for w in (self.opt_alias, self.opt_nonfree, self.opt_src, self.opt_bpo):
            card.add(w)
        mrow = W.hbox(10)
        mrow.append(W.label("Mirror", "row-title"))
        known = [m for m, _l in MIRRORS]
        opts = MIRRORS if style["mirror"] in known else [(style["mirror"], style["mirror"] + " (current)")] + MIRRORS
        self.mirror = W.dropdown(opts, style["mirror"], lambda v: self._preview())
        self.mirror.set_hexpand(True)
        mrow.append(self.mirror)
        card.add(mrow)
        self.preview = Gtk.TextView()
        self.preview.set_monospace(True)
        self.preview.set_editable(False)
        self.preview.set_left_margin(12)
        self.preview.set_top_margin(10)
        self.preview.set_bottom_margin(10)
        self.preview.add_css_class("editor")
        card.add(self.preview)
        btns = W.hbox(8)
        btns.append(W.button("Switch and upgrade", "software-update-available-symbolic", "danger", self.switch_branch))
        btns.append(W.button("Open in APT Sources editor", "document-edit-symbolic", "", self.to_editor))
        card.add(btns)
        self._preview()

    def _on_branch(self, key):
        self.branch = key
        if hasattr(self, "preview"):
            self._preview()

    def generated(self):
        comps = ["main", "contrib", "non-free", "non-free-firmware"] if self.opt_nonfree.switch.get_active() else ["main", "non-free-firmware"]
        return sources.official_sources_text(self.branch, system.STABLE, system.TESTING,
                                             use_alias=self.opt_alias.switch.get_active(), components=comps,
                                             deb_src=self.opt_src.switch.get_active(),
                                             backports=self.opt_bpo.switch.get_active() and self.branch == "stable",
                                             mirror=W.dd_value(self.mirror) or sources.DEBIAN_MIRROR,
                                             app_label=f"{APP_NAME} {VERSION}")

    def _preview(self):
        if hasattr(self, "preview"):
            self.preview.get_buffer().set_text(self.generated())

    # ------------------------------------------------------------- data
    def refresh(self):
        self.loading(self.list_box, "Checking for updates (from the local package lists)…")
        self._fill_auto()
        self.win.data.get("upgrades", lambda: apt.simulate_upgrade(True), self._fill)

    def _fill(self, result):
        W.clear(self.status.body)
        W.clear(self.list_box)
        if isinstance(result, Exception):
            self.list_box.append(W.empty_state("dialog-error-symbolic", "Could not check updates", str(result)))
            return
        items, ok = result
        age = apt.lists_age()
        sec = [u for u in items if u["security"]]
        big = W.label(f"{len(items)} update(s)" if items else "System is up to date", "big-number")
        self.status.add(big)
        when = "never" if age is None else (f"{int(age // 3600)} h ago" if age >= 3600 else f"{int(age // 60)} min ago")
        pairs = [("Security updates", str(len(sec))), ("Package lists refreshed", when),
                 ("Branch", system.BRANCH_LABEL.get(self.win.release["branch"], "?"))]
        if system.reboot_required():
            pairs.append(("Restart", "required to finish updates"))
        self.status.add(W.kv_grid(pairs))
        if age is None or age > 86400:
            self.status.add(W.label("Tip: click 'Check for updates' to download the latest package lists.", "dim", wrap=True))
        self.win.set_nav_count("updates", len(items))
        if not items:
            self.list_box.append(W.empty_state("object-select-symbolic", "No updates available",
                                               "Click 'Check for updates' to refresh the package lists first."))
            return
        for i, u in enumerate(items[:400]):
            badges = [("security", "err")] if u["security"] else []
            origin = u["origin"].split(",")[0].split("[")[0].strip()
            self.list_box.append(W.action_row(u["name"], f"{u['old'] or 'new'} → {u['new']}   ·   {origin}", [],
                                              last=i == len(items) - 1, title_badges=badges))
        if len(items) > 400:
            self.list_box.append(W.label(f"… and {len(items) - 400} more", "dim"))

    def _fill_auto(self):
        W.clear(self.auto_box)
        inst = apt.installed()
        uu = "unattended-upgrades" in inst and run(["systemctl", "is-enabled", "unattended-upgrades"], timeout=5)[1].strip() == "enabled"
        self.auto_box.append(W.switch_row("Automatic security updates", "unattended-upgrades installs Debian security fixes daily.",
                                          uu, self._toggle_unattended))
        timer = run(["systemctl", "is-enabled", "apt-daily.timer"], timeout=5)[1].strip() == "enabled"
        self.auto_box.append(W.switch_row("Refresh package lists daily", "apt-daily.timer keeps update information current.",
                                          timer, self._toggle_daily))
        lb = "apt-listbugs" in inst
        self.auto_box.append(W.switch_row("Warn about critical bugs (apt-listbugs)",
                                          "Recommended on Testing and Sid.", lb, self._toggle_listbugs, last=True))

    # ---------------------------------------------------------- actions
    def check(self):
        self.win.run(Task("Check for updates", [("Refreshing package lists", "apt_update"),
                                                ("Flatpak updates", "if command -v flatpak >/dev/null; then flatpak remote-ls --updates || true; fi")],
                          refresh={"packages", "sources"}))

    def upgrade(self):
        self.win.run(Task("Install updates", [("Refreshing package lists", "apt_update"), ("Upgrading packages", "apt-get upgrade -y"),
                                              ("Flatpak", "if command -v flatpak >/dev/null; then flatpak update -y --noninteractive; fi")],
                          refresh={"packages"}))

    def full_upgrade(self):
        self.win.run(Task("Full upgrade", [("Refreshing package lists", "apt_update"),
                                           ("Full upgrade (review removals before answering)", "apt-get full-upgrade"),
                                           ("Removing unneeded packages", "apt-get autoremove --purge -y")], refresh={"packages"}),
                     confirm="A full upgrade can install new packages and remove conflicting ones. You will see the list and can "
                             "cancel in the console.")

    def flatpak_update(self):
        self.win.run(Task("Update Flatpak apps", [("Updating", ["ensure_pkg flatpak", "flatpak update -y --noninteractive"])],
                          refresh={"flatpak"}))

    def firmware_update(self):
        self.win.run(Task("Firmware updates (fwupd)", [("Installing fwupd", "ensure_pkg fwupd"),
                                                      ("Refreshing metadata", "fwupdmgr refresh --force || true"),
                                                      ("Available updates", "fwupdmgr get-updates || true"),
                                                      ("Installing", "fwupdmgr update || true")]))

    def _toggle_unattended(self, on):
        if on:
            steps = [("Installing unattended-upgrades", "apt_install unattended-upgrades apt-listchanges"),
                     ("Enabling", ["echo 'unattended-upgrades unattended-upgrades/enable_auto_updates boolean true' | debconf-set-selections",
                                   "DEBIAN_FRONTEND=noninteractive dpkg-reconfigure -f noninteractive unattended-upgrades",
                                   "systemctl enable --now unattended-upgrades"])]
        else:
            steps = [("Disabling", ["systemctl disable --now unattended-upgrades",
                                    "printf 'APT::Periodic::Unattended-Upgrade \"0\";\\n' > /etc/apt/apt.conf.d/21debos-unattended"])]
        self.win.run(Task("Automatic security updates", steps, refresh={"packages"}))

    def _toggle_daily(self, on):
        cmd = "systemctl enable --now apt-daily.timer apt-daily-upgrade.timer" if on else "systemctl disable --now apt-daily.timer"
        self.win.run(Task("Daily package list refresh", [("systemd timers", cmd)]))

    def _toggle_listbugs(self, on):
        steps = [("apt-listbugs", "apt_install apt-listbugs apt-listchanges" if on else "apt-get purge -y apt-listbugs")]
        self.win.run(Task("apt-listbugs", steps, refresh={"packages"}))

    def to_editor(self):
        page = self.win.pages["sources"]
        self.win.navigate("sources")
        page.load_text("/etc/apt/sources.list.d/debian.sources", self.generated())

    def _write_steps(self, text, target_branch):
        steps = [("Backing up APT configuration", "backup_apt_sources"),
                 ("Writing debian.sources", ["debos_helper write-official <<'DEBOS_EOF'", text.rstrip("\n"), "DEBOS_EOF"])]
        if target_branch in ("testing", "sid"):
            steps.append(("Installing apt-listbugs and apt-listchanges", ["apt_update || true", "apt_install apt-listbugs apt-listchanges"]))
        steps += [("Refreshing package lists", "apt-get update --allow-releaseinfo-change"),
                  ("Minimal upgrade first", "apt-get upgrade --without-new-pkgs"),
                  ("Full upgrade (review removals before answering)", "apt-get full-upgrade"),
                  ("Removing obsolete packages", "apt-get autoremove --purge"),
                  ("Done", "ok 'Restart the computer to finish the upgrade.'")]
        return steps

    def switch_branch(self):
        r = self.win.release
        if r["is_lmde"]:
            self.win.info("Not available on LMDE", "LMDE manages its own repositories; switching the Debian branch would break it.")
            return
        target = self.branch
        cur = system.BRANCH_RANK.get(r["branch"], 2)
        msg = (f"Switch to Debian {system.BRANCH_LABEL[target]} and run a full upgrade?\n\n"
               "• Make a backup or Timeshift snapshot first.\n• Your current sources are backed up to /var/backups/debos-toolbox.\n"
               "• The upgrade asks for confirmation in the console; read the list of packages to be removed.")
        danger = False
        if system.BRANCH_RANK[target] < cur:
            danger = True
            msg = (f"WARNING: going from {system.BRANCH_LABEL.get(r['branch'])} to {system.BRANCH_LABEL[target]} is a DOWNGRADE. "
                   "Debian does not support downgrades: packages stay at their newer versions until the target branch catches "
                   "up, and mixing can break the system.\n\n") + msg
        task = Task(f"Switch to Debian {system.BRANCH_LABEL[target]}", self._write_steps(self.generated(), target),
                    refresh={"sources", "packages"})
        self.win.run(task, confirm=msg, danger=danger)

    def release_upgrade(self):
        r = self.win.release
        text = sources.official_sources_text("stable", system.STABLE, system.TESTING, components=official_style()["components"]
                                             if "main" in official_style()["components"] else None)
        steps = [("Pre-flight checks", [
            "dpkg --audit | grep -q . && fail 'Fix broken packages first (Recommendations > Repair).' || true",
            "HELD=$(apt-mark showhold); [ -z \"$HELD\" ] || warn \"Held packages: $HELD\"",
            '[ "$(free_space_gb /)" -ge 5 ] || fail "At least 5 GB of free space is needed on /."',
        ]), ("Upgrading the current release fully", ["apt_update", "apt-get full-upgrade -y"])] + self._write_steps(text, "stable")
        self.win.run(Task(f"Upgrade Debian {r['debian_codename']} → {system.STABLE}", steps, refresh={"sources", "packages"}),
                     confirm=f"Upgrade from Debian {r['debian_number']} ({r['debian_codename']}) to Debian "
                             f"{system.DEBIAN_RELEASES[system.STABLE]} ({system.STABLE})?\nThis takes a while and needs a restart. "
                             "Third-party repositories stay as they are; review them afterwards on the Repositories page.",
                     danger=True)
