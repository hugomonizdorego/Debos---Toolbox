# Debos - Toolbox

**Version 0.6.0** · A complete GTK 4 toolbox for **Debian Stable, Testing and Sid** (and LMDE).

Debos - Toolbox cleans, repairs, updates and customizes a Debian system from one place. It finds problems
before you do (the **Recommendations** page), repairs APT repositories and signing keys, installs software,
desktops, kernels and drivers, and tweaks your desktop.

Every administrative action becomes a readable bash script. You can review it before it runs, and it runs
in the console built into the window. Administrator rights come from **pkexec** (polkit), then **sudo**, then
**su**. All output is saved to `/var/log/debos-toolbox/tasks.log`.

Version 0.6.0 is a complete rewrite in **Python 3 + GTK 4** (PyGObject) with a new interface.

## Supported systems

| System | Status |
|---|---|
| Debian 13 "trixie" (Stable) | ✅ Fully supported |
| Debian 12 "bookworm" (Oldstable) | ✅ Supported, with an upgrade path to Stable |
| Debian Testing ("forky") | ✅ Supported; third-party repositories use the Stable codename |
| Debian Sid (Unstable) | ✅ Supported, with apt-listbugs and snapshot recommendations |
| LMDE 6 / 7 | ✅ Supported; branch switching is disabled |

The branch is detected automatically from `/etc/os-release`, `/etc/debian_version` and the suites in
your APT sources. Both APT 2.x (bookworm) and APT 3.x (trixie and later, including the `sqv` verifier)
are handled.

## Features

