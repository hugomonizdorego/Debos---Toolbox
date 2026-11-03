import glob
import os
import re
import shutil


from .. import widgets as W
from ..core.tasks import Task
from ..core.util import read_file, run, shq
from ..i18n import _
from .base import Page

PROTECTED = {"apt", "dpkg", "bash", "coreutils", "systemd", "dbus", "sudo", "network-manager", "polkitd", "pkexec",
             "gnome-shell", "gnome-session", "gnome-control-center", "plasma-desktop", "plasma-workspace", "systemsettings",
             "xfce4-session", "xfce4-panel", "xfce4-settings", "cinnamon", "mate-panel", "lxqt-session", "nautilus", "dolphin",
             "thunar", "nemo", "caja", "pcmanfm", "pcmanfm-qt", "debos-toolbox", "xdg-utils", "desktop-file-utils", "gdm3",
             "sddm", "lightdm", "budgie-desktop", "xterm"}


def scan_apps():
    names = {}
    for path in glob.glob("/usr/share/applications/*.desktop"):
        text = read_file(path)
        if "[Desktop Entry]" not in text or re.search(r"^NoDisplay\s*=\s*true", text, re.M):
            continue
        m = re.search(r"^Name\s*=\s*(.+)$", text, re.M)
        icon = re.search(r"^Icon\s*=\s*(.+)$", text, re.M)
        names[path] = (m.group(1).strip() if m else os.path.basename(path), icon.group(1).strip() if icon else "")
    apps = {}
    paths = list(names)
    for i in range(0, len(paths), 150):
        code, text = run(["dpkg-query", "-S"] + paths[i:i + 150], timeout=60)
        for line in text.splitlines():
            if ": " not in line:
                continue
            pkgs, path = line.split(": ", 1)
            for pkg in pkgs.split(","):
                pkg = pkg.strip().split(":")[0]
                if pkg and pkg not in PROTECTED:
                    nm, ic = names.get(path.strip(), (pkg, ""))
                    entry = apps.setdefault(("deb", pkg), {"names": set(), "icon": ic})
                    entry["names"].add(nm)
    code, text = run(["dpkg-query", "-W", "-f=${Package} ${Essential} ${Priority}\n"], timeout=30)
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 3 and (p[1] == "yes" or p[2] in ("required", "important")):
            apps.pop(("deb", p[0]), None)
    if shutil.which("flatpak"):
        code, text = run(["flatpak", "list", "--app", "--columns=application,name"], timeout=30)
        for line in text.splitlines():
            parts = line.split("\t")
            if parts and parts[0]:
                apps[("flatpak", parts[0])] = {"names": {parts[1] if len(parts) > 1 else parts[0]}, "icon": parts[0]}
    return sorted(((k, p, ", ".join(sorted(v["names"])), v["icon"]) for (k, p), v in apps.items()), key=lambda x: x[2].lower())


class Uninstall(Page):
    ID = "uninstall"
    TITLE = "Uninstall"
    SUBTITLE = "Remove installed applications"
    ICON = "list-remove-symbolic"
    KEYWORDS = "remove uninstall delete purge application app"

    def build(self):
        self.add_action(W.button(_("Remove"), "user-trash-symbolic", "danger", self.remove))
        top = W.hbox(10)
        self.search = W.search_entry("Filter installed apps")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", lambda *_a: self.render())
        top.append(self.search)
        self.count = W.label("", "dim")
        top.append(self.count)
        self.content.append(top)
        self.card = W.Card()
        self.content.append(self.card)
        self.items, self.checks = [], {}

    def refresh(self):
        self.loading(self.card.body, "Scanning installed applications…")
        self.win.async_call(scan_apps, self._loaded)

    def _loaded(self, items):
        self.items = [] if isinstance(items, Exception) else items
        self.render()

    def render(self):
        W.clear(self.card.body)
        q = self.search.get_text().strip().lower()
        shown = [it for it in self.items if not q or q in it[2].lower() or q in it[1].lower()]
        self.count.set_text(f"{len(shown)} of {len(self.items)} apps")
        if not shown:
            self.card.add(W.empty_state("system-search-symbolic", "No applications found"))
            return
        for i, (kind, pkg, name, icon) in enumerate(shown):
            key = (kind, pkg)
            chk = self.checks.get(key)
            row = W.check_row(name, f"{'Flatpak' if kind == 'flatpak' else 'Debian package'}: {pkg}",
                              chk.get_active() if chk else False, last=i == len(shown) - 1)
            ic = W.icon([icon, "application-x-executable-symbolic"], 32)
            row.insert_child_after(ic, row.check)
            self.checks[key] = row.check
            self.card.add(row)

    def remove(self):
        sel = [k for k, c in self.checks.items() if c.get_active()]
        if not sel:
            self.win.toast(_("Nothing selected."))
            return
        debs = [p for k, p in sel if k == "deb"]
        fps = [p for k, p in sel if k == "flatpak"]
        steps = []
        if debs:
            steps.append(("Removing packages (check the list before confirming)",
                          [f"apt-get purge {' '.join(shq(d) for d in debs)}", "apt-get autoremove --purge"]))
        if fps:
            steps.append(("Removing Flatpak apps", [f"flatpak uninstall -y --noninteractive {' '.join(shq(f) for f in fps)}",
                                                    "flatpak uninstall --unused -y --noninteractive || true"]))
        self.checks = {}
        self.win.run(Task(f"Remove {len(sel)} app(s)", steps, refresh={"packages", "flatpak"}),
                     confirm="Remove:\n• " + "\n• ".join(p for _k, p in sel[:30]))
