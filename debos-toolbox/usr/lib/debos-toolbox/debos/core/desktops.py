"""Desktop environments, window managers and display managers packaged in Debian."""

import glob
import os

from . import system
from .util import shq

# variants: (key, label, packages) - the first available variant is the default
DESKTOPS = [
    {"id": "gnome", "name": "GNOME", "desc": "Modern desktop with the Activities overview.", "color": "blue",
     "detect": ["gnome-shell"], "sessions": ["gnome", "gnome-xorg", "gnome-wayland", "gnome-classic"], "xdg": ["gnome"],
     "variants": [("full", "Full (Debian task)", "task-gnome-desktop"), ("standard", "Standard", "gnome"),
                  ("minimal", "Minimal", "gnome-core")],
     "remove": "task-gnome-desktop gnome gnome-core gnome-shell gnome-session", "dm": "gdm3"},
    {"id": "kde", "name": "KDE Plasma", "desc": "Highly customizable, feature-rich desktop.", "color": "cyan",
     "detect": ["plasma-workspace"], "sessions": ["plasma", "plasmawayland", "plasmax11"], "xdg": ["kde"],
     "variants": [("full", "Full (Debian task)", "task-kde-desktop"), ("standard", "Standard", "kde-standard"),
                  ("minimal", "Minimal", "kde-plasma-desktop")],
     "remove": "task-kde-desktop kde-standard kde-plasma-desktop plasma-desktop plasma-workspace", "dm": "sddm"},
    {"id": "xfce", "name": "Xfce", "desc": "Fast, stable and light on resources.", "color": "teal",
     "detect": ["xfce4-session"], "sessions": ["xfce"], "xdg": ["xfce"],
     "variants": [("full", "Full (Debian task)", "task-xfce-desktop"), ("standard", "Standard", "xfce4 xfce4-goodies"),
                  ("minimal", "Minimal", "xfce4")],
     "remove": "task-xfce-desktop xfce4 xfce4-goodies xfce4-session xfwm4 xfce4-panel", "dm": "lightdm"},
    {"id": "cinnamon", "name": "Cinnamon", "desc": "Traditional, elegant desktop from Linux Mint.", "color": "orange",
     "detect": ["cinnamon"], "sessions": ["cinnamon", "cinnamon2d"], "xdg": ["x-cinnamon", "cinnamon"],
     "variants": [("full", "Full (Debian task)", "task-cinnamon-desktop"), ("standard", "Standard", "cinnamon-desktop-environment"),
                  ("minimal", "Minimal", "cinnamon-core")],
     "remove": "task-cinnamon-desktop cinnamon-desktop-environment cinnamon-core cinnamon cinnamon-session", "dm": "lightdm"},
    {"id": "mate", "name": "MATE", "desc": "The classic GNOME 2 experience.", "color": "lime",
     "detect": ["mate-session-manager"], "sessions": ["mate"], "xdg": ["mate"],
     "variants": [("full", "Full (Debian task)", "task-mate-desktop"), ("standard", "Standard", "mate-desktop-environment"),
                  ("minimal", "Minimal", "mate-desktop-environment-core")],
     "remove": "task-mate-desktop mate-desktop-environment mate-desktop-environment-core mate-session-manager mate-panel", "dm": "lightdm"},
    {"id": "lxqt", "name": "LXQt", "desc": "Lightweight Qt desktop.", "color": "purple",
     "detect": ["lxqt-session"], "sessions": ["lxqt"], "xdg": ["lxqt"],
     "variants": [("full", "Full (Debian task)", "task-lxqt-desktop"), ("standard", "Standard", "lxqt"), ("minimal", "Minimal", "lxqt-core")],
     "remove": "task-lxqt-desktop lxqt lxqt-core lxqt-session lxqt-panel", "dm": "sddm"},
    {"id": "lxde", "name": "LXDE", "desc": "Very light GTK desktop for older hardware.", "color": "slate",
     "detect": ["lxde-core", "lxsession-logout"], "sessions": ["lxde"], "xdg": ["lxde"],
     "variants": [("full", "Full (Debian task)", "task-lxde-desktop"), ("standard", "Standard", "lxde"), ("minimal", "Minimal", "lxde-core")],
     "remove": "task-lxde-desktop lxde lxde-core lxpanel", "dm": "lightdm"},
    {"id": "budgie", "name": "Budgie", "desc": "Sleek desktop focused on simplicity.", "color": "violet",
     "detect": ["budgie-desktop"], "sessions": ["budgie-desktop"], "xdg": ["budgie"],
     "variants": [("standard", "Standard", "budgie-desktop-environment"), ("minimal", "Minimal", "budgie-desktop")],
     "remove": "budgie-desktop-environment budgie-desktop", "dm": "lightdm"},
    {"id": "flashback", "name": "GNOME Flashback", "desc": "GNOME with a classic panel layout.", "color": "blue",
     "detect": ["gnome-flashback"], "sessions": ["gnome-flashback-metacity", "gnome-flashback-compiz"], "xdg": ["gnome-flashback"],
     "variants": [("full", "Full (Debian task)", "task-gnome-flashback-desktop"), ("minimal", "Minimal", "gnome-session-flashback")],
     "remove": "task-gnome-flashback-desktop gnome-session-flashback gnome-flashback", "dm": "gdm3"},
    {"id": "enlightenment", "name": "Enlightenment", "desc": "Fast, beautiful desktop with effects.", "color": "amber",
     "detect": ["enlightenment"], "sessions": ["enlightenment"], "xdg": ["enlightenment"],
     "variants": [("standard", "Standard", "enlightenment terminology")], "remove": "enlightenment", "dm": "lightdm"},
    {"id": "lomiri", "name": "Lomiri", "desc": "Convergent desktop from UBports (formerly Unity 8).", "color": "orange",
     "detect": ["lomiri"], "sessions": ["lomiri"], "xdg": ["lomiri"],
     "variants": [("standard", "Standard", "lomiri-desktop-session")], "remove": "lomiri-desktop-session lomiri", "dm": "lightdm"},
    {"id": "ukui", "name": "UKUI", "desc": "Windows-like desktop from openKylin.", "color": "red",
     "detect": ["ukui-session-manager"], "sessions": ["ukui"], "xdg": ["ukui"],
     "variants": [("standard", "Standard", "ukui-desktop-environment")], "remove": "ukui-desktop-environment ukui-session-manager", "dm": "lightdm"},
    {"id": "phosh", "name": "Phosh", "desc": "Touch-friendly shell for phones and tablets.", "color": "green",
     "detect": ["phosh"], "sessions": ["phosh"], "xdg": ["phosh"],
     "variants": [("full", "Full", "phosh-full"), ("minimal", "Core", "phosh-core")], "remove": "phosh-full phosh-core phosh", "dm": "gdm3"},
]

