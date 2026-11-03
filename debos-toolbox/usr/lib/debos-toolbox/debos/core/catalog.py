"""Software catalogue.

Each app lists install methods in order of preference:
  apt      - a package from the Debian archive (checked with apt-cache at runtime)
  extrepo  - a Debian-curated third-party repository (extrepo enable NAME)
  vendor   - the vendor's own repository / installer
  deb      - a single .deb download
  flatpak  - an app from Flathub
Only methods that work on the running Debian release are offered.
"""

from .util import shq

CATEGORIES = [
    ("popular", "Popular", "starred-symbolic"),
    ("browsers", "Browsers", "web-browser-symbolic"),
    ("internet", "Internet & Chat", "mail-unread-symbolic"),
    ("office", "Office", "x-office-document-symbolic"),
    ("media", "Multimedia", "applications-multimedia-symbolic"),
    ("graphics", "Graphics & Photo", "applications-graphics-symbolic"),
    ("dev", "Development", "utilities-terminal-symbolic"),
    ("system", "System & Tools", "applications-system-symbolic"),
    ("security", "Security & Privacy", "security-high-symbolic"),
    ("games", "Gaming", "applications-games-symbolic"),
]
CAT_COLOR = {"browsers": "blue", "internet": "cyan", "office": "orange", "media": "pink", "graphics": "violet",
             "dev": "purple", "system": "teal", "security": "green", "games": "red"}
CAT_GLYPH = {k: g for k, _t, g in CATEGORIES}


def _repo(name, key_url, key_file, uri, suites, components="main", arch=None):
    lines = [f"add_key {key_url} {key_file}", f"write_source {name} <<'EOF'", "Types: deb", f"URIs: {uri}",
             f"Suites: {suites}", f"Components: {components}"]
    if arch:
        lines.append(f"Architectures: {arch}")
    lines += [f"Signed-By: {key_file}", "EOF", "apt_update"]
    return lines


APPS = []


def A(aid, name, summary, cat, icons=(), popular=False, check=None, apt=None, nonfree=False, extrepo=None,
      vendor=None, deb=None, flatpak=None, post=None, glyph=None, arch=None, order=None):
    methods = []
    if apt:
        methods.append({"type": "apt", "packages": apt.split(), "nonfree": nonfree})
    if extrepo:
        repo, policy, pkgs = extrepo[:3]
        methods.append({"type": "extrepo", "repo": repo, "policy": policy, "packages": pkgs.split(),
                        "pre": extrepo[3] if len(extrepo) > 3 else []})
    if vendor:
        label, steps, vpkgs = vendor
        methods.append({"type": "vendor", "label": label, "steps": steps, "packages": vpkgs.split()})
    if deb:
        methods.append({"type": "deb", "url": deb[0], "packages": deb[1].split()})
    if flatpak:
        methods.append({"type": "flatpak", "id": flatpak})
    if order:
        methods.sort(key=lambda m: order.index(m["type"]) if m["type"] in order else len(order))
    first_pkgs = next((m["packages"] for m in methods if m.get("packages")), [])
    APPS.append({"id": aid, "name": name, "summary": summary, "category": cat, "icons": list(icons) + [aid],
                 "popular": popular, "check": check or (first_pkgs[0] if first_pkgs else None),
                 "methods": methods, "post": post or [], "color": CAT_COLOR.get(cat, "blue"),
                 "glyph": glyph or CAT_GLYPH.get(cat, "application-x-executable-symbolic"), "arch": arch})


CHROMIUM_NO_REPO = 'printf \'repo_add_once="false"\\nrepo_reenable_on_distupgrade="false"\\n\' > /etc/default/{name}'

# ---------------------------------------------------------------- browsers
A("firefox", "Firefox", "Fast, private browser from Mozilla (latest release).", "browsers",
  ("firefox", "org.mozilla.firefox"), popular=True, apt="firefox", flatpak="org.mozilla.firefox",
  vendor=("Mozilla APT repository", [
      "install -d -m 0755 /etc/apt/keyrings",
      "download https://packages.mozilla.org/apt/repo-signing-key.gpg /etc/apt/keyrings/packages.mozilla.org.asc",
      "rm -f /etc/apt/sources.list.d/mozilla.list",
      "write_source mozilla <<'EOF'", "Types: deb", "URIs: https://packages.mozilla.org/apt", "Suites: mozilla",
      "Components: main", "Signed-By: /etc/apt/keyrings/packages.mozilla.org.asc", "EOF",
      "printf 'Package: *\\nPin: origin packages.mozilla.org\\nPin-Priority: 1000\\n' > /etc/apt/preferences.d/mozilla",
      "apt_update", "apt_install firefox"], "firefox"))
A("firefox-esr", "Firefox ESR", "Debian's default Firefox with extended support.", "browsers", ("firefox-esr",), apt="firefox-esr")
A("chromium", "Chromium", "Open-source browser that Chrome is based on.", "browsers", ("chromium", "org.chromium.Chromium"),
  apt="chromium", flatpak="org.chromium.Chromium")
