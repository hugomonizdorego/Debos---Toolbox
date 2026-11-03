"""Kernel inventory and the shell recipes to install, build and remove kernels."""

import glob
import os
import re

from .system import version_key
from .util import run, shq

META_RE = re.compile(r"^linux-image-(?:(?:rt|cloud)-)?(?:amd64|arm64|armmp|armmp-lpae|686|686-pae|ppc64el|s390x|riscv64|liquorix-amd64)$")
XANMOD_META_RE = re.compile(r"^linux-xanmod(?:-[a-z]+)?-x64v[1-4]$")


def kernel_kind(version):
    v = version.lower()
    if "xanmod" in v:
        return "XanMod"
    if "liquorix" in v:
        return "Liquorix"
    if "gnu" in v or "libre" in v:
        return "Linux-libre"
    if "debos" in v:
        return "Built by Debos"
    if re.search(r"-(rt-)?(amd64|arm64|armmp|686-pae|686|cloud-amd64|ppc64el|s390x|riscv64)$", v):
        return "Debian"
    return "Custom"


def inventory():
    """Return {'kernels': [...], 'metas': [...], 'running': str}.

    Each kernel dict: version, package (or None for kernels installed outside
    dpkg), kind, size, running, managed, headers (installed header packages),
    newest (newest of its kind), files (for unmanaged kernels).
    """
    running = os.uname().release
    code, text = run(["dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\t${Version}\t${Installed-Size}\n",
                      "linux-image-*", "linux-headers-*", "linux-xanmod*"], timeout=30)
    images, headers, metas = {}, set(), []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 4 or not parts[1].startswith("ii"):
            continue
        pkg, _st, ver, size = parts
        if pkg.startswith("linux-headers-"):
            headers.add(pkg)
            continue
        if META_RE.match(pkg) or XANMOD_META_RE.match(pkg):
            metas.append({"package": pkg, "version": ver})
            continue
        m = re.match(r"^linux-image-(\d.*?)(-unsigned)?(-dbg)?$", pkg)
        if not m or m.group(3):
            continue
        kver = m.group(1)
        images[kver] = {"version": kver, "package": pkg, "pkg_version": ver, "kind": kernel_kind(kver),
                        "size": int(size) * 1024 if size.isdigit() else 0, "running": kver == running,
                        "managed": True, "headers": [], "files": []}
    for kver, k in images.items():
        k["headers"] = sorted(h for h in headers if h == f"linux-headers-{kver}")
        dbg = f"linux-image-{kver}-dbg"
        k["dbg"] = dbg if run(["dpkg-query", "-W", "-f=${db:Status-Abbrev}", dbg], timeout=10)[1].startswith("ii") else None

    # kernels in /boot that dpkg does not know (built with "make install")
    boot = sorted(glob.glob("/boot/vmlinuz-*"))
    owned = set()
    if boot:
        code, text = run(["dpkg-query", "-S"] + boot, timeout=30)
        for line in text.splitlines():
            if ": " in line:
                owned.add(line.split(": ", 1)[1].strip())
    for path in boot:
        kver = path[len("/boot/vmlinuz-"):]
        if kver.endswith(".old") or kver in images or path in owned:
            continue
        files = [p for p in (path, f"/boot/initrd.img-{kver}", f"/boot/System.map-{kver}", f"/boot/config-{kver}",
                             f"/lib/modules/{kver}") if os.path.exists(p)]
        size = sum(_size(p) for p in files)
        images[kver] = {"version": kver, "package": None, "pkg_version": "", "kind": "Manual install",
                        "size": size, "running": kver == running, "managed": False, "headers": [],
                        "files": files, "dbg": None}
    kernels = sorted(images.values(), key=lambda k: version_key(k["version"]), reverse=True)
    seen_kinds = set()
    for k in kernels:
        k["newest"] = k["kind"] not in seen_kinds
        seen_kinds.add(k["kind"])
    return {"kernels": kernels, "metas": metas, "running": running}


def _size(path):
    if os.path.isdir(path):
        total = 0
        for base, _d, files in os.walk(path):
            for f in files:
                try:
                    total += os.lstat(os.path.join(base, f)).st_size
                except OSError:
                    pass
        return total
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def old_kernels(inv):
    """Kernels that can safely go: not running and not the newest of their kind."""
    return [k for k in inv["kernels"] if not k["running"] and not k["newest"]]


