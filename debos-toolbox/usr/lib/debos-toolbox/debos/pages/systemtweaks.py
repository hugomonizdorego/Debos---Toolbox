import os
import shutil

from gi.repository import Gtk

from .. import widgets as W
from ..core import apt, system
from ..core.tasks import Task
from ..core.util import read_file, run, user_groups
from .base import Page


def enabled(unit):
    return run(["systemctl", "is-enabled", unit], timeout=5)[1].strip() in ("enabled", "static", "alias")


def active(unit):
    return run(["systemctl", "is-active", unit], timeout=5)[1].strip() == "active"


def tweak_state(ctx):
    inst = apt.installed()
    swappiness = read_file("/proc/sys/vm/swappiness").strip()
    return {
        "zram": "zram-tools" in inst and active("zramswap"),
        "swappiness": swappiness == "10",
        "swappiness_value": swappiness,
        "fstrim": enabled("fstrim.timer"),
        "earlyoom": "earlyoom" in inst and active("earlyoom"),
        "tlp": "tlp" in inst and enabled("tlp"),
        "timeshift": "timeshift" in inst,
        "i386": "i386" in apt.foreign_architectures(),
        "aptfancy": os.path.exists("/etc/apt/apt.conf.d/99debos-ui"),
        "journal": os.path.exists("/etc/systemd/journald.conf.d/99-debos.conf"),
        "nobeep": os.path.exists("/etc/modprobe.d/debos-nobeep.conf"),
        "sudo": "sudo" in user_groups(ctx.user),
        "flathub": shutil.which("flatpak") is not None and "flathub" in run(["flatpak", "remotes"], timeout=10)[1],
        "failed": [l.split()[0] for l in run(["systemctl", "--failed", "--no-legend", "--plain"], timeout=10)[1].splitlines() if l.strip()],
        "laptop": system.is_laptop(),
        "ssd": system.has_ssd(),
    }


TWEAKS = [
    ("zram", "Compressed RAM swap (ZRAM)", "zram-tools with zstd, 50% of RAM. Prevents freezes on low-memory systems.",
     [("Installing zram-tools", "apt_install zram-tools"), ("Configuring", ["printf 'ALGO=zstd\\nPERCENT=50\\nPRIORITY=100\\n' > /etc/default/zramswap",
                                                                           "systemctl restart zramswap", "swapon --show"])],
     [("Disabling ZRAM", ["systemctl disable --now zramswap || true"])]),
    ("swappiness", "Lower swappiness (10)", "Keep applications in RAM longer; good for desktops.",
     [("Setting vm.swappiness=10", ["echo 'vm.swappiness=10' > /etc/sysctl.d/99-debos-swappiness.conf", "sysctl -p /etc/sysctl.d/99-debos-swappiness.conf"])],
     [("Restoring the default", ["rm -f /etc/sysctl.d/99-debos-swappiness.conf", "sysctl -w vm.swappiness=60"])]),
    ("fstrim", "Weekly SSD TRIM", "fstrim.timer keeps SSDs fast.", [("Enabling", "systemctl enable --now fstrim.timer")],
     [("Disabling", "systemctl disable --now fstrim.timer")]),
    ("earlyoom", "earlyoom", "Ends the biggest process before memory runs out, instead of freezing.",
     [("Installing", "apt_install earlyoom"), ("Enabling", "systemctl enable --now earlyoom")], [("Disabling", "systemctl disable --now earlyoom")]),
    ("tlp", "TLP battery saver (laptops)", "Advanced power management; replaces power-profiles-daemon.",
     [("Installing", "apt_install tlp tlp-rdw"), ("Enabling", "systemctl enable --now tlp")], [("Removing", "apt-get purge -y tlp tlp-rdw")]),
    ("timeshift", "Timeshift snapshots", "Roll back the system after a bad upgrade.", [("Installing", "apt_install timeshift")],
     [("Removing", "apt-get purge -y timeshift")]),
    ("i386", "32-bit software (i386)", "Needed by Steam and many Wine programs.", [("Adding i386", ["dpkg --add-architecture i386", "apt_update"])],
     [("Removing i386", ["dpkg --remove-architecture i386 || fail 'Remove all :i386 packages first.'", "apt_update"])]),
    ("aptfancy", "Colourful APT with progress bar", "Coloured output and a progress bar for apt and dpkg.",
     [("Configuring", "printf 'Dpkg::Progress-Fancy \"1\";\\nAPT::Color \"1\";\\n' > /etc/apt/apt.conf.d/99debos-ui")],
     [("Restoring", "rm -f /etc/apt/apt.conf.d/99debos-ui")]),
    ("journal", "Limit the system journal to 500 MB", "Stops logs from filling the disk.",
     [("Configuring", ["mkdir -p /etc/systemd/journald.conf.d", "printf '[Journal]\\nSystemMaxUse=500M\\n' > /etc/systemd/journald.conf.d/99-debos.conf",
                       "systemctl restart systemd-journald"])],
     [("Restoring", ["rm -f /etc/systemd/journald.conf.d/99-debos.conf", "systemctl restart systemd-journald"])]),
    ("nobeep", "Silence the PC speaker beep", "Blacklists the pcspkr module.",
     [("Configuring", ["echo 'blacklist pcspkr' > /etc/modprobe.d/debos-nobeep.conf", "modprobe -r pcspkr 2>/dev/null || true"])],
     [("Restoring", "rm -f /etc/modprobe.d/debos-nobeep.conf")]),
    ("sudo", "Administrator rights for your user (sudo group)", "Lets you use sudo with your own password. Log out afterwards.",
     [("Adding to sudo", ["ensure_pkg sudo", 'usermod -aG sudo "$TARGET_USER"'])], [("Removing from sudo", 'gpasswd -d "$TARGET_USER" sudo')]),
    ("flathub", "Flatpak with Flathub", "Thousands of desktop apps in a sandbox; adds the store plugin for GNOME Software / Discover.",
     [("Installing Flatpak", "apt_install flatpak"),
      ("Adding Flathub", "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"),
      ("Store plugins", ["is_installed gnome-software && apt_install gnome-software-plugin-flatpak || true",
                         "is_installed plasma-discover && apt_install plasma-discover-backend-flatpak || true"])],
     [("Removing Flathub", "flatpak remote-delete --force flathub || true")]),
]