A("chrome", "Google Chrome", "Google's web browser.", "browsers", ("google-chrome",), popular=True, arch=("amd64",),
  extrepo=("google_chrome", "non-free", "google-chrome-stable", [CHROMIUM_NO_REPO.format(name="google-chrome")]),
  deb=("https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb", "google-chrome-stable"))
A("brave", "Brave", "Privacy browser with built-in ad blocking.", "browsers", ("brave-browser", "com.brave.Browser"), popular=True,
  extrepo=("brave_release", "main", "brave-browser"), flatpak="com.brave.Browser",
  vendor=("Brave repository", _repo("brave-browser-release", "https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg",
                                    "/usr/share/keyrings/brave-browser-archive-keyring.gpg", "https://brave-browser-apt-release.s3.brave.com/",
                                    "stable", arch="amd64 arm64") + ["apt_install brave-browser"], "brave-browser"))
A("edge", "Microsoft Edge", "Microsoft's Chromium-based browser.", "browsers", ("microsoft-edge",), arch=("amd64",),
  extrepo=("edge", "non-free", "microsoft-edge-stable", [CHROMIUM_NO_REPO.format(name="microsoft-edge")]), flatpak="com.microsoft.Edge",
  vendor=("Microsoft repository", [CHROMIUM_NO_REPO.format(name="microsoft-edge")] + _repo(
      "microsoft-edge", "https://packages.microsoft.com/keys/microsoft.asc", "/usr/share/keyrings/microsoft-edge.gpg",
      "https://packages.microsoft.com/repos/edge", "stable", arch="amd64") + ["apt_install microsoft-edge-stable"], "microsoft-edge-stable"))
A("vivaldi", "Vivaldi", "Feature-packed, highly customizable browser.", "browsers", ("vivaldi",), flatpak="com.vivaldi.Vivaldi",
  vendor=("Vivaldi repository", [CHROMIUM_NO_REPO.format(name="vivaldi")] + _repo(
      "vivaldi", "https://repo.vivaldi.com/archive/linux_signing_key.pub", "/usr/share/keyrings/vivaldi.gpg",
      "https://repo.vivaldi.com/archive/deb/", "stable") + ["apt_install vivaldi-stable"], "vivaldi-stable"))
A("opera", "Opera", "Browser with a free built-in VPN.", "browsers", ("opera",), arch=("amd64",),
  extrepo=("opera_stable", "non-free", "opera-stable", ["echo 'opera-stable opera-stable/add-deb-source boolean false' | debconf-set-selections"]),
  flatpak="com.opera.Opera")
A("librewolf", "LibreWolf", "Firefox fork focused on privacy and security.", "browsers", ("librewolf", "io.gitlab.librewolf-community"),
  extrepo=("librewolf", "main", "librewolf"), flatpak="io.gitlab.librewolf-community")
A("floorp", "Floorp", "Customizable Firefox-based browser.", "browsers", ("floorp", "one.ablaze.floorp"), flatpak="one.ablaze.floorp",
  vendor=("Floorp PPA", ["add_key https://ppa.floorp.app/KEY.gpg /usr/share/keyrings/Floorp.gpg",
                         "download https://ppa.floorp.app/Floorp.list /etc/apt/sources.list.d/Floorp.list", "apt_update",
                         "apt_install floorp"], "floorp"))
A("zen", "Zen Browser", "Calm, beautiful Firefox-based browser.", "browsers", ("app.zen_browser.zen",), flatpak="app.zen_browser.zen")
A("tor", "Tor Browser", "Browse anonymously through the Tor network.", "browsers", ("torbrowser", "org.torproject.torbrowser-launcher"),
  apt="torbrowser-launcher", nonfree=True, flatpak="org.torproject.torbrowser-launcher")
A("epiphany", "GNOME Web", "Simple, clean browser for GNOME.", "browsers", ("org.gnome.Epiphany",), apt="epiphany-browser")
A("falkon", "Falkon", "Lightweight Qt web browser from KDE.", "browsers", ("falkon", "org.kde.falkon"), apt="falkon")

# ------------------------------------------------------------- internet
A("thunderbird", "Thunderbird", "Email, calendar and contacts.", "internet", ("thunderbird", "org.mozilla.Thunderbird"), popular=True,
  apt="thunderbird", flatpak="org.mozilla.Thunderbird", glyph="mail-unread-symbolic")
A("evolution", "Evolution", "Email and groupware suite for GNOME.", "internet", ("org.gnome.Evolution", "evolution"), apt="evolution")
A("telegram", "Telegram", "Fast and secure messaging.", "internet", ("telegram", "org.telegram.desktop"), popular=True,
  apt="telegram-desktop", flatpak="org.telegram.desktop", glyph="mail-send-symbolic")