WMS = [
    {"id": "i3", "name": "i3", "desc": "Popular tiling window manager for X11.", "detect": ["i3-wm"], "sessions": ["i3"], "xdg": ["i3"],
     "packages": "i3 i3status suckless-tools rofi xss-lock", "type": "X11 tiling"},
    {"id": "sway", "name": "Sway", "desc": "i3-compatible Wayland compositor.", "detect": ["sway"], "sessions": ["sway"], "xdg": ["sway"],
     "packages": "sway swaybg swayidle swaylock waybar wofi foot grim slurp wl-clipboard", "type": "Wayland tiling"},
    {"id": "hyprland", "name": "Hyprland", "desc": "Dynamic tiling Wayland compositor with animations.", "detect": ["hyprland"],
     "sessions": ["hyprland"], "xdg": ["hyprland"], "packages": "hyprland hyprpaper waybar wofi kitty", "type": "Wayland tiling"},
    {"id": "wayfire", "name": "Wayfire", "desc": "3D Wayland compositor with plugins.", "detect": ["wayfire"], "sessions": ["wayfire"],
     "xdg": ["wayfire"], "packages": "wayfire wf-shell wcm", "type": "Wayland stacking"},
    {"id": "labwc", "name": "labwc", "desc": "Openbox-like Wayland compositor.", "detect": ["labwc"], "sessions": ["labwc"], "xdg": ["labwc"],
     "packages": "labwc swaybg waybar foot", "type": "Wayland stacking"},
    {"id": "river", "name": "river", "desc": "Dynamic tiling Wayland compositor.", "detect": ["river"], "sessions": ["river"], "xdg": ["river"],
     "packages": "river foot", "type": "Wayland tiling"},
    {"id": "niri", "name": "niri", "desc": "Scrollable-tiling Wayland compositor.", "detect": ["niri"], "sessions": ["niri"], "xdg": ["niri"],
     "packages": "niri foot", "type": "Wayland tiling"},
    {"id": "bspwm", "name": "bspwm", "desc": "Binary space partitioning tiling WM.", "detect": ["bspwm"], "sessions": ["bspwm"], "xdg": ["bspwm"],
     "packages": "bspwm sxhkd polybar rofi xterm", "type": "X11 tiling"},
    {"id": "openbox", "name": "Openbox", "desc": "Highly configurable floating WM.", "detect": ["openbox"], "sessions": ["openbox"],
     "xdg": ["openbox"], "packages": "openbox obconf tint2 menu xterm", "type": "X11 stacking"},
    {"id": "fluxbox", "name": "Fluxbox", "desc": "Light stacking WM with tabs.", "detect": ["fluxbox"], "sessions": ["fluxbox"],
     "xdg": ["fluxbox"], "packages": "fluxbox xterm", "type": "X11 stacking"},
    {"id": "awesome", "name": "awesome", "desc": "Dynamic WM configured in Lua.", "detect": ["awesome"], "sessions": ["awesome"],
     "xdg": ["awesome"], "packages": "awesome awesome-extra xterm", "type": "X11 tiling"},
    {"id": "icewm", "name": "IceWM", "desc": "Windows-like, very light.", "detect": ["icewm"], "sessions": ["icewm-session", "icewm"],
     "xdg": ["icewm"], "packages": "icewm xterm", "type": "X11 stacking"},
    {"id": "jwm", "name": "JWM", "desc": "Joe's Window Manager - tiny and simple.", "detect": ["jwm"], "sessions": ["jwm"], "xdg": ["jwm"],
     "packages": "jwm xterm", "type": "X11 stacking"},
    {"id": "herbstluftwm", "name": "herbstluftwm", "desc": "Manual tiling WM using frames.", "detect": ["herbstluftwm"],
     "sessions": ["herbstluftwm"], "xdg": ["herbstluftwm"], "packages": "herbstluftwm xterm", "type": "X11 tiling"},
    {"id": "xmonad", "name": "xmonad", "desc": "Tiling WM written and configured in Haskell.", "detect": ["xmonad"], "sessions": ["xmonad"],
     "xdg": ["xmonad"], "packages": "xmonad libghc-xmonad-contrib-dev xmobar xterm", "type": "X11 tiling"},
    {"id": "dwm", "name": "dwm", "desc": "Suckless dynamic window manager.", "detect": ["dwm"], "sessions": ["dwm"], "xdg": ["dwm"],
     "packages": "dwm suckless-tools stterm", "type": "X11 tiling"},
    {"id": "spectrwm", "name": "spectrwm", "desc": "Small dynamic tiling WM.", "detect": ["spectrwm"], "sessions": ["spectrwm"],
     "xdg": ["spectrwm"], "packages": "spectrwm xterm", "type": "X11 tiling"},
    {"id": "qtile", "name": "Qtile", "desc": "Tiling WM written in Python.", "detect": ["qtile"], "sessions": ["qtile"], "xdg": ["qtile"],
     "packages": "qtile", "type": "X11/Wayland tiling"},
    {"id": "wmaker", "name": "Window Maker", "desc": "NeXTSTEP-style window manager.", "detect": ["wmaker"], "sessions": ["wmaker"],
     "xdg": ["windowmaker", "wmaker"], "packages": "wmaker wmaker-data", "type": "X11 stacking"},
    {"id": "fvwm3", "name": "FVWM3", "desc": "Classic, extremely configurable WM.", "detect": ["fvwm3"], "sessions": ["fvwm3"],
     "xdg": ["fvwm3"], "packages": "fvwm3 xterm", "type": "X11 stacking"},
    {"id": "pekwm", "name": "PekWM", "desc": "Light WM with window grouping.", "detect": ["pekwm"], "sessions": ["pekwm"], "xdg": ["pekwm"],
     "packages": "pekwm xterm", "type": "X11 stacking"},
    {"id": "cwm", "name": "cwm", "desc": "Minimal WM from OpenBSD.", "detect": ["cwm"], "sessions": ["cwm"], "xdg": ["cwm"],
     "packages": "cwm xterm", "type": "X11 stacking"},
    {"id": "notion", "name": "Notion", "desc": "Tiling, tabbing WM.", "detect": ["notion"], "sessions": ["notion"], "xdg": ["notion"],
     "packages": "notion xterm", "type": "X11 tiling"},
    {"id": "ratpoison", "name": "ratpoison", "desc": "Keyboard-only WM, no mouse needed.", "detect": ["ratpoison"], "sessions": ["ratpoison"],
     "xdg": ["ratpoison"], "packages": "ratpoison xterm", "type": "X11 tiling"},
    {"id": "e16", "name": "Enlightenment DR16", "desc": "The classic Enlightenment window manager.", "detect": ["e16"], "sessions": ["e16"],
     "xdg": ["e16"], "packages": "e16", "type": "X11 stacking"},
]

