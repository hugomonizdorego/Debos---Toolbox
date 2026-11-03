"""System cleaner ("janitor").

Item ideas follow Ubuntu Cleaner / Ubuntu Tweak's Janitor (APT cache, unneeded
packages, old kernels, package configs, thumbnails, browser caches) plus
Debian-specific ones (journal, rotated logs, crash dumps, Flatpak leftovers,
kernel build trees).  Scanning never needs root; cleaning user items runs as
the desktop user, system items as root.
"""

import glob
import os
import re
import subprocess
import time

from . import apt, kernels
from .util import path_size, run, shq

BROWSERS = [
    # id, title, cache dirs relative to $HOME, process names
    ("firefox", "Firefox", [".cache/mozilla"], ["firefox", "firefox-esr", "firefox-bin"]),
    ("chromium", "Chromium", [".cache/chromium"], ["chromium"]),
    ("chrome", "Google Chrome", [".cache/google-chrome"], ["chrome"]),
    ("brave", "Brave", [".cache/BraveSoftware"], ["brave"]),
    ("vivaldi", "Vivaldi", [".cache/vivaldi"], ["vivaldi-bin"]),
    ("opera", "Opera", [".cache/opera"], ["opera"]),
    ("edge", "Microsoft Edge", [".cache/microsoft-edge"], ["msedge"]),
    ("librewolf", "LibreWolf", [".cache/librewolf"], ["librewolf"]),
    ("floorp", "Floorp", [".cache/floorp"], ["floorp"]),
]

DEV_CACHES = [".cache/pip", ".npm/_cacache", ".cache/yarn", ".cache/go-build", ".cache/mesa_shader_cache",
              ".cache/gstreamer-1.0", ".cache/thumbnails-old", ".cache/winetricks", ".cache/composer", ".cache/deno",
              ".cache/typescript", ".cache/electron", ".cache/node-gyp"]


class Item:
    def __init__(self, iid, section, title, desc, root, default=True, icon="edit-clear-all-symbolic"):
        self.id, self.section, self.title, self.desc = iid, section, title, desc
        self.root, self.default, self.icon = root, default, icon


ITEMS = [
    Item("apt_cache", "System", "Package cache", "Downloaded .deb files in /var/cache/apt (apt-get clean).", True, True, "package-x-generic-symbolic"),
    Item("autoremove", "System", "Unneeded packages", "Dependencies nothing needs anymore (apt autoremove).", True, True, "list-remove-symbolic"),
    Item("old_kernels", "System", "Old kernels", "Kernels other than the running one and the newest of each type.", True, True, "computer-symbolic"),
    Item("residual", "System", "Package configs", "Settings left behind by removed packages (dpkg state 'rc').", True, True, "document-properties-symbolic"),
    Item("journal", "System", "System journal", "Shrink systemd logs to 200 MB / 14 days.", True, True, "document-open-symbolic"),
    Item("old_logs", "System", "Rotated logs", "Compressed and rotated files in /var/log.", True, False, "document-revert-symbolic"),
    Item("crash", "System", "Crash reports and core dumps", "/var/crash and systemd-coredump files.", True, True, "dialog-warning-symbolic"),
    Item("var_tmp", "System", "Old temporary files", "Files in /var/tmp untouched for more than 14 days.", True, False, "folder-symbolic"),
    Item("module_leftovers", "System", "Leftover kernel modules", "Module folders in /lib/modules of kernels that are no longer installed (often left by DKMS).", True, False, "application-x-addon-symbolic"),
    Item("kernel_build", "System", "Kernel build files", "Source trees and packages left by kernel builds in /var/tmp/debos-kernel.", True, True, "applications-engineering-symbolic"),
    Item("flatpak_unused", "System", "Unused Flatpak runtimes", "Runtimes no installed app needs anymore.", True, True, "view-app-grid-symbolic"),
    Item("thumbnails", "Personal", "Thumbnail cache", "Image previews; regenerated when needed.", False, True, "camera-photo-symbolic"),
    Item("trash", "Personal", "Trash", "Empty your Trash (cannot be undone).", False, False, "user-trash-symbolic"),
    Item("recent", "Personal", "Recent files history", "The list of recently opened documents (privacy).", False, False, "document-open-symbolic"),
    Item("dev_caches", "Personal", "Developer and app caches", "pip, npm, yarn, Go, shader and other caches.", False, True, "applications-utilities-symbolic"),
    Item("flatpak_caches", "Personal", "Flatpak app caches", "Cache folders of Flatpak applications (~/.var/app/*/cache).", False, True, "view-app-grid-symbolic"),
    Item("installers", "Personal", "Old installers in Downloads", ".deb, .rpm and .run files in ~/Downloads older than 30 days.", False, False, "folder-download-symbolic"),
] + [Item(f"browser_{bid}", "Browsers", f"{title} cache", "Cached web content; you stay logged in.", False, True, "web-browser-symbolic")
     for bid, title, _dirs, _procs in BROWSERS]