A("signal", "Signal", "Private messenger with end-to-end encryption.", "internet", ("signal-desktop", "org.signal.Signal"), arch=("amd64",),
  extrepo=("signal", "non-free", "signal-desktop"), flatpak="org.signal.Signal", glyph="dialog-password-symbolic")
A("element", "Element", "Secure Matrix chat client.", "internet", ("element-desktop", "im.riot.Riot"),
  extrepo=("element.io", "main", "element-desktop"), flatpak="im.riot.Riot")
A("discord", "Discord", "Voice, video and text chat.", "internet", ("discord", "com.discordapp.Discord"), popular=True, arch=("amd64",),
  deb=("https://discord.com/api/download?platform=linux&format=deb", "discord"), flatpak="com.discordapp.Discord",
  glyph="audio-speakers-symbolic")
A("slack", "Slack", "Team chat and collaboration.", "internet", ("slack", "com.slack.Slack"), arch=("amd64",),
  extrepo=("slack", "non-free", "slack-desktop"), flatpak="com.slack.Slack")
A("zoom", "Zoom", "Video meetings.", "internet", ("Zoom", "us.zoom.Zoom"), arch=("amd64",),
  deb=("https://zoom.us/client/latest/zoom_amd64.deb", "zoom"), flatpak="us.zoom.Zoom", glyph="camera-web-symbolic")
A("transmission", "Transmission", "Simple BitTorrent client.", "internet", ("transmission",), apt="transmission-gtk", glyph="folder-download-symbolic")
A("qbittorrent", "qBittorrent", "Feature-rich BitTorrent client.", "internet", ("qbittorrent", "org.qbittorrent.qBittorrent"),
  apt="qbittorrent", flatpak="org.qbittorrent.qBittorrent", glyph="folder-download-symbolic")
A("filezilla", "FileZilla", "FTP, FTPS and SFTP client.", "internet", ("filezilla",), apt="filezilla", glyph="network-server-symbolic")
A("remmina", "Remmina", "Remote desktop client (RDP, VNC, SSH).", "internet", ("org.remmina.Remmina", "remmina"),
  apt="remmina remmina-plugin-rdp remmina-plugin-vnc", glyph="video-display-symbolic")
A("anydesk", "AnyDesk", "Remote desktop software.", "internet", ("anydesk",), extrepo=("anydesk", "non-free", "anydesk"),
  glyph="video-display-symbolic")
A("teamviewer", "TeamViewer", "Remote control and support.", "internet", ("TeamViewer", "teamviewer"),
  extrepo=("teamviewer_default", "non-free", "teamviewer"), glyph="video-display-symbolic")
A("syncthing", "Syncthing", "Continuous file synchronization between devices.", "internet", ("syncthing",), apt="syncthing",
  glyph="emblem-synchronizing-symbolic")
A("nextcloud", "Nextcloud Desktop", "Sync files with your Nextcloud server.", "internet", ("Nextcloud", "com.nextcloud.desktopclient.nextcloud"),
  apt="nextcloud-desktop", glyph="network-server-symbolic")

# --------------------------------------------------------------- office
A("libreoffice", "LibreOffice", "Full office suite: Writer, Calc, Impress.", "office", ("libreoffice-startcenter", "org.libreoffice.LibreOffice"),
  popular=True, apt="libreoffice libreoffice-gtk3", flatpak="org.libreoffice.LibreOffice")
A("onlyoffice", "ONLYOFFICE", "Office suite with great MS Office compatibility.", "office", ("onlyoffice-desktopeditors", "org.onlyoffice.desktopeditors"),
  arch=("amd64",), extrepo=("onlyoffice-desktopeditors", "main", "onlyoffice-desktopeditors"), flatpak="org.onlyoffice.desktopeditors")
A("okular", "Okular", "Universal document viewer from KDE.", "office", ("okular", "org.kde.okular"), apt="okular")
A("evince", "Document Viewer", "PDF and document viewer for GNOME.", "office", ("org.gnome.Evince", "evince"), apt="evince")
A("xournalpp", "Xournal++", "Handwriting notes and PDF annotation.", "office", ("com.github.xournalpp.xournalpp",), apt="xournalpp")
A("calibre", "Calibre", "E-book library manager and converter.", "office", ("calibre-gui", "calibre"), apt="calibre")
A("obsidian", "Obsidian", "Markdown knowledge base.", "office", ("md.obsidian.Obsidian", "obsidian"), flatpak="md.obsidian.Obsidian")
A("joplin", "Joplin", "Open-source note taking with sync.", "office", ("net.cozic.joplin_desktop",), flatpak="net.cozic.joplin_desktop")
A("zotero", "Zotero", "Research and citation manager.", "office", ("org.zotero.Zotero",), flatpak="org.zotero.Zotero")
A("gnucash", "GnuCash", "Personal and small-business accounting.", "office", ("gnucash", "org.gnucash.GnuCash"), apt="gnucash")
A("scribus", "Scribus", "Desktop publishing.", "office", ("scribus",), apt="scribus")