DMS = [
    {"id": "gdm3", "name": "GDM", "desc": "GNOME Display Manager (X11 and Wayland).", "packages": "gdm3", "binary": "gdm3", "unit": "gdm"},
    {"id": "sddm", "name": "SDDM", "desc": "Qt login manager used by KDE and LXQt.", "packages": "sddm", "binary": "sddm", "unit": "sddm"},
    {"id": "lightdm", "name": "LightDM (GTK greeter)", "desc": "Light and flexible, default for Xfce/MATE/Cinnamon.",
     "packages": "lightdm lightdm-gtk-greeter", "binary": "lightdm", "unit": "lightdm", "greeter": "lightdm-gtk-greeter"},
    {"id": "slick", "name": "LightDM (Slick greeter)", "desc": "Elegant LightDM greeter from Linux Mint.",
     "packages": "lightdm slick-greeter", "binary": "lightdm", "unit": "lightdm", "greeter": "slick-greeter", "detect": "slick-greeter"},
    {"id": "arctica", "name": "LightDM (Arctica greeter)", "desc": "Modern LightDM greeter from Arctica.",
     "packages": "lightdm arctica-greeter", "binary": "lightdm", "unit": "lightdm", "greeter": "arctica-greeter", "detect": "arctica-greeter"},
    {"id": "lxdm", "name": "LXDM", "desc": "LXDE display manager, very light.", "packages": "lxdm", "binary": "lxdm", "unit": "lxdm"},
    {"id": "xdm", "name": "XDM", "desc": "The classic X display manager.", "packages": "xdm", "binary": "xdm", "unit": "xdm"},
    {"id": "wdm", "name": "WDM", "desc": "WINGs display manager (Window Maker style).", "packages": "wdm", "binary": "wdm", "unit": "wdm"},
    {"id": "nodm", "name": "nodm", "desc": "Automatic login without a greeter (kiosks).", "packages": "nodm", "binary": "nodm", "unit": "nodm"},
    {"id": "greetd", "name": "greetd + tuigreet", "desc": "Minimal login daemon with a console greeter (great for Wayland WMs).",
     "packages": "greetd tuigreet", "binary": "greetd", "unit": "greetd", "detect": "greetd"},
    {"id": "ly", "name": "Ly", "desc": "Lightweight TUI display manager.", "packages": "ly", "binary": "ly", "unit": "ly"},
]


