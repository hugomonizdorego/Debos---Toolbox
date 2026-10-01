# Debos - Toolbox

**Version 0.5.0** · The all-in-one GUI toolbox for **Debian Stable, Testing, Sid** and **LMDE**.

Clean and repair your system, keep it up to date, switch between Debian branches, install software,
desktops, kernels and drivers, configure the network and customize the boot and login screens, all from
one modern interface with light and dark themes.

Every privileged action is turned into a readable bash script that runs with `sudo` in a terminal window,
so you always see exactly what happens. All output is also saved to `/var/log/debos-toolbox.log`.

## Supported systems

| System | Status |
|---|---|
| Debian 13 "trixie" (Stable) | ✅ Fully supported |
| Debian 12 "bookworm" (Oldstable) | ✅ Supported, with an upgrade path to Stable |
| Debian Testing ("forky") | ✅ Supported (third-party repositories use `trixie`) |
| Debian Sid (Unstable) | ✅ Supported, with apt-listbugs recommendations |
| LMDE 6 / 7 | ✅ Supported (branch switching disabled) |

The branch is detected automatically from `/etc/os-release`, `/etc/debian_version` and your APT sources.

## Features

| Page | What it does |
|---|---|
| **Dashboard** | OS, branch, kernel, CPU, memory, disk, updates, package health, Secure Boot, plus one-click Update / Full Upgrade / Fix |
| **Clean System** | autoremove, APT cache, residual configs, journal, Flatpak runtimes, thumbnails, rotated logs, Trash, old `/tmp` files, duplicate finder (shows estimated sizes) |
| **Repair APT & Keys** | dpkg configure, broken dependencies, stale locks, duplicate source lines, missing `NO_PUBKEY` keys, rebuild lists, `apt modernize-sources`, keyring reinstall |
| **Updates & Release** | Check updates, upgrade, full-upgrade, Flatpak updates. **Switch between Stable / Testing / Sid** with a generated deb822 `debian.sources` (backports, deb-src, non-free, mirror choice) and a warning before any downgrade |
| **APT Sources** | Edit any `.list` / `.sources` file, with an automatic backup in `/var/backups/debos-toolbox` |
| **Install Software** | 50+ apps from Debian or official vendor repositories (Firefox, Chrome, Edge, Brave, Vivaldi, VS Code, Docker, VirtualBox, Steam, WineHQ…) and 29 Flatpaks, with search and "installed" badges |
| **Uninstall Software** | Lists installed desktop apps (APT + Flatpak), protects essential packages |
| **Desktops & WMs** | GNOME, KDE Plasma, XFCE, Cinnamon, MATE, LXQt, LXDE, Budgie (Full / Minimal / Core / Remove) and i3, Sway, bspwm, Openbox, awesome, IceWM, JWM, Qtile |
| **Kernels** | Debian backports, XanMod (x64v2/v3/v4, Edge, LTS, RT) with CPU-level detection, Liquorix, Linux-libre, mainline compile into `.deb` packages; safe removal of old kernels |
| **Drivers & Hardware** | Hardware detection with recommendations: NVIDIA, Nouveau, AMD, Intel, Wi-Fi firmware, Broadcom, CPU microcode, Bluetooth, printers, scanners, fwupd, 32-bit support, Vulkan |
| **Network** | IP / gateway / DNS / public IP, speed test, Wi-Fi & LAN scan, DNS presets (Cloudflare, Google, Quad9, AdGuard, OpenDNS), saved Wi-Fi passwords, hostname, UFW firewall, SSH, RDP, MAC changer |
| **Tweaks & Tools** | ZRAM, swappiness, unattended upgrades, SSD TRIM, earlyoom, TLP, Timeshift, Flathub, fonts, essentials, plus diagnostics (boot errors, failed services, boot time, disk usage, inxi) |
| **Customizer** | GRUB (timeout, colors, background, os-prober, remember last entry, quiet), Plymouth (custom image theme or installed theme), login screen for GDM3, LightDM GTK, Slick-Greeter and SDDM, display-manager switching |
| **About** | Background health monitor at login, feedback form, links |

The interface is available in **English** (default), **Bahasa Indonesia** and **Português**. Language and
theme are remembered in `~/.config/debos-toolbox/settings.json`.

## Installation

### The easy way (GUI)

1. Download `debos-toolbox_0.5.0_all.deb`.
2. Double-click it. Your software installer (GNOME Software, GDebi, Discover…) opens.
3. Click **Install** and enter your password.

### From the terminal

```bash
cd ~/Downloads
sudo apt update
sudo apt install ./debos-toolbox_0.5.0_all.deb
```

Start it from the application menu (**Debos - Toolbox**) or run `debos-toolbox`.

Command-line options:

```text
debos-toolbox --version   # print version and build
debos-toolbox --startup   # run the background health check (used by autostart)
```

## Building the package

```bash
./build-deb.sh
```

The version is read from the `VERSION` file and must match `APP_VERSION` in
`debos-toolbox/usr/bin/debos-toolbox`. To release a new version, update both (and the changelog in
`debos-toolbox/usr/share/doc/debos-toolbox/changelog`), then run the build script.

## License

Open Source (GNU GPL v3), FDSL - TL. Developed in Timor-Leste by Hugo Moniz do Rego.
Please credit the original author in derivative works.
