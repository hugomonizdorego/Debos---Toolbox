"""Recommendation engine: inspects the system and suggests fixes.

Every recommendation is a dict:
  id, severity (critical|warning|info|tip), title, detail,
  action: ("page", page_id) or ("task", title, steps, root)
  label: text of the action button, safe: True if it can run in "Fix all"
"""

import os
import shutil

from . import apt, kernels, sources, system
from .util import human_size, path_size, run

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "tip": 3}


def _service_active(name):
    return run(["systemctl", "is-active", name], timeout=5)[1].strip() == "active"


def _service_enabled(name):
    return run(["systemctl", "is-enabled", name], timeout=5)[1].strip() in ("enabled", "static", "enabled-runtime")


def collect(release, home, installed=None):
    installed = installed if installed is not None else apt.installed()
    recs = []

    def add(rid, severity, title, detail, action, label="Fix", safe=False):
        recs.append({"id": rid, "severity": severity, "title": title, "detail": detail, "action": action,
                     "label": label, "safe": safe})

    branch = release.get("branch")

    # ---------------------------------------------------------------- packages
    audit = apt.broken()
    if audit:
        add("broken", "critical", "Broken or half-installed packages",
            "dpkg reports packages that are not fully installed. This blocks other installs.",
            ("task", "Repair packages", [("Configuring interrupted packages", "dpkg --configure -a"),
                                         ("Fixing dependencies", "apt-get --fix-broken install -y")], True), safe=True)
    upgrades, _ok = apt.simulate_upgrade(full=True)
    if upgrades:
        sec = sum(1 for u in upgrades if u["security"])
        add("updates", "warning" if sec else "info", f"{len(upgrades)} update(s) available" + (f", {sec} security" if sec else ""),
            "Install updates to get bug and security fixes.", ("page", "updates"), label="Review")
    age = apt.lists_age()
    if age is None or age > 7 * 86400:
        add("stale-lists", "info", "Package lists are out of date",
            "The package information has not been refreshed for more than a week." if age else "Package lists were never downloaded.",
            ("task", "Refresh package lists", [("apt-get update", "apt_update")], True), label="Refresh", safe=True)
    held = apt.held()
    if held:
        add("held", "info", f"{len(held)} package(s) on hold", "Held packages are never upgraded: " + ", ".join(held[:8]),
            ("page", "updates"), label="Review")

    # ----------------------------------------------------------------- kernels
    inv = kernels.inventory()
    old = kernels.old_kernels(inv)
    if old:
        add("old-kernels", "info", f"{len(old)} old kernel(s) can be removed",
            f"They use about {human_size(sum(k['size'] for k in old))}. The running and newest kernels are kept.",
            ("task", "Remove old kernels", kernels.remove_steps(old), True), label="Remove", safe=True)
    manual = [k for k in inv["kernels"] if not k["managed"] and not k["running"]]
    if manual:
        add("manual-kernels", "warning", "Kernels installed outside APT",
            "Found kernels built with 'make install' (older Debos versions did this): " +
            ", ".join(k["version"] for k in manual) + ". APT cannot update or remove them.",
            ("page", "kernels"), label="Manage")
    if system.reboot_required():
        add("reboot", "warning", "Restart required", "A newer kernel or core library is installed. Restart to use it.",
            ("page", "dashboard"), label="Later")

    # ------------------------------------------------------------ repositories
    entries = sources.parse_all()
    for issue in sources.entry_issues(entries, release.get("debian_codename"), branch):
        if issue["id"] in ("cdrom", "conflict-signed-by", "duplicate", "missing-key"):
            add(f"repo-{issue['id']}", "critical" if issue["severity"] == "error" else "warning", issue["title"], issue["detail"],
                ("task", "Repository Doctor", [("Repository Doctor", "debos_helper doctor")], True), safe=True)
        elif issue["id"] == "nonfree-firmware":
            add("nonfree-firmware", "warning", issue["title"], issue["detail"],
                ("task", "Enable non-free-firmware", [("Enable components", "enable_components non-free-firmware"), ("Refresh", "apt_update")], True),
                label="Enable", safe=True)
        elif issue["id"] in ("mixed-suites", "no-official", "trusted-yes"):
            add(f"repo-{issue['id']}", "warning" if issue["severity"] != "error" else "critical", issue["title"], issue["detail"],
                ("page", "repositories"), label="Review")
    # keep only one Repository Doctor entry
    seen_doctor = False
    deduped = []
    for r in recs:
        if r["action"][0] == "task" and r["action"][1] == "Repository Doctor":
            if seen_doctor:
                continue
            seen_doctor = True
        deduped.append(r)
    recs[:] = deduped
    if os.path.isfile(sources.LEGACY_KEYRING) and os.path.getsize(sources.LEGACY_KEYRING) > 0:
        add("legacy-keyring", "warning", "Repository keys in the deprecated trusted.gpg",
            "apt prints 'Key is stored in legacy trusted.gpg keyring'. Move the keys to trusted.gpg.d.",
            ("task", "Migrate repository keys", [("Migrating keys", "debos_helper migrate-keys"), ("Refresh", "apt_update")], True),
            safe=True)
    comps = {c for e in entries if e.enabled and e.is_official_debian() for c in e.components}
    if entries and "contrib" not in comps and branch in ("stable", "testing", "sid", "oldstable"):
        add("components", "tip", "contrib and non-free are disabled",
            "Steam, NVIDIA drivers, Microsoft fonts and many firmware packages need them.",
            ("task", "Enable contrib and non-free", [("Enable components", "enable_components"), ("Refresh", "apt_update")], True),
            label="Enable")

    # ----------------------------------------------------------------- hardware
    cpu = system.cpu_info()
    micro = {"intel": "intel-microcode", "amd": "amd64-microcode"}.get(cpu["vendor"])
    if micro and micro not in installed and not system.virtualization():
        add("microcode", "warning", "CPU microcode updates are missing",
            f"{micro} provides security fixes for your {cpu['vendor'].upper()} processor (non-free-firmware).",
            ("task", f"Install {micro}", [("Enable non-free-firmware", "enable_components non-free-firmware"), ("Refresh", "apt_update"),
                                          (f"Install {micro}", f"apt_install {micro}")], True), label="Install", safe=True)
    try:
        from . import drivers
        scan = drivers.scan(installed, cpu["vendor"], system.virtualization(), system.secure_boot_state())
        for r in scan["recs"]:
            if r["status"] == "recommended" and r["id"] not in ("microcode", "printing") and not r["id"].startswith("nodriver"):
                add(f"driver-{r['id']}", "warning" if r["category"] in ("gpu", "network", "audio") else "tip",
                    r["title"], r["detail"], ("page", "drivers"), label="Open")
            elif r["id"].startswith("nodriver"):
                add(f"driver-{r['id']}", "warning", r["title"], r["detail"], ("page", "drivers"), label="Open")
    except Exception:
        pass

    # ------------------------------------------------------------------ system
    usage = shutil.disk_usage("/")
    pct = usage.used * 100 // max(usage.total, 1)
    if pct >= 90:
        add("disk-full", "critical", f"Disk almost full ({pct}% used)", f"Only {human_size(usage.free)} free on /.",
            ("page", "cleaner"), label="Clean")
    apt_cache = apt.apt_cache_size()
    journal = path_size("/var/log/journal")
    thumbs = path_size(os.path.join(home, ".cache/thumbnails"))
    reclaim = apt_cache + max(0, journal - 200 * 2 ** 20) + thumbs
    if reclaim > 500 * 2 ** 20:
        add("reclaim", "info", f"{human_size(reclaim)} can be freed", "Package cache, old logs and thumbnails.",
            ("page", "cleaner"), label="Clean")
    if branch == "stable" and "unattended-upgrades" not in installed:
        add("unattended", "tip", "Automatic security updates are off",
            "unattended-upgrades installs Debian security fixes automatically every day.",
            ("page", "systemtweaks"), label="Open")
    if "ufw" not in installed and "firewalld" not in installed:
        add("firewall", "tip", "No firewall installed", "UFW blocks unwanted incoming connections with one switch.",
            ("task", "Enable firewall", [("Install UFW", "apt_install ufw"), ("Enable UFW",
                                          ["ufw default deny incoming", "ufw default allow outgoing", "ufw --force enable"])], True),
            label="Enable")
    mem = system.meminfo()
    swap_total = mem.get("SwapTotal", 0)
    if mem.get("MemTotal", 0) < 8 * 2 ** 30 and swap_total == 0:
        add("zram", "tip", "No swap configured", "With less than 8 GB RAM, compressed ZRAM swap prevents freezes.",
            ("task", "Enable ZRAM", [("Install zram-tools", "apt_install zram-tools"),
                                     ("Configure", ["printf 'ALGO=zstd\\nPERCENT=50\\nPRIORITY=100\\n' > /etc/default/zramswap",
                                                    "systemctl restart zramswap"])], True), label="Enable")
    if system.has_ssd() and not _service_enabled("fstrim.timer"):
        add("fstrim", "tip", "Weekly SSD TRIM is disabled", "TRIM keeps SSDs fast.",
            ("task", "Enable TRIM", [("Enable fstrim.timer", "systemctl enable --now fstrim.timer")], True), label="Enable", safe=True)
    if "flatpak" in installed:
        code, text = run(["flatpak", "remotes", "--columns=name"], timeout=10)
        if "flathub" not in text:
            add("flathub", "tip", "Flathub is not configured", "Flatpak is installed but has no app source.",
                ("task", "Add Flathub", [("Add Flathub", "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo")], True),
                label="Add", safe=True)
    if branch in ("testing", "sid"):
        if "apt-listbugs" not in installed:
            add("listbugs", "warning" if branch == "sid" else "tip", "apt-listbugs is not installed",
                "It warns about release-critical bugs before an upgrade installs them - essential on Testing and Sid.",
                ("task", "Install apt-listbugs", [("Install", "apt_install apt-listbugs apt-listchanges")], True), label="Install", safe=True)
        if "timeshift" not in installed and "snapper" not in installed:
            add("snapshots", "tip", "No system snapshot tool", "Timeshift lets you roll back a broken upgrade.",
                ("task", "Install Timeshift", [("Install", "apt_install timeshift")], True), label="Install")
    code, text = run(["systemctl", "--failed", "--no-legend", "--plain"], timeout=10)
    failed = [l.split()[0] for l in text.splitlines() if l.strip()]
    if failed:
        add("failed-units", "warning", f"{len(failed)} service(s) failed", ", ".join(failed[:6]), ("page", "systemtweaks"), label="Details")
    if release.get("branch") in ("oldstable", "oldoldstable"):
        add("old-release", "warning", f"Debian {release.get('debian_codename')} is not the current stable release",
            f"Debian {system.DEBIAN_RELEASES[system.STABLE]} ({system.STABLE}) is available.", ("page", "updates"), label="Upgrade")
    recs.sort(key=lambda r: SEVERITY_ORDER.get(r["severity"], 9))
    return recs


def health_score(recs):
    penalty = {"critical": 22, "warning": 9, "info": 3, "tip": 1}
    return max(0, 100 - sum(penalty.get(r["severity"], 0) for r in recs))