# ----------------------------------------------------------- multimedia
A("vlc", "VLC", "Plays almost every audio and video format.", "media", ("vlc", "org.videolan.VLC"), popular=True, apt="vlc",
  flatpak="org.videolan.VLC", glyph="media-playback-start-symbolic")
A("codecs", "Multimedia Codecs", "FFmpeg and GStreamer plugins for all common formats.", "media", (), popular=True,
  apt="libavcodec-extra ffmpeg gstreamer1.0-libav gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-vaapi",
  glyph="audio-card-symbolic")
A("mpv", "mpv", "Minimal, powerful media player.", "media", ("mpv",), apt="mpv", glyph="media-playback-start-symbolic")
A("celluloid", "Celluloid", "Simple GTK front-end for mpv.", "media", ("io.github.celluloid_player.Celluloid",), apt="celluloid",
  glyph="media-playback-start-symbolic")
A("haruna", "Haruna", "Qt video player built on mpv.", "media", ("haruna", "org.kde.haruna"), apt="haruna", glyph="media-playback-start-symbolic")
A("smplayer", "SMPlayer", "Media player with many options.", "media", ("smplayer",), apt="smplayer", glyph="media-playback-start-symbolic")
A("audacious", "Audacious", "Lightweight audio player.", "media", ("audacious",), apt="audacious", glyph="audio-speakers-symbolic")
A("rhythmbox", "Rhythmbox", "Music library and player.", "media", ("org.gnome.Rhythmbox3", "rhythmbox"), apt="rhythmbox", glyph="audio-speakers-symbolic")
A("lollypop", "Lollypop", "Modern music player for GNOME.", "media", ("org.gnome.Lollypop",), apt="lollypop", glyph="audio-speakers-symbolic")
A("strawberry", "Strawberry", "Music player for large collections.", "media", ("strawberry", "org.strawberrymusicplayer.strawberry"), apt="strawberry",
  glyph="audio-speakers-symbolic")
A("elisa", "Elisa", "Simple music player from KDE.", "media", ("elisa", "org.kde.elisa"), apt="elisa", glyph="audio-speakers-symbolic")
A("spotify", "Spotify", "Music streaming.", "media", ("spotify-client", "com.spotify.Client"), popular=True,
  extrepo=("spotify", "non-free", "spotify-client"), flatpak="com.spotify.Client", glyph="audio-speakers-symbolic")
A("audacity", "Audacity", "Record and edit audio.", "media", ("audacity", "org.audacityteam.Audacity"), apt="audacity", glyph="audio-card-symbolic")
A("ardour", "Ardour", "Professional digital audio workstation.", "media", ("ardour",), apt="ardour", glyph="audio-card-symbolic")
A("kdenlive", "Kdenlive", "Professional video editor.", "media", ("kdenlive", "org.kde.kdenlive"), apt="kdenlive", flatpak="org.kde.kdenlive",
  glyph="camera-web-symbolic")
A("shotcut", "Shotcut", "Cross-platform video editor.", "media", ("org.shotcut.Shotcut", "shotcut"), apt="shotcut", glyph="camera-web-symbolic")
A("openshot", "OpenShot", "Easy video editor.", "media", ("openshot-qt", "org.openshot.OpenShot"), apt="openshot-qt", glyph="camera-web-symbolic")
A("obs", "OBS Studio", "Screen recording and live streaming.", "media", ("com.obsproject.Studio", "obs"), popular=True, apt="obs-studio",
  flatpak="com.obsproject.Studio", glyph="camera-web-symbolic")
A("handbrake", "HandBrake", "Video transcoder.", "media", ("fr.handbrake.ghb", "handbrake"), apt="handbrake", glyph="media-optical-symbolic")
A("easyeffects", "EasyEffects", "Audio effects for PipeWire.", "media", ("com.github.wwmm.easyeffects",), apt="easyeffects", glyph="audio-speakers-symbolic")
A("kodi", "Kodi", "Media center.", "media", ("kodi",), apt="kodi", glyph="video-display-symbolic")

# ------------------------------------------------------------- graphics
A("gimp", "GIMP", "Advanced image editor.", "graphics", ("gimp", "org.gimp.GIMP"), popular=True, apt="gimp", flatpak="org.gimp.GIMP")
A("inkscape", "Inkscape", "Vector graphics editor.", "graphics", ("org.inkscape.Inkscape", "inkscape"), apt="inkscape", flatpak="org.inkscape.Inkscape")
A("krita", "Krita", "Digital painting studio.", "graphics", ("krita", "org.kde.krita"), apt="krita", flatpak="org.kde.krita")
A("blender", "Blender", "3D modelling, animation and rendering.", "graphics", ("blender", "org.blender.Blender"), popular=True, apt="blender",
  flatpak="org.blender.Blender")