def _running(names):
    for name in names:
        try:
            if subprocess.run(["pgrep", "-x", name], capture_output=True, timeout=5).returncode == 0:
                return True
        except Exception:
            pass
    return False


def leftover_module_dirs():
    """Versions in /lib/modules without a kernel image and not owned by any package."""
    running = os.uname().release
    dirs = {}
    for base in ("/usr/lib/modules", "/lib/modules"):
        for d in glob.glob(base + "/*"):
            if os.path.isdir(d) and not os.path.islink(d):
                dirs.setdefault(os.path.basename(d), d)
    cands = []
    for ver, d in dirs.items():
        if ver == running or not re.match(r"^[0-9][A-Za-z0-9._+~-]*$", ver):
            continue
        # kernels kept on the EFI partition (systemd-boot, kernel-install, UKIs) count as installed
        if os.path.exists(f"/boot/vmlinuz-{ver}") or glob.glob(f"/boot/efi/*/{ver}") or glob.glob(f"/efi/*/{ver}") \
                or glob.glob(f"/boot/efi/EFI/Linux/*{ver}*.efi"):
            continue
        cands.append(ver)
    if not cands:
        return []
    _rc, text = run(["dpkg-query", "-S"] + [f"{b}/{v}" for v in cands for b in ("/lib/modules", "/usr/lib/modules")], timeout=30)
    owned = {line.split(": ", 1)[1].strip().rstrip("/").rsplit("/", 1)[-1] for line in text.splitlines() if ": " in line}
    return [(v, dirs[v]) for v in sorted(cands) if v not in owned]


def kernel_build_running():
    return subprocess.run(["pgrep", "-f", "make.* bindeb-pkg"], capture_output=True).returncode == 0


def _sum(paths):
    return sum(path_size(p) for p in paths)


def _inside(home, path):
    real = os.path.realpath(path)
    return real.startswith(os.path.realpath(home) + os.sep)