def session_files():
    names = set()
    for d in ("/usr/share/xsessions", "/usr/share/wayland-sessions"):
        for path in glob.glob(os.path.join(d, "*.desktop")):
            names.add(os.path.basename(path)[:-8].lower())
    return names


def status(entry, installed, sessions, current_names, current_session):
    is_installed = any(p in installed for p in entry.get("detect", [])) or any(s in sessions for s in entry.get("sessions", []))
    is_current = any(x in current_names for x in entry.get("xdg", [])) or \
        (current_session and current_session.lower() in entry.get("sessions", []))
    return is_installed, is_current


def all_candidate_packages():
    pkgs = set()
    for d in DESKTOPS:
        for _k, _l, p in d["variants"]:
            pkgs.update(p.split())
    for w in WMS:
        pkgs.update(w["packages"].split()[:1])
    for dm in DMS:
        pkgs.update(dm["packages"].split())
    return pkgs


def available_variants(entry, candidates):
    return [(k, l, p) for k, l, p in entry["variants"] if all(candidates.get(x) for x in p.split())]


def wm_available(entry, candidates):
    return bool(candidates.get(entry["packages"].split()[0]))


def dm_available(entry, candidates):
    return all(candidates.get(p) for p in entry["packages"].split())


def dm_installed(entry, installed):
    return entry.get("detect", entry["packages"].split()[-1]) in installed