A("darktable", "darktable", "RAW photo workflow.", "graphics", ("darktable", "org.darktable.Darktable"), apt="darktable", glyph="camera-photo-symbolic")
A("rawtherapee", "RawTherapee", "RAW image processing.", "graphics", ("rawtherapee", "com.rawtherapee.RawTherapee"), apt="rawtherapee", glyph="camera-photo-symbolic")
A("digikam", "digiKam", "Professional photo management.", "graphics", ("digikam", "org.kde.digikam"), apt="digikam", glyph="camera-photo-symbolic")
A("shotwell", "Shotwell", "Photo organizer for GNOME.", "graphics", ("shotwell", "org.gnome.Shotwell"), apt="shotwell", glyph="camera-photo-symbolic")
A("pinta", "Pinta", "Simple drawing and image editing.", "graphics", ("pinta", "com.github.PintaProject.Pinta"), apt="pinta")
A("freecad", "FreeCAD", "Parametric 3D CAD modeller.", "graphics", ("freecad", "org.freecad.FreeCAD"), apt="freecad", glyph="applications-engineering-symbolic")
A("librecad", "LibreCAD", "2D CAD drawing.", "graphics", ("librecad",), apt="librecad", glyph="applications-engineering-symbolic")
A("googleearth", "Google Earth Pro", "Explore the planet in 3D.", "graphics", ("google-earth-pro",), arch=("amd64",),
  deb=("https://dl.google.com/dl/earth/client/current/google-earth-pro-stable_current_amd64.deb", "google-earth-pro-stable"),
  glyph="find-location-symbolic")

# ---------------------------------------------------------- development
A("devtools", "Developer Essentials", "Compilers, git, make, cmake and pkg-config.", "dev", (), popular=True,
  apt="build-essential git curl wget make cmake pkg-config", glyph="utilities-terminal-symbolic")
A("vscode", "Visual Studio Code", "Microsoft's code editor.", "dev", ("vscode", "code", "com.visualstudio.code"), popular=True,
  extrepo=("vscode", "non-free", "code", ["echo 'code code/add-microsoft-repo boolean false' | debconf-set-selections"]),
  flatpak="com.visualstudio.code",
  vendor=("Microsoft repository", ["echo 'code code/add-microsoft-repo boolean false' | debconf-set-selections"] + _repo(
      "vscode", "https://packages.microsoft.com/keys/microsoft.asc", "/usr/share/keyrings/microsoft-vscode.gpg",
      "https://packages.microsoft.com/repos/code", "stable", arch="amd64 arm64 armhf") + ["apt_install code"], "code"))
A("vscodium", "VSCodium", "VS Code without Microsoft telemetry.", "dev", ("vscodium", "codium", "com.vscodium.codium"),
  extrepo=("vscodium", "main", "codium"), flatpak="com.vscodium.codium")
A("docker", "Docker Engine", "Official Docker CE with Compose and Buildx.", "dev", ("docker",), popular=True,
  extrepo=("docker-ce", "main", "docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
           ["apt-get remove -y docker.io docker-doc docker-compose podman-docker containerd runc 2>/dev/null || true",
            "rm -f /etc/apt/sources.list.d/docker.list /etc/apt/sources.list.d/docker.sources"]),
  apt="docker.io docker-compose", order=("extrepo", "apt"), post=['usermod -aG docker "$TARGET_USER"', "info 'Log out and back in to use docker without sudo.'"],
  glyph="network-server-symbolic")
A("podman", "Podman", "Daemonless containers (Docker compatible).", "dev", (), apt="podman podman-compose", glyph="network-server-symbolic")
A("virtualbox", "VirtualBox", "Oracle VirtualBox virtual machines (amd64).", "dev", ("virtualbox",), arch=("amd64",),
  vendor=("Oracle repository", _repo("virtualbox", "https://www.virtualbox.org/download/oracle_vbox_2016.asc",
                                     "/usr/share/keyrings/oracle-virtualbox-2016.gpg", "https://download.virtualbox.org/virtualbox/debian",
                                     "$VENDOR_CODENAME", components="contrib", arch="amd64") + [
      "VB=$(apt-cache pkgnames virtualbox- | grep -E '^virtualbox-[0-9.]+$' | sort -V | tail -n1)",
      '[ -n "$VB" ] || fail "No VirtualBox package found in the Oracle repository."',
      'apt_install dkms "linux-headers-$(uname -r)" "$VB"', 'usermod -aG vboxusers "$TARGET_USER"'], "virtualbox-7.2"),
  glyph="computer-symbolic")
A("virtmanager", "Virtual Machine Manager", "KVM/QEMU virtual machines (virt-manager).", "dev", ("virt-manager",), popular=True,
  apt="virt-manager qemu-system libvirt-daemon-system", post=['usermod -aG libvirt "$TARGET_USER"', "systemctl enable --now libvirtd"],
  glyph="computer-symbolic")
