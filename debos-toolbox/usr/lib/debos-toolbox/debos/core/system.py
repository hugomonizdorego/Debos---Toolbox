"""Detect the Debian release/branch and basic facts about the machine."""

import glob
import os
import re
import shutil

from . import sources
from .util import out, read_file, run

DEBIAN_RELEASES = {"bullseye": "11", "bookworm": "12", "trixie": "13", "forky": "14", "duke": "15"}
OLDOLDSTABLE, OLDSTABLE, STABLE, TESTING = "bullseye", "bookworm", "trixie", "forky"
# Codenames that third-party vendors (Docker, XanMod, WineHQ, VirtualBox...) publish packages for.
VENDOR_CODENAMES = ("bookworm", "trixie")
BRANCH_RANK = {"oldoldstable": 0, "oldstable": 1, "stable": 2, "testing": 3, "sid": 4}
BRANCH_LABEL = {"oldoldstable": "Oldoldstable", "oldstable": "Oldstable", "stable": "Stable",
                "testing": "Testing", "sid": "Unstable (Sid)", "unknown": "Unknown"}


def parse_os_release(text=None):
    if text is None:
        text = read_file("/etc/os-release") or read_file("/usr/lib/os-release")
    data = {}
    for line in text.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def detect_release(os_release=None, debian_version=None, suites=None):
    """Return a dict describing the distribution and Debian branch.

    os_release / debian_version / suites can be injected for testing.
    """
    osr = parse_os_release(os_release)
    dv = (read_file("/etc/debian_version") if debian_version is None else debian_version).strip()
    info = {
        "pretty": osr.get("PRETTY_NAME", "Unknown Linux"),
        "id": osr.get("ID", ""),
        "id_like": osr.get("ID_LIKE", ""),
        "version_id": osr.get("VERSION_ID", ""),
        "codename": osr.get("VERSION_CODENAME", ""),
        "debian_codename": osr.get("DEBIAN_CODENAME", "") or osr.get("VERSION_CODENAME", ""),
        "debian_version": dv,
        "branch": "unknown",
        "is_debian": osr.get("ID", "") == "debian",
        "is_lmde": osr.get("ID", "") == "linuxmint" and bool(osr.get("DEBIAN_CODENAME")),
        "is_debian_family": osr.get("ID", "") == "debian" or "debian" in osr.get("ID_LIKE", "").split(),
        "has_apt": shutil.which("apt-get") is not None,
    }
    codename = info["debian_codename"]
    rolling = info["is_debian"] and ("sid" in dv or not info["version_id"])
    if rolling:
        if suites is None:
            suites = {sources.suite_base(s) for e in sources.parse_all() if e.enabled and e.is_official_debian()
                      for s in e.suites}
        if suites & {"sid", "unstable"}:
            info["branch"], info["debian_codename"] = "sid", "sid"
        else:
            info["branch"] = "testing"
            if not codename or codename == "sid":
                info["debian_codename"] = TESTING
    elif codename == STABLE:
        info["branch"] = "stable"
    elif codename == OLDSTABLE:
        info["branch"] = "oldstable"
    elif codename == OLDOLDSTABLE:
        info["branch"] = "oldoldstable"
    elif codename == TESTING:
        info["branch"] = "testing"
    dc = info["debian_codename"]
    info["vendor_codename"] = dc if dc in VENDOR_CODENAMES else STABLE
    info["debian_number"] = DEBIAN_RELEASES.get(dc, "")
    return info


def release_badge(info):
    if info["is_lmde"]:
        num = DEBIAN_RELEASES.get(info["debian_codename"], "?")
        return f"{info['pretty']} · Debian {num} base"
    if info["is_debian"]:
        if info["branch"] == "sid":
            return "Debian sid · Unstable"
        num = info["debian_number"]
        label = BRANCH_LABEL.get(info["branch"], "")
        return (f"Debian {num} ({info['debian_codename']}) · {label}" if num else f"Debian {info['debian_codename']} · {label}").strip(" ·")
    return info["pretty"]


def arch():
    return out(["dpkg", "--print-architecture"]) or os.uname().machine


def secure_boot_state():
    """'enabled', 'disabled' or 'bios'."""
    if not os.path.isdir("/sys/firmware/efi"):
        return "bios"
    for path in glob.glob("/sys/firmware/efi/efivars/SecureBoot-*"):
        try:
            with open(path, "rb") as fh:
                return "enabled" if fh.read()[-1] == 1 else "disabled"
        except OSError:
            break
    return "disabled"