def scan_item(item, home):
    """Return a result dict: size, count, details, paths, packages, warning, skip."""
    r = {"size": 0, "count": 0, "details": [], "paths": [], "packages": [], "warning": None, "skip": False}
    iid = item.id
    if iid == "apt_cache":
        r["size"] = apt.apt_cache_size()
        r["count"] = len(glob.glob("/var/cache/apt/archives/*.deb"))
    elif iid == "autoremove":
        pkgs = apt.autoremovable()
        sizes = apt.installed_sizes(pkgs)
        r.update(packages=pkgs, count=len(pkgs), size=sum(sizes.values()), details=pkgs[:200])
    elif iid == "old_kernels":
        inv = kernels.inventory()
        old = kernels.old_kernels(inv)
        r.update(count=len(old), size=sum(k["size"] for k in old), details=[f"{k['version']} ({k['kind']})" for k in old])
        r["kernels"] = old
    elif iid == "residual":
        pkgs = apt.residual_configs()
        r.update(packages=pkgs, count=len(pkgs), details=pkgs[:200])
    elif iid == "journal":
        size = path_size("/var/log/journal")
        r.update(size=max(0, size - 200 * 1024 * 1024), count=1 if size > 200 * 1024 * 1024 else 0,
                 details=[f"Journal currently uses {size // (1024 * 1024)} MB"])
    elif iid == "old_logs":
        files = []
        for pat in ("/var/log/*.gz", "/var/log/*.[0-9]", "/var/log/*.old", "/var/log/*/*.gz", "/var/log/*/*.[0-9]",
                    "/var/log/*/*.old"):
            # samba names live per-client logs "log.<address>": those are not rotated files
            files += [f for f in glob.glob(pat) if os.path.isfile(f) and not os.path.basename(f).startswith("log.")]
        r.update(paths=files, count=len(files), size=_sum(files), details=files[:200])
    elif iid == "crash":
        files = glob.glob("/var/crash/*") + glob.glob("/var/lib/systemd/coredump/*")
        r.update(paths=files, count=len(files), size=_sum(files), details=files[:200])
    elif iid == "var_tmp":
        cutoff = time.time() - 14 * 86400
        files = []
        for base, dirs, names in os.walk("/var/tmp", onerror=lambda e: None):
            dirs[:] = [d for d in dirs if not d.startswith(("systemd-private-", "debos-kernel"))]
            for n in names:
                p = os.path.join(base, n)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if st.st_atime < cutoff and st.st_mtime < cutoff:
                    files.append(p)
                    r["size"] += st.st_size
        r.update(count=len(files), details=files[:200])
    elif iid == "module_leftovers":
        found = leftover_module_dirs()
        r.update(count=len(found), size=_sum([d for _v, d in found]), details=[d for _v, d in found])
        r["versions"] = [v for v, _d in found]
    elif iid == "kernel_build":
        r["size"] = path_size("/var/tmp/debos-kernel")
        r["count"] = 1 if r["size"] else 0
        if r["size"] and kernel_build_running():
            r["warning"] = "A kernel build is running"
            r["skip"] = True
    elif iid == "flatpak_unused":
        r["count"] = 1 if os.path.isdir("/var/lib/flatpak/runtime") else 0
        r["details"] = ["Unused runtimes are detected by flatpak itself while cleaning."]
        r["unknown_size"] = True
    elif iid == "thumbnails":
        p = os.path.join(home, ".cache/thumbnails")
        r.update(paths=[p] if os.path.isdir(p) else [], size=path_size(p))
        r["count"] = 1 if r["size"] else 0
    elif iid == "trash":
        paths = [p for p in (os.path.join(home, ".local/share/Trash/files"), os.path.join(home, ".local/share/Trash/info")) if os.path.isdir(p)]
        r.update(paths=[os.path.join(p, "*") for p in paths], size=_sum(paths))
        r["count"] = sum(len(os.listdir(p)) for p in paths[:1]) if paths else 0
    elif iid == "recent":
        files = [p for p in glob.glob(os.path.join(home, ".local/share/recently-used.xbel*")) if os.path.isfile(p)]
        r.update(paths=files, size=_sum(files), count=len(files))
    elif iid == "dev_caches":
        dirs = [os.path.join(home, d) for d in DEV_CACHES if os.path.isdir(os.path.join(home, d))]
        r.update(paths=dirs, size=_sum(dirs), count=len(dirs), details=dirs)
    elif iid == "flatpak_caches":
        dirs = [d for d in glob.glob(os.path.join(home, ".var/app/*/cache")) if os.path.isdir(d)]
        r.update(paths=dirs, size=_sum(dirs), count=len(dirs), details=dirs[:200])
    elif iid == "installers":
        cutoff = time.time() - 30 * 86400
        dl = os.path.join(home, "Downloads")
        files = []
        for pat in ("*.deb", "*.rpm", "*.run"):
            for f in glob.glob(os.path.join(dl, pat)):
                try:
                    if os.path.getmtime(f) < cutoff:
                        files.append(f)
                except OSError:
                    pass
        r.update(paths=files, size=_sum(files), count=len(files), details=files)
    elif iid.startswith("browser_"):
        bid = iid[len("browser_"):]
        _b, _t, dirs, procs = next(b for b in BROWSERS if b[0] == bid)
        paths = [os.path.join(home, d) for d in dirs if os.path.isdir(os.path.join(home, d))]
        r.update(paths=paths, size=_sum(paths), count=len(paths))
        if paths and _running(procs):
            r["warning"] = "Close the browser first"
            r["skip"] = True
    # user paths must stay inside the home directory
    if not item.root:
        r["paths"] = [p for p in r["paths"] if _inside(home, p.rstrip("*").rstrip("/") or p)]
    return r