A("boxes", "GNOME Boxes", "Simple virtual machines.", "dev", ("org.gnome.Boxes",), apt="gnome-boxes", glyph="computer-symbolic")
A("geany", "Geany", "Fast, lightweight IDE.", "dev", ("geany",), apt="geany", glyph="text-editor-symbolic")
A("kate", "Kate", "Advanced text editor from KDE.", "dev", ("kate", "org.kde.kate"), apt="kate", glyph="text-editor-symbolic")
A("builder", "GNOME Builder", "IDE for GNOME applications.", "dev", ("org.gnome.Builder",), apt="gnome-builder")
A("meld", "Meld", "Visual diff and merge tool.", "dev", ("org.gnome.Meld", "meld"), apt="meld", glyph="edit-copy-symbolic")
A("python", "Python tools", "pip, venv and pipx for Python development.", "dev", (), apt="python3-pip python3-venv pipx python3-dev")
A("nodejs", "Node.js", "JavaScript runtime with npm.", "dev", (), apt="nodejs npm")
A("golang", "Go", "The Go programming language.", "dev", (), apt="golang")
A("rust", "Rust", "rustc and cargo from Debian.", "dev", (), apt="rustc cargo")
A("java", "Java (OpenJDK)", "Default Java development kit.", "dev", (), apt="default-jdk")
A("androidstudio", "Android Studio", "Official Android IDE.", "dev", ("com.google.AndroidStudio",), flatpak="com.google.AndroidStudio")
A("dbeaver", "DBeaver", "Universal database tool.", "dev", ("io.dbeaver.DBeaverCommunity",), flatpak="io.dbeaver.DBeaverCommunity")
A("pycharm", "PyCharm Community", "Python IDE from JetBrains.", "dev", ("com.jetbrains.PyCharm-Community",), flatpak="com.jetbrains.PyCharm-Community")

# --------------------------------------------------------------- system
A("timeshift", "Timeshift", "System snapshots and rollback.", "system", ("timeshift",), popular=True, apt="timeshift", glyph="document-revert-symbolic")
A("gparted", "GParted", "Partition editor.", "system", ("gparted",), apt="gparted", glyph="drive-harddisk-symbolic")
A("disks", "Disks", "Manage drives, SMART data and disk images.", "system", ("org.gnome.DiskUtility", "gnome-disk-utility"), apt="gnome-disk-utility",
  glyph="drive-harddisk-symbolic")
A("baobab", "Disk Usage Analyzer", "See what fills your disk.", "system", ("org.gnome.baobab", "baobab"), apt="baobab", glyph="drive-harddisk-symbolic")
A("synaptic", "Synaptic", "Classic graphical package manager.", "system", ("synaptic",), apt="synaptic", glyph="package-x-generic-symbolic")
A("gnomesoftware", "GNOME Software", "App store with Flatpak support.", "system", ("org.gnome.Software",), apt="gnome-software gnome-software-plugin-flatpak",
  glyph="system-software-install-symbolic")
A("discover", "Plasma Discover", "KDE app store with Flatpak support.", "system", ("plasmadiscover", "org.kde.discover"),
  apt="plasma-discover plasma-discover-backend-flatpak", glyph="system-software-install-symbolic")
A("bleachbit", "BleachBit", "Advanced disk and privacy cleaner.", "system", ("bleachbit", "org.bleachbit.BleachBit"), apt="bleachbit", glyph="user-trash-symbolic")
A("btop", "btop and htop", "Beautiful terminal system monitors.", "system", ("btop", "htop"), apt="btop htop", glyph="utilities-terminal-symbolic")
A("missioncenter", "Mission Center", "Task manager with CPU, GPU and disk graphs.", "system", ("io.missioncenter.MissionCenter",),
  flatpak="io.missioncenter.MissionCenter")
A("cpux", "CPU-X", "Detailed CPU, motherboard and memory info.", "system", ("cpu-x",), apt="cpu-x", glyph="computer-symbolic")
A("gnometweaks", "GNOME Tweaks", "Advanced GNOME settings.", "system", ("org.gnome.tweaks",), apt="gnome-tweaks", glyph="preferences-other-symbolic")
A("extensions", "Extension Manager", "Browse and install GNOME Shell extensions.", "system", ("com.mattjakeman.ExtensionManager",),
  apt="gnome-shell-extension-manager", flatpak="com.mattjakeman.ExtensionManager")
A("dconf", "dconf Editor", "Low-level desktop settings editor.", "system", ("ca.desrt.dconf-editor",), apt="dconf-editor", glyph="preferences-other-symbolic")
A("flatseal", "Flatseal", "Manage Flatpak permissions.", "system", ("com.github.tchx84.Flatseal",), flatpak="com.github.tchx84.Flatseal",
  glyph="security-medium-symbolic")