# ---------------------------------------------------------------------------
# Recipes (lists of (title, code) steps)
# ---------------------------------------------------------------------------
def remove_steps(kernels):
    managed = [k for k in kernels if k["managed"] and not k["running"]]
    manual = [k for k in kernels if not k["managed"] and not k["running"]]
    steps = []
    if managed:
        pkgs = []
        for k in managed:
            pkgs.append(k["package"])
            pkgs += k["headers"]
            if k.get("dbg"):
                pkgs.append(k["dbg"])
        steps.append(("Removing kernel packages", [
            f"apt-get purge -y {' '.join(shq(p) for p in pkgs)}",
            "apt-get autoremove --purge -y",
        ]))
    if manual:
        steps.append(("Removing kernels installed outside APT",
                      f"debos_helper remove-kernel-files {' '.join(shq(k['version']) for k in manual)}"))
    steps.append(("Updating the boot menu", "if command -v update-grub >/dev/null; then update-grub; fi"))
    return steps


def debian_steps(flavor=""):
    meta = f"linux-image-{flavor}$ARCH" if flavor else "linux-image-$ARCH"
    hdr = f"linux-headers-{flavor}$ARCH" if flavor else "linux-headers-$ARCH"
    return [("Installing the Debian kernel", ['apt_update || true', f'apt_install "{meta}" "{hdr}"'])]


def backports_steps():
    return [("Installing the newest Debian kernel from backports", [
        'case "$BRANCH" in stable|oldstable) ;; *) fail "Backports only exist for Debian Stable and Oldstable." ;; esac',
        'if ! grep -rqsE -- "^[^#]*[[:space:]]$DEBIAN_CODENAME-backports([[:space:]]|$)" /etc/apt/sources.list /etc/apt/sources.list.d/; then',
        '  write_source debos-backports <<EOF',
        'Types: deb',
        'URIs: http://deb.debian.org/debian',
        'Suites: $DEBIAN_CODENAME-backports',
        'Components: main contrib non-free non-free-firmware',
        'Signed-By: $DEBIAN_KEYRING',
        'EOF',
        'fi',
        'apt_update',
        'apt-get install -y -t "$DEBIAN_CODENAME-backports" "linux-image-$ARCH" "linux-headers-$ARCH"',
    ])]


def xanmod_steps(package):
    return [
        ("Adding the XanMod repository", [
            "need_arch amd64",
            "add_key https://dl.xanmod.org/archive.key /etc/apt/keyrings/xanmod-archive-keyring.gpg",
            "rm -f /etc/apt/sources.list.d/xanmod.list /etc/apt/sources.list.d/xanmod-release.list",
            "write_source xanmod-release <<EOF",
            "Types: deb",
            "URIs: http://deb.xanmod.org",
            "Suites: $VENDOR_CODENAME",
            "Components: main",
            "Signed-By: /etc/apt/keyrings/xanmod-archive-keyring.gpg",
            "EOF",
            "apt_update",
        ]),
        (f"Installing {package}", [
            f"if pkg_available {shq(package)}; then",
            f"  apt_install {shq(package)}",
            "else",
            "  info \"Available XanMod packages: $(apt-cache search --names-only '^linux-xanmod' | cut -d' ' -f1 | tr '\\n' ' ')\"",
            f"  fail {shq(package + ' is not offered for this Debian release / CPU level.')}",
            "fi",
        ]),
    ]


def liquorix_steps():
    return [("Installing the Liquorix kernel", [
        "need_arch amd64",
        "if extrepo_has liquorix; then",
        "  extrepo_enable liquorix && apt_update",
        "else",
        "  download https://liquorix.net/install-liquorix.sh /tmp/debos-liquorix.sh",
        "  bash /tmp/debos-liquorix.sh; rm -f /tmp/debos-liquorix.sh",
        "fi",
        "apt_install linux-image-liquorix-amd64 linux-headers-liquorix-amd64",
    ])]


def libre_steps(lts=False):
    pkg = "linux-libre-lts" if lts else "linux-libre"
    return [("Installing Linux-libre (FSFLA freesh)", [
        "BASE=https://linux-libre.fsfla.org/pub/linux-libre/freesh/pool/main/f/freesh-archive-keyring/",
        "KR=$(curl -fsSL \"$BASE\" | grep -oE 'freesh-archive-keyring_[0-9.]+_all\\.deb' | sort -uV | tail -n1)",
        "[ -n \"$KR\" ] || fail 'Could not find the freesh keyring package.'",
        "download \"$BASE$KR\" /tmp/debos-freesh.deb",
        "apt_install /tmp/debos-freesh.deb; rm -f /tmp/debos-freesh.deb",
        "apt_update",
        f"apt_install {pkg}",
    ])]