def clean_steps(selected):
    """selected: list of (item, result).  Returns (steps, needs_root)."""
    steps, root = [], False
    for item, r in selected:
        iid = item.id
        if item.root:
            root = True
        if iid == "apt_cache":
            steps.append((item.title, ["apt-get clean", "apt-get autoclean -y"]))
        elif iid == "autoremove":
            steps.append((item.title, "apt-get autoremove --purge -y"))
        elif iid == "old_kernels" and r.get("kernels"):
            steps += kernels.remove_steps(r["kernels"])
        elif iid == "residual" and r["packages"]:
            steps.append((item.title, f"dpkg --purge {' '.join(shq(p) for p in r['packages'])}"))
        elif iid == "journal":
            steps.append((item.title, "journalctl --vacuum-size=200M --vacuum-time=14d"))
        elif iid == "old_logs":
            steps.append((item.title, "find /var/log -maxdepth 2 -type f \\( -name '*.gz' -o -name '*.[0-9]' -o -name '*.old' \\) "
                                      "-not -name 'log.*' -delete"))
        elif iid == "crash":
            steps.append((item.title, ["rm -rf --one-file-system /var/crash/* 2>/dev/null || true",
                                       "rm -f /var/lib/systemd/coredump/* 2>/dev/null || true"]))
        elif iid == "module_leftovers" and r.get("versions"):
            steps.append((item.title, f"debos_helper remove-kernel-files {' '.join(shq(v) for v in r['versions'])}"))
        elif iid == "var_tmp":
            steps.append((item.title, "find /var/tmp -mindepth 1 -xdev -atime +14 -mtime +14 "
                                      "-not -path '/var/tmp/systemd-private-*' -not -path '/var/tmp/debos-kernel*' -delete 2>/dev/null || true"))
        elif iid == "kernel_build":
            steps.append((item.title, ['if pgrep -f "make.* bindeb-pkg" >/dev/null; then fail "A kernel build is running."; fi',
                                       "rm -rf /var/tmp/debos-kernel"]))
        elif iid == "flatpak_unused":
            steps.append((item.title, ["if command -v flatpak >/dev/null; then",
                                       "  flatpak uninstall --unused -y --noninteractive || true",
                                       "  as_user flatpak uninstall --user --unused -y --noninteractive || true",
                                       "fi"]))
        elif r["paths"]:
            quoted = []
            for p in r["paths"]:
                if p.endswith("/*"):
                    quoted.append(shq(p[:-2]) + "/*")   # glob must stay unquoted
                else:
                    quoted.append(shq(p))
            steps.append((item.title, f"as_user rm -rf --one-file-system -- {' '.join(quoted)}"))
    return steps, root


def scan_all(home, progress=None):
    results = {}
    for i, item in enumerate(ITEMS):
        try:
            results[item.id] = scan_item(item, home)
        except Exception as exc:  # keep scanning the rest
            results[item.id] = {"size": 0, "count": 0, "details": [str(exc)], "paths": [], "packages": [],
                                "warning": "Scan failed", "skip": True}
        if progress:
            progress((i + 1) / len(ITEMS), item.title)
    return results