def install_de_steps(entry, packages):
    return [(f"Installing {entry['name']}", [f"apt_install {packages}", "systemctl set-default graphical.target"])]


def remove_de_steps(entry, installed):
    pkgs = [p for p in entry["remove"].split() if p in installed]
    if not pkgs:
        return []
    return [(f"Removing {entry['name']}", [f"apt-get purge {' '.join(shq(p) for p in pkgs)}",
                                          "apt-get autoremove --purge"])]


def install_wm_steps(entry):
    main, *extra = entry["packages"].split()
    steps = [(f"Installing {entry['name']}", f"apt_install {shq(main)}")]
    if extra:
        steps.append(("Installing recommended tools", f"apt_install_available {' '.join(shq(p) for p in extra)}"))
    return steps


def remove_wm_steps(entry, installed):
    pkgs = [p for p in entry["detect"] + entry["packages"].split()[:1] if p in installed]
    if not pkgs:
        return []
    return [(f"Removing {entry['name']}", [f"apt-get purge {' '.join(sorted(set(shq(p) for p in pkgs)))}", "apt-get autoremove --purge"])]


def switch_dm_steps(entry):
    pkgs, binary, unit = entry["packages"], entry["binary"], entry["unit"]
    steps = [(f"Installing {entry['name']}", [
        f"echo '{binary} shared/default-x-display-manager select {binary}' | debconf-set-selections",
        f"DEBIAN_FRONTEND=noninteractive apt-get install -y {pkgs}",
    ])]
    code = []
    if entry["id"] == "greetd":
        code += [
            "mkdir -p /etc/greetd",
            "[ -f /etc/greetd/config.toml ] && cp -n /etc/greetd/config.toml /etc/greetd/config.toml.debos.bak",
            "cat > /etc/greetd/config.toml <<'EOF'",
            "[terminal]", "vt = 7", "", "[default_session]",
            'command = "tuigreet --time --remember --remember-session --asterisks"', 'user = "_greetd"', "EOF",
            "id _greetd >/dev/null 2>&1 || true",
        ]
    else:
        code += [f'BIN=$(command -v {binary} || echo /usr/sbin/{binary})', 'echo "$BIN" > /etc/X11/default-display-manager',
                 f"DEBIAN_FRONTEND=noninteractive dpkg-reconfigure {binary} || true"]
    code += [
        f"UNIT={unit}.service",
        f'[ -f "/lib/systemd/system/$UNIT" ] || [ -f "/usr/lib/systemd/system/$UNIT" ] || UNIT=$(systemctl list-unit-files --no-legend "{unit}*.service" | awk \'NR==1{{print $1}}\')',
        '[ -n "$UNIT" ] || fail "No systemd unit found for the display manager."',
        'UNITPATH=$( [ -f "/usr/lib/systemd/system/$UNIT" ] && echo "/usr/lib/systemd/system/$UNIT" || echo "/lib/systemd/system/$UNIT")',
        'ln -sf "$UNITPATH" /etc/systemd/system/display-manager.service',
        "systemctl daemon-reload",
    ]
    if entry.get("greeter"):
        code += ["mkdir -p /etc/lightdm/lightdm.conf.d",
                 f"printf '[Seat:*]\\ngreeter-session={entry['greeter']}\\n' > /etc/lightdm/lightdm.conf.d/40-debos-greeter.conf"]
    code.append(f"ok {shq(entry['name'] + ' is now the login screen. Restart the computer to use it.')}")
    steps.append(("Setting the default login screen", code))
    return steps


def current_info():
    s = system.session()
    return s["names"], s["session"]