KERNEL_ORG = "https://www.kernel.org"
KERNEL_CDN = "https://cdn.kernel.org/pub/linux/kernel"


def mainline_steps(moniker="stable", version="", config="running", localmod=False, suffix="-debos", jobs=0,
                   keep_source=False):
    """Download a kernel from kernel.org, build Debian packages and install them.

    The build directory is /var/tmp/debos-kernel; values are passed between
    steps through small files because every step runs in its own subshell.
    """
    if version and not re.match(r"^\d+\.\d+(\.\d+)?$", version):
        raise ValueError("invalid kernel version")
    if not re.match(r"^-[a-z0-9][a-z0-9.-]{0,20}$", suffix):
        raise ValueError("invalid local version suffix")
    need = 8 if localmod else 20
    jobs_expr = str(int(jobs)) if jobs else "$(nproc)"
    py = ("import sys,json; d=json.load(sys.stdin); "
          f"r=next(x for x in d['releases'] if x['moniker']=={moniker!r} and x['source'] and x['source'].endswith('.tar.xz')); "
          "print(r['version'], r['source'])")
    resolve = [
        f'KORG="${{DEBOS_KERNEL_ORG:-{KERNEL_ORG}}}"',
        f'KCDN="${{DEBOS_KERNEL_CDN:-{KERNEL_CDN}}}"',
    ]
    if version:
        resolve += [f"KVER={shq(version)}", 'KSRC="$KCDN/v${KVER%%.*}.x/linux-$KVER.tar.xz"']
    else:
        resolve += [f"read -r KVER KSRC < <(curl -fsSL --retry 3 \"$KORG/releases.json\" | python3 -c {shq(py)})",
                    '[ -n "$KSRC" ] || fail "Could not read the release list from kernel.org."']
    steps = [
        ("Checking disk space and build directory", [
            "B=/var/tmp/debos-kernel",
            'mkdir -p "$B"',
            'FREE=$(free_space_gb "$B")',
            f'info "Free space in $B: ${{FREE}} GB (needed: about {need} GB)"',
            f'[ "$FREE" -ge {need} ] || fail "Not enough free space: about {need} GB are needed in $B."',
            'secure_boot_enabled && warn "Secure Boot is enabled: a self-built kernel is unsigned and will not boot until you disable Secure Boot or sign it." || true',
        ]),
        ("Installing build tools", [
            "apt_install build-essential fakeroot bc bison flex libssl-dev libelf-dev libncurses-dev dwarves rsync cpio kmod "
            "python3 xz-utils zstd debhelper libdw-dev gawk openssl gnupg curl",
        ]),
        ("Downloading the kernel source", ["B=/var/tmp/debos-kernel", 'cd "$B"'] + resolve + [
            'info "Kernel $KVER from $KSRC"',
            'echo "$KVER" > "$B/.version"',
            'if [ -f "linux-$KVER.tar.xz" ] && xz -t "linux-$KVER.tar.xz" 2>/dev/null; then info "Using the already downloaded archive."; '
            'else rm -f "linux-$KVER.tar.xz"; download "$KSRC" "linux-$KVER.tar.xz"; fi',
            'download "${KSRC%.xz}.sign" "linux-$KVER.tar.sign" || warn "Signature file not available."',
        ]),
        ("Verifying the release signature", [
            "B=/var/tmp/debos-kernel", 'cd "$B"', 'KVER=$(cat "$B/.version")',
            'if [ ! -s "linux-$KVER.tar.sign" ]; then warn "No signature to check."; exit 0; fi',
            'export GNUPGHOME=$(mktemp -d)',
            'gpg --batch --quiet --auto-key-locate clear,wkd,nodefault --locate-keys torvalds@kernel.org gregkh@kernel.org >/dev/null 2>&1 || true',
            'if xz -cd "linux-$KVER.tar.xz" | gpg --batch --verify "linux-$KVER.tar.sign" - 2> "$B/.gpg.log"; then',
            '  ok "Good signature from kernel.org"',
            'elif grep -q "BAD signature" "$B/.gpg.log"; then',
            '  cat "$B/.gpg.log"; rm -f "linux-$KVER.tar.xz"; fail "BAD signature - the download was corrupted or tampered with."',
            'else',
            '  cat "$B/.gpg.log"; warn "The signature could not be checked (signing keys unavailable). Continuing."',
            'fi',
            'rm -rf "$GNUPGHOME"',
        ]),
        ("Preparing the kernel configuration", [
            "B=/var/tmp/debos-kernel", 'cd "$B"', 'KVER=$(cat "$B/.version")',
            'rm -rf "linux-$KVER" && tar -xf "linux-$KVER.tar.xz" && cd "linux-$KVER"',
        ] + ([
            'if [ -f "/boot/config-$(uname -r)" ]; then cp "/boot/config-$(uname -r)" .config; info "Based on the running kernel configuration."',
            'elif [ -r /proc/config.gz ]; then zcat /proc/config.gz > .config',
            'else make defconfig; fi',
        ] if config == "running" else ["make defconfig"]) + [
            "scripts/config --file .config --disable SYSTEM_TRUSTED_KEYS --disable SYSTEM_REVOCATION_KEYS "
            "--set-str SYSTEM_TRUSTED_KEYS '' --set-str SYSTEM_REVOCATION_KEYS '' --disable DEBUG_INFO "
            "--disable DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT --disable DEBUG_INFO_DWARF4 --disable DEBUG_INFO_DWARF5 "
            "--enable DEBUG_INFO_NONE --disable DEBUG_INFO_BTF --set-str LOCALVERSION ''",
        ] + ([
            'lsmod > "$B/.lsmod"',
            '[ "$(wc -l < "$B/.lsmod")" -gt 20 ] || warn "Only a few modules are loaded: drivers for devices that are not plugged in now will be left out."',
            # answer new questions with their defaults; process substitution keeps yes(1) out of pipefail
            'make LSMOD="$B/.lsmod" localmodconfig < <(yes "") >/dev/null',
        ] if localmod else []) + [
            "make olddefconfig",
        ]),
        ("Compiling (this can take from 20 minutes to several hours)", [
            "B=/var/tmp/debos-kernel", 'KVER=$(cat "$B/.version")', 'cd "$B/linux-$KVER"',
            # a fresh package revision for every build, so a rebuild of the same version installs as an upgrade
            'PKGV="$KVER-$(date +%Y%m%d%H%M)"', 'echo "$PKGV" > "$B/.pkgversion"',
            f'info "Building with {jobs_expr if jobs else "all"} parallel jobs; full log: $B/build.log"',
            f'setsid nice -n 10 make -j"{jobs_expr}" bindeb-pkg LOCALVERSION={shq(suffix)} KDEB_PKGVERSION="$PKGV" > "$B/build.log" 2>&1 &',
            'PID=$!',
            # background jobs ignore Ctrl+C in scripts: stop the whole build process group ourselves
            "trap 'kill -TERM -- -\"$PID\" 2>/dev/null; echo; warn \"Build stopped.\"; exit 130' INT TERM",
            'while kill -0 "$PID" 2>/dev/null; do sleep 15; info "$(date +%H:%M:%S) $(tail -n 1 "$B/build.log" | cut -c1-110)"; done',
            'if ! wait "$PID"; then',
            '  echo; tail -n 40 "$B/build.log"; fail "The kernel build failed - see the lines above or $B/build.log"',
            'fi',
            # the real release string (6.12 builds as 6.12.0-debos, LOCALVERSION may add more)
            'cat include/config/kernel.release > "$B/.krelease"',
            'ok "Built $(cat "$B/.krelease")"',
        ]),
        ("Installing the new kernel packages", [
            "B=/var/tmp/debos-kernel", 'KVER=$(cat "$B/.version")', 'cd "$B"',
            'KREL=$(cat "$B/.krelease")', 'PKGV=$(cat "$B/.pkgversion")',
            'DEBS=()',
            'for f in "$B"/linux-image-"$KREL"_"$PKGV"_*.deb "$B"/linux-headers-"$KREL"_"$PKGV"_*.deb; do [ -f "$f" ] && DEBS+=("$f"); done',
            '[ ${#DEBS[@]} -gt 0 ] || fail "No kernel packages were produced."',
            'info "Packages: ${DEBS[*]##*/}"',
            'apt-get install -y "${DEBS[@]}"',
            'ok "Kernel $KREL installed. Reboot and choose it in GRUB (Advanced options)."',
        ]),
    ]
    if not keep_source:
        steps.append(("Removing the build tree (packages are kept)", [
            "B=/var/tmp/debos-kernel", 'KVER=$(cat "$B/.version")', 'rm -rf "$B/linux-$KVER"',
            'info "Kernel packages remain in $B for reinstalling."',
        ]))
    return steps