A("dejadup", "Déjà Dup Backups", "Simple encrypted backups.", "system", ("org.gnome.DejaDup",), apt="deja-dup", glyph="document-save-symbolic")
A("gnomefirmware", "Firmware", "Update device firmware (fwupd).", "system", ("org.gnome.Firmware",), apt="gnome-firmware fwupd", glyph="emblem-system-symbolic")
A("kitty", "kitty", "Fast GPU-accelerated terminal.", "system", ("kitty",), apt="kitty", glyph="utilities-terminal-symbolic")
A("tilix", "Tilix", "Tiling terminal emulator.", "system", ("com.gexperts.Tilix",), apt="tilix", glyph="utilities-terminal-symbolic")
A("fastfetch", "fastfetch", "System information in the terminal.", "system", (), apt="fastfetch", glyph="utilities-terminal-symbolic")

# ------------------------------------------------------------- security
A("keepassxc", "KeePassXC", "Offline password manager.", "security", ("keepassxc", "org.keepassxc.KeePassXC"), popular=True, apt="keepassxc",
  glyph="dialog-password-symbolic")
A("bitwarden", "Bitwarden", "Cloud password manager.", "security", ("com.bitwarden.desktop",), flatpak="com.bitwarden.desktop", glyph="dialog-password-symbolic")
A("gufw", "Firewall (UFW + Gufw)", "Simple firewall with a graphical interface.", "security", ("gufw",), popular=True, apt="ufw gufw",
  post=["ufw --force enable"], glyph="security-high-symbolic")
A("clamtk", "ClamTk Antivirus", "Virus scanner based on ClamAV.", "security", ("clamtk",), apt="clamav clamav-freshclam clamtk")
A("firejail", "Firejail", "Sandbox applications.", "security", ("firetools",), apt="firejail firetools")
A("wireguard", "WireGuard", "Modern VPN (tools + NetworkManager support).", "security", (), apt="wireguard-tools", glyph="network-vpn-symbolic")
A("openvpn", "OpenVPN for NetworkManager", "Import .ovpn VPN profiles.", "security", (), apt="network-manager-openvpn-gnome", glyph="network-vpn-symbolic")
A("seahorse", "Passwords and Keys", "Manage GPG and SSH keys.", "security", ("org.gnome.seahorse.Application", "seahorse"), apt="seahorse",
  glyph="dialog-password-symbolic")
A("metadatacleaner", "Metadata Cleaner", "Remove hidden metadata from files.", "security", ("fr.romainvigier.MetadataCleaner",), apt="metadata-cleaner")
A("gtkhash", "GtkHash", "Checksum calculator.", "security", ("org.gtkhash.gtkhash",), apt="gtkhash")

# --------------------------------------------------------------- gaming
A("steam", "Steam", "Valve's gaming platform.", "games", ("steam", "com.valvesoftware.Steam"), popular=True, arch=("amd64",),
  apt="steam-installer mesa-vulkan-drivers libglx-mesa0:i386 mesa-vulkan-drivers:i386 libgl1-mesa-dri:i386", nonfree=True,
  flatpak="com.valvesoftware.Steam")
A("lutris", "Lutris", "Open gaming platform for Wine, emulators and more.", "games", ("lutris", "net.lutris.Lutris"), apt="lutris",
  flatpak="net.lutris.Lutris")
A("heroic", "Heroic Games Launcher", "Epic, GOG and Amazon games.", "games", ("com.heroicgameslauncher.hgl",), flatpak="com.heroicgameslauncher.hgl")
A("bottles", "Bottles", "Run Windows software in managed bottles.", "games", ("com.usebottles.bottles",), flatpak="com.usebottles.bottles")
A("wine", "Wine", "Run Windows applications.", "games", ("wine",), apt="wine wine64", extrepo=("winehq", "main", "winehq-stable"))
A("gamemode", "GameMode + MangoHud", "Performance mode and FPS overlay.", "games", (), apt="gamemode mangohud")
A("protonup", "ProtonUp-Qt", "Install Proton-GE and Wine-GE.", "games", ("net.davidotek.pupgui2",), flatpak="net.davidotek.pupgui2")
A("retroarch", "RetroArch", "Frontend for emulators.", "games", ("retroarch",), apt="retroarch")
A("luanti", "Luanti (Minetest)", "Open-source voxel game engine.", "games", ("org.luanti.luanti", "net.minetest.minetest", "minetest"),
  apt="luanti", flatpak="org.luanti.luanti")
A("supertuxkart", "SuperTuxKart", "Kart racing game.", "games", ("supertuxkart",), apt="supertuxkart")
A("0ad", "0 A.D.", "Historical real-time strategy.", "games", ("0ad",), apt="0ad")
A("dolphinemu", "Dolphin Emulator", "GameCube and Wii emulator.", "games", ("dolphin-emu",), apt="dolphin-emu")
A("prism", "Prism Launcher", "Minecraft launcher.", "games", ("org.prismlauncher.PrismLauncher",), flatpak="org.prismlauncher.PrismLauncher")

APP_INDEX = {a["id"]: a for a in APPS}