| Page | What it does |
|---|---|
| **Dashboard** | System tiles (updates, packages, reclaimable space, kernels, repositories, health), disk / memory / health gauges, live CPU chart, system information, quick actions |
| **Recommendations** | Checks for broken packages, pending updates, stale package lists, held packages, old and manually installed kernels, needed restarts, repository and key problems, missing firmware and microcode, missing drivers, full disks, firewall, ZRAM, TRIM, unattended upgrades, Flathub, failed services and more. Each suggestion has a one-click fix |
| **Cleaner** | **Scan** (refresh) and **Clean**: APT cache, unneeded packages, old kernels, leftover kernel modules, package configs, journal, rotated logs, crash dumps, `/var/tmp`, kernel build files, unused Flatpak runtimes, thumbnails, Trash, recent files, developer caches, Flatpak app caches, old installers and the caches of 9 browsers (skipped while the browser is open) |
| **Updates & Release** | Refresh, upgrade, full upgrade, Flatpak updates; switch **Stable / Testing / Sid** with a generated deb822 `debian.sources`, mirror choice, and a check before any downgrade |
| **Repositories** | Official components (contrib, non-free, non-free-firmware), backports, Fasttrack, experimental, **extrepo** (Debian's curated third-party repositories), third-party entries, keys, and the **Repository Doctor** |
| **APT Sources** | Edit any `.list` or `.sources` file, with automatic backups |
| **Software Center** | About 137 apps from Debian, extrepo, vendor repositories, `.deb` downloads and Flathub, with categories, search and install / remove buttons |
| **Uninstall** | Installed desktop apps (APT and Flatpak); essential packages are protected |
| **Desktops & WMs** | 13 desktops, 25 window managers and 11 login managers, limited to those available on your Debian release. A ✓ marks what is installed, and the desktop, window manager and login manager you are using now are marked **Current** |
| **Kernels** | Debian, RT and backports kernels; XanMod (picks x86-64-v2/v3/v4 for your CPU); Liquorix; Linux-libre; **build any kernel.org release** into `.deb` packages; remove old kernels, including kernels installed outside APT |
| **Drivers** | Reads PCI devices from sysfs and suggests drivers: NVIDIA (`nvidia-detect`, Secure Boot MOK enrolment), AMD, Intel, Wi-Fi firmware by vendor, Realtek NICs, SOF audio, CPU microcode, Bluetooth, printers, guest tools for VMs, and `isenkram` for devices with no driver |
| **Network** | Diagnostics, DNS presets, firewall, SSH and remote access |
| **System Tweaks** | ZRAM, swappiness, SSD TRIM, earlyoom, TLP power saving, Timeshift snapshots, coloured APT output, Flathub and other switches that show their current state |
| **Desktop Tweaks** | Appearance, windows, fonts, input and privacy settings for GNOME, Cinnamon, MATE and Xfce |
| **Startup Apps, Default Apps, Templates & Scripts** | Autostart entries, default applications and `update-alternatives`, new-document templates and file manager scripts |
| **Customizer** | GRUB, boot splash (Plymouth) and login screen |

**Ctrl F** searches pages, apps and settings. **Ctrl R** refreshes the current page, **Ctrl J** shows the
console and **Ctrl Q** quits. The interface has light and dark themes and is available in **English**
(default), **Bahasa Indonesia** and **Português**.

### Repository Doctor

The Doctor runs `apt-get update`, reads its output and fixes what it can:

* disables CD/DVD entries;
* merges duplicate definitions without losing components, and aligns conflicting `Signed-By` values;
* repairs missing or expired keys: reinstalls Debian keyrings, refreshes extrepo keys, finds keys already on
  the system, downloads vendor keys, or asks keyservers;
* moves keys out of the deprecated `/etc/apt/trusted.gpg`;
* accepts changed release information, limits repositories to your architecture when needed, and disables
  repositories that no longer exist.

Every file is backed up to `/var/backups/debos-toolbox/` first.

### Building a kernel from kernel.org

The kernel is built as Debian packages (`make bindeb-pkg`). APT installs them, so the kernel can be removed
like any other package.

* The download is checked against the kernel.org signature (signing keys come from WKD).
* You can start from the running kernel's configuration or from `defconfig`. `localmodconfig` makes a much
  faster build.
* Debug info and BTF are switched off, and free disk space is checked first.
* The build log is kept in `/var/tmp/debos-kernel/build.log`.
* Stopping the task stops the whole build.

## Requirements

* Debian 12 or later (GTK 4.6 or newer, Python 3.9 or newer, PyGObject 3.42 or newer)
* `gir1.2-gtk-4.0`, `python3-gi`, `pkexec` (or `sudo`)
* Optional: `gir1.2-vte-3.91` for the embedded console. Without it, tasks open in an external terminal.

## Installation

### The easy way

1. Download `debos-toolbox_0.6.0_all.deb`.
2. Open it with your software installer (GNOME Software, Discover, GDebi…).
3. Click **Install**.

### From the terminal

```bash
sudo apt install ./debos-toolbox_0.6.0_all.deb
```

Start **Debos - Toolbox** from the application menu, or run `debos-toolbox`.

```text
debos-toolbox --page cleaner   # open a page directly (cleaner, updates, repositories, software, kernels, drivers…)
debos-toolbox --startup        # background health check (used by the login monitor)
debos-toolbox --version
```

### Run without installing

```bash
./debos-toolbox/usr/bin/debos-toolbox
```

## Building the package

```bash
./build-deb.sh
```

The script reads the version from `VERSION` and checks that it matches `VERSION` in
`debos-toolbox/usr/lib/debos-toolbox/debos/__init__.py`. It also checks the syntax of every Python and shell
file before it builds `debos-toolbox_<version>_all.deb`. To release a new version, update both files and the
changelog in `debos-toolbox/usr/share/doc/debos-toolbox/changelog`.

## Files

| Path | Purpose |
|---|---|
| `~/.config/debos-toolbox/settings.json` | Settings (theme, language, ignored recommendations…) |
| `/var/log/debos-toolbox/tasks.log` | Log of all administrative tasks |
| `/var/backups/debos-toolbox/` | Backups of APT sources, keys and other changed files |
| `/var/tmp/debos-kernel/` | Kernel build directory (the Cleaner can remove it) |

## Credits

The Cleaner and the desktop tweak pages are inspired by
[Ubuntu Cleaner](https://github.com/gerardpuig/ubuntu-cleaner) and
[Ubuntu Tweak](https://github.com/tualatrix/ubuntu-tweak). Their features were reimplemented for Debian and
GTK 4; no code was copied.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