class SystemTweaks(Page):
    ID = "systemtweaks"
    TITLE = "System Tweaks"
    SUBTITLE = "Performance, security and maintenance tweaks"
    ICON = "emblem-system-symbolic"
    KEYWORDS = "tweak zram swap swappiness trim ssd earlyoom tlp battery timeshift i386 journal sudo flathub diagnostics logs report"

    def build(self):
        self.card_tweaks = self.card("Tweaks", "Each switch shows the current state and applies the change immediately.")
        diag = self.card("Diagnostics and logs")
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(4)
        for text, steps in (
                ("Boot errors", [("journalctl", "journalctl -b -p 3 --no-pager | tail -n 150")]),
                ("Failed services", [("systemctl", "systemctl --failed --no-pager")]),
                ("Boot time", [("systemd-analyze", ["systemd-analyze", "systemd-analyze blame --no-pager | head -n 25"])]),
                ("Disk usage", [("df", ["df -hT -x tmpfs -x devtmpfs", "du -xh --max-depth=1 /var \"$TARGET_HOME\" 2>/dev/null | sort -rh | head -n 20"])]),
                ("Held and foreign packages", [("apt", ["apt-mark showhold", "apt list --installed 2>/dev/null | grep ',local]' || ok 'none'"])]),
                ("Debos task log", [("log", "tail -n 300 /var/log/debos-toolbox/tasks.log 2>/dev/null | sed 's/\\x1b\\[[0-9;]*m//g' || echo 'No log yet.'")]),
                ("System report (to ~/debos-report.txt)", [("Report", [
                    'OUT="$TARGET_HOME/debos-report.txt"',
                    '{ echo "== Debos - Toolbox system report $(date)"; cat /etc/os-release; echo; uname -a; echo; '
                    'lscpu | head -n 20; echo; free -h; echo; df -hT -x tmpfs -x devtmpfs; echo; lspci -nnk; echo; '
                    'apt-cache policy | head -n 60; echo; systemctl --failed --no-pager; echo; journalctl -b -p 3 --no-pager | tail -n 60; } > "$OUT" 2>&1',
                    'chown "$TARGET_USER" "$OUT"', 'ok "Report written to $OUT"'])]),
                ("Root shell", [("Interactive root shell (type exit to finish)", "bash -i")])):
            flow.insert(W.button(text, kind="", small=True, on_click=lambda t=text, s=steps: self.win.run(Task(t, s))), -1)
        diag.add(flow)
        self.failed_box = W.vbox(6)
        diag.add(self.failed_box)

    def refresh(self):
        self.loading(self.card_tweaks.body)
        self.win.async_call(lambda: tweak_state(self.win.ctx), self._fill)

    def _fill(self, st):
        body = self.card_tweaks.body
        W.clear(body)
        if isinstance(st, Exception):
            body.append(W.label(str(st), "err-text"))
            return
        shown = [t for t in TWEAKS if not (t[0] == "tlp" and not st["laptop"]) and not (t[0] == "fstrim" and not st["ssd"])]
        for i, (key, title, desc, on_steps, off_steps) in enumerate(shown):
            sub = desc
            if key == "swappiness":
                sub += f" Current value: {st['swappiness_value']}."
            body.append(W.switch_row(title, sub, st.get(key, False),
                                     lambda on, k=key, t=title, a=on_steps, b=off_steps: self._apply(k, t, on, a, b),
                                     last=i == len(shown) - 1))
        W.clear(self.failed_box)
        if st["failed"]:
            self.failed_box.append(W.label("Failed services: " + ", ".join(st["failed"]), "err-text", wrap=True))

    def _apply(self, key, title, on, on_steps, off_steps):
        self.win.run(Task(f"{title}: {'on' if on else 'off'}", on_steps if on else off_steps, refresh={"tweaks", "packages"}))
        return True