def all_packages():
    pkgs = set()
    for app in APPS:
        for m in app["methods"]:
            if m["type"] == "apt":
                pkgs.update(p.split(":")[0] for p in m["packages"])
    return pkgs


def available_methods(app, candidates, extrepo_names, arch, has_flatpak_remote=True):
    """Methods that can work on this system, preserving preference order."""
    res = []
    if app.get("arch") and arch not in app["arch"]:
        flat = [m for m in app["methods"] if m["type"] == "flatpak"]
        return flat
    for m in app["methods"]:
        t = m["type"]
        if t == "apt":
            # contrib/non-free packages may only appear after the components are enabled
            if m.get("nonfree") or all(candidates.get(p.split(":")[0]) for p in m["packages"]):
                res.append(m)
        elif t == "extrepo":
            if extrepo_names is None or m["repo"] in extrepo_names:
                res.append(m)
        else:
            res.append(m)
    return res


def method_label(m):
    return {"apt": "Debian package", "extrepo": f"Vendor repository (extrepo: {m.get('repo')})",
            "vendor": m.get("label", "Vendor repository"), "deb": "Vendor .deb download",
            "flatpak": "Flathub (Flatpak)"}[m["type"]]


def install_steps(app, m):
    name = app["name"]
    steps = []
    if m["type"] == "apt":
        code = []
        if m.get("nonfree"):
            code += ["enable_components contrib non-free non-free-firmware"]
            if any(":i386" in p for p in m["packages"]):
                code += ["dpkg --add-architecture i386"]
            code += ["apt_update"]
        code += [f"apt_install {' '.join(shq(p) for p in m['packages'])}"]
        steps.append((f"Installing {name}", code))
    elif m["type"] == "extrepo":
        steps.append((f"Enabling the {m['repo']} repository (extrepo)", [
            "ensure_pkg extrepo",
            f"extrepo_has {shq(m['repo'])} || fail {shq(m['repo'] + ' is not offered by extrepo for this Debian release - choose another source.')}",
        ] + list(m.get("pre", [])) + [f"extrepo_enable {shq(m['repo'])} {shq(m['policy'])}", "apt_update"]))
        steps.append((f"Installing {name}", f"apt_install {' '.join(shq(p) for p in m['packages'])}"))
    elif m["type"] == "vendor":
        code = list(m["steps"])
        if app.get("arch"):
            code.insert(0, "need_arch " + " ".join(app["arch"]))
        steps.append((f"Installing {name} from {m['label']}", code))
    elif m["type"] == "deb":
        tmp = f"/tmp/debos-{app['id']}.deb"
        code = ([f"need_arch {' '.join(app['arch'])}"] if app.get("arch") else []) + [
            f"download {shq(m['url'])} {tmp}", f"apt_install {tmp}", f"rm -f {tmp}"]
        steps.append((f"Installing {name} (.deb)", code))
    elif m["type"] == "flatpak":
        steps.append(("Setting up Flathub", ["ensure_pkg flatpak",
                                             "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"]))
        steps.append((f"Installing {name} from Flathub", f"flatpak install -y --noninteractive flathub {shq(m['id'])}"))
    if app.get("post") and m["type"] != "flatpak":
        steps.append((f"Finishing {name}", list(app["post"])))
    return steps


def remove_steps(app, installed_pkgs, installed_flatpaks):
    steps = []
    pkgs = []
    for m in app["methods"]:
        for p in m.get("packages", []):
            base = p.split(":")[0]
            if base in installed_pkgs and base not in pkgs and base not in ("mesa-vulkan-drivers", "libglx-mesa0", "libgl1-mesa-dri", "ffmpeg"):
                pkgs.append(base)
    if pkgs:
        steps.append((f"Removing {app['name']}", [f"apt-get purge {' '.join(shq(p) for p in pkgs)}", "apt-get autoremove --purge -y"]))
    for m in app["methods"]:
        if m["type"] == "flatpak" and m["id"] in installed_flatpaks:
            steps.append((f"Removing {app['name']} (Flatpak)", f"flatpak uninstall -y --noninteractive {shq(m['id'])}"))
    return steps


def extrepo_list():
    """Names and descriptions offered by `extrepo search` (None if extrepo is missing)."""
    import shutil
    from .util import run
    if not shutil.which("extrepo"):
        return None
    code, text = run(["extrepo", "search", "."], timeout=90)
    repos, cur = {}, None
    for line in text.splitlines():
        if line.startswith("Found ") and line.endswith(":"):
            cur = line[6:-1]
            repos[cur] = {"name": cur, "description": "", "policy": "main"}
        elif cur and line.startswith("description:"):
            repos[cur]["description"] = line.split(":", 1)[1].strip().strip("'\"|>-").strip()
        elif cur and line.startswith("  ") and repos[cur]["description"] == "":
            repos[cur]["description"] = line.strip()
        elif cur and line.startswith("policy:"):
            repos[cur]["policy"] = line.split(":", 1)[1].strip()
    return repos