def cpu_info():
    model, vendor, flags = "Unknown CPU", "", set()
    for line in read_file("/proc/cpuinfo").splitlines():
        if line.startswith("model name") and model == "Unknown CPU":
            model = re.sub(r"\s+", " ", line.split(":", 1)[1].strip())
        elif line.startswith("vendor_id") and not vendor:
            vendor = line.split(":", 1)[1].strip()
        elif line.startswith("flags") and not flags:
            flags = set(line.split(":", 1)[1].split())
        elif line.startswith(("Hardware", "Model")) and model == "Unknown CPU" and ":" in line:
            model = line.split(":", 1)[1].strip()
    level = 0
    if "lm" in flags:
        level = 1
        if {"cx16", "lahf_lm", "popcnt", "sse4_1", "sse4_2", "ssse3"} <= flags:
            level = 2
            if {"avx", "avx2", "bmi1", "bmi2", "f16c", "fma", "abm", "movbe", "xsave"} <= flags:
                level = 3
                if {"avx512f", "avx512bw", "avx512cd", "avx512dq", "avx512vl"} <= flags:
                    level = 4
    return {"model": model, "vendor": {"GenuineIntel": "intel", "AuthenticAMD": "amd"}.get(vendor, vendor.lower()),
            "threads": os.cpu_count() or 1, "x86_level": level}


def meminfo():
    mem = {}
    for line in read_file("/proc/meminfo").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            mem[parts[0].rstrip(":")] = int(parts[1]) * 1024
    return mem


def cpu_times():
    """(idle, total) jiffies from /proc/stat for load sampling."""
    line = read_file("/proc/stat").splitlines()[:1]
    if not line:
        return 0, 0
    vals = [int(v) for v in line[0].split()[1:] if v.isdigit()]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return idle, sum(vals)


def uptime_text():
    try:
        secs = int(float(read_file("/proc/uptime", "0").split()[0]))
    except (ValueError, IndexError):
        return "?"
    d, h, m = secs // 86400, secs % 86400 // 3600, secs % 3600 // 60
    return f"{d}d {h}h {m}m" if d else f"{h}h {m}m"


def session():
    """Information about the running desktop session."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("XDG_SESSION_DESKTOP") or \
        os.environ.get("DESKTOP_SESSION") or ""
    return {"desktop": desktop, "names": [d.lower() for d in re.split(r"[:;]", desktop) if d],
            "type": os.environ.get("XDG_SESSION_TYPE", "x11" if os.environ.get("DISPLAY") else "unknown"),
            "session": os.environ.get("DESKTOP_SESSION", "")}


def is_laptop():
    return any(os.path.exists(p) for p in glob.glob("/sys/class/power_supply/BAT*"))


def has_ssd():
    for path in glob.glob("/sys/block/*/queue/rotational"):
        name = path.split("/")[3]
        if name.startswith(("loop", "ram", "zram", "sr", "dm-")):
            continue
        if read_file(path).strip() == "0":
            return True
    return False


def virtualization():
    code, text = run(["systemd-detect-virt"], timeout=5)
    text = text.strip()
    return text if code == 0 and text and text != "none" else ""


def version_key(text):
    """Natural sort key: '6.12.10-amd64' > '6.12.9-amd64'."""
    return [(0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"(\d+)", text) if p]


def reboot_required():
    """True when /run/reboot-required exists or a newer kernel than the running one is installed."""
    if os.path.exists("/run/reboot-required"):
        return True
    running = os.uname().release
    flavor = running.rsplit("-", 1)[-1] if "-" in running else ""
    versions = [os.path.basename(p)[len("vmlinuz-"):] for p in glob.glob("/boot/vmlinuz-*")]
    same_flavor = [v for v in versions if not flavor or v.endswith("-" + flavor)]
    if not same_flavor or running not in versions:
        return False
    return max(same_flavor, key=version_key) != running


def display_manager():
    target = os.path.realpath("/etc/systemd/system/display-manager.service")
    unit = os.path.basename(target) if os.path.exists(target) else ""
    name = unit.replace(".service", "")
    if not name:
        name = os.path.basename(read_file("/etc/X11/default-display-manager").strip())
    return {"gdm": "gdm3"}.get(name, name)


def users():
    import pwd
    found = []
    for ent in pwd.getpwall():
        if 1000 <= ent.pw_uid < 60000 and not ent.pw_shell.endswith(("nologin", "false")):
            found.append(ent.pw_name)
    return found
