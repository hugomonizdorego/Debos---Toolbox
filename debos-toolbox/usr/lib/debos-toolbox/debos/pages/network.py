import os
import re
import shutil

from gi.repository import Gtk

from .. import widgets as W
from ..core.tasks import Task
from ..core.util import read_file, run, shq
from ..i18n import _
from .base import Page

DNS = [("auto", "Automatic (from your network)", "", ""),
       ("cloudflare", "Cloudflare (fast, private)", "1.1.1.1 1.0.0.1", "2606:4700:4700::1111 2606:4700:4700::1001"),
       ("google", "Google", "8.8.8.8 8.8.4.4", "2001:4860:4860::8888 2001:4860:4860::8844"),
       ("quad9", "Quad9 (blocks malware)", "9.9.9.9 149.112.112.112", "2620:fe::fe 2620:fe::9"),
       ("adguard", "AdGuard (blocks ads)", "94.140.14.14 94.140.15.15", "2a10:50c0::ad1:ff 2a10:50c0::ad2:ff"),
       ("opendns", "OpenDNS", "208.67.222.222 208.67.220.220", "2620:119:35::35 2620:119:53::53")]


def net_info(public=False):
    rows = []
    for line in run(["ip", "-o", "-4", "addr", "show"])[1].splitlines():
        p = line.split()
        if len(p) > 3 and p[1] != "lo":
            rows.append((p[1], p[3]))
    for line in run(["ip", "-o", "-6", "addr", "show", "scope", "global"])[1].splitlines():
        p = line.split()
        if len(p) > 3:
            rows.append((p[1] + " (IPv6)", p[3]))
    gw = run(["ip", "route", "show", "default"])[1].split("\n")[0]
    rows.append(("Gateway", gw or "none"))
    dns = [l.split()[1] for l in read_file("/etc/resolv.conf").splitlines() if l.startswith("nameserver") and len(l.split()) > 1]
    rows.append(("DNS", ", ".join(dns) or "unknown"))
    if shutil.which("nmcli"):
        act = run(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"])[1]
        conns = [a.replace(":", " / ") for a in act.splitlines() if not a.endswith(":lo")]
        if conns:
            rows.append(("Connections", "; ".join(conns)))
    if public:
        ip = run(["curl", "-s", "--max-time", "6", "https://ifconfig.me"], timeout=8)[1].strip()
        rows.append(("Public IP", ip or "unavailable"))
    return rows


class Network(Page):
    ID = "network"
    TITLE = "Network"
    SUBTITLE = "Diagnostics, DNS, firewall and remote access"
    ICON = "network-wireless-symbolic"
    KEYWORDS = "network wifi dns firewall ufw ssh rdp vpn ip speed test hostname mac"

    def build(self):
        self.add_action(W.button("Show public IP", "network-transmit-receive-symbolic", "", lambda: self.load(True)))
        row = W.hbox(16)
        self.content.append(row)
        self.info = W.Card("Network information")
        self.info.set_hexpand(True)
        row.append(self.info)
        diag = W.Card("Diagnostics")
        diag.set_size_request(360, -1)
        for text, steps in (("Speed test", [("speedtest-cli", ["ensure_pkg speedtest-cli", "as_user speedtest-cli --secure"])]),
                            ("Ping test", [("Ping", ["ping -c 4 deb.debian.org", "ping -c 4 1.1.1.1"])]),
                            ("Wi-Fi networks and LAN hosts", [("Scan", [
                                "ensure_pkg network-manager iw rfkill nmap", "rfkill unblock wifi || true",
                                "nmcli device wifi rescan 2>/dev/null || true; sleep 2; nmcli device wifi list || true",
                                "IFACE=$(ip route show default | awk '{for(i=1;i<=NF;i++) if($i==\"dev\") print $(i+1)}' | head -n1)",
                                "SUBNET=$(ip -o -4 addr show dev \"$IFACE\" 2>/dev/null | awk '{print $4}' | head -n1)",
                                "if [ -n \"$SUBNET\" ]; then info \"Scanning $SUBNET on $IFACE\"; nmap -sn \"$SUBNET\"; else warn 'No IPv4 network.'; fi"])]),
                            ("Restart networking", [("NetworkManager", "systemctl restart NetworkManager")]),
                            ("Saved Wi-Fi passwords", [("Passwords", [
                                "nmcli -t -f NAME,TYPE connection show | awk -F: '$2 ~ /wireless/ {print $1}' | while read -r n; do "
                                "printf '%-32s %s\\n' \"$n\" \"$(nmcli -s -g 802-11-wireless-security.psk connection show \"$n\" 2>/dev/null)\"; done"])])):
            b = W.button(text, kind="", on_click=lambda t=text, s=steps: self.win.run(Task(t, s)))
            b.set_halign(Gtk.Align.FILL)
            diag.add(b)
        row.append(diag)

        dns = self.card("DNS servers", "Applied to the active NetworkManager connection.")
        r = W.hbox(10)
        self.dns = W.dropdown([(k, t) for k, t, _4, _6 in DNS], "cloudflare")
        self.dns.set_hexpand(True)
        r.append(self.dns)
        r.append(W.button(_("Apply"), kind="primary", on_click=self.apply_dns))
        r.append(W.button("Flush DNS cache", on_click=lambda: self.win.run(Task("Flush DNS cache", [("resolvectl", [
            "if command -v resolvectl >/dev/null; then resolvectl flush-caches && ok 'DNS cache flushed'; else warn 'systemd-resolved is not used'; fi"])]))))
        dns.add(r)

        fw = self.card("Firewall (UFW)", "Blocks incoming connections except the services you allow.")
        st = W.hbox(8)
        for text, kind, steps in (
                ("Enable", "primary", [("Enabling UFW", ["ensure_pkg ufw", "ufw default deny incoming", "ufw default allow outgoing", "ufw --force enable",
                                                          "ufw status verbose"])]),
                ("Disable", "", [("Disabling UFW", "ufw disable")]),
                ("Status", "", [("Status", ["ensure_pkg ufw", "ufw status verbose"])]),
                ("Allow SSH", "", [("Rule", ["ensure_pkg ufw", "ufw allow OpenSSH || ufw allow 22/tcp"])]),
                ("Install Gufw", "", [("Gufw", "apt_install gufw")])):
            st.append(W.button(text, kind=kind, on_click=lambda t=text, s=steps: self.win.run(Task(f"Firewall: {t}", s, refresh={"packages"}))))
        fw.add(st)

        remote = self.card("Remote access")
        for i, (title, sub, task) in enumerate((
                ("SSH server", "Log in to this computer from others (OpenSSH).",
                 Task("SSH server", [("Install", "apt_install openssh-server"), ("Enable", "systemctl enable --now ssh"),
                                     ("Firewall", "command -v ufw >/dev/null && ufw allow OpenSSH || true"),
                                     ("Address", "ok \"Connect with: ssh $TARGET_USER@$(hostname -I | awk '{print $1}')\"")], refresh={"packages"})),
                ("Remote desktop server (RDP)", "xrdp with an Xfce session, reachable from Windows Remote Desktop or Remmina.",
                 Task("RDP server", [("Install", "apt_install xrdp xfce4 xfce4-goodies"), ("Configure", [
                     "adduser xrdp ssl-cert 2>/dev/null || true", "echo xfce4-session > /etc/skel/.xsession",
                     "as_user sh -c 'echo xfce4-session > \"$HOME/.xsession\"'", "systemctl enable xrdp", "systemctl restart xrdp",
                     "command -v ufw >/dev/null && ufw allow 3389/tcp || true"]),
                     ("Address", "ok \"RDP: $(hostname -I | awk '{print $1}'):3389 - log out locally before connecting as the same user.\"")],
                     refresh={"packages"})),
                ("Remmina client", "Connect to RDP, VNC and SSH machines.",
                 Task("Remmina", [("Install", "apt_install remmina remmina-plugin-rdp remmina-plugin-vnc")], refresh={"packages"})))):
            remote.add(W.action_row(title, sub, [W.button(_("Install"), kind="primary", small=True, on_click=lambda t=task: self.win.run(t))],
                                    "video-display-symbolic", "info", last=i == 2))

        ident = self.card("Identity")
        hr = W.hbox(10)
        hr.append(W.label("Hostname", "row-title"))
        self.host = Gtk.Entry()
        self.host.set_text(os.uname().nodename)
        self.host.set_hexpand(True)
        hr.append(self.host)
        hr.append(W.button("Change", kind="primary", on_click=self.set_hostname))
        ident.add(hr)
        mr = W.hbox(10)
        mr.append(W.label("MAC address", "row-title"))
        ifaces = sorted(i for i in os.listdir("/sys/class/net") if i != "lo") if os.path.isdir("/sys/class/net") else []
        self.iface = W.dropdown([(i, i) for i in ifaces] or [("", "no interface")], ifaces[0] if ifaces else "")
        self.iface.set_hexpand(True)
        mr.append(self.iface)
        mr.append(W.button("Randomize", on_click=lambda: self.mac("-r")))
        mr.append(W.button("Restore", on_click=lambda: self.mac("-p")))
        ident.add(mr)
        ident.add(W.button("Edit /etc/hosts", kind="ghost", on_click=lambda: self.win.run(Task(
            "Edit /etc/hosts", [("Editing with nano (Ctrl+O saves, Ctrl+X exits)", "nano /etc/hosts")]))))

    def refresh(self):
        self.load(False)

    def load(self, public):
        self.loading(self.info.body)
        self.win.async_call(lambda: net_info(public), self._fill)

    def _fill(self, rows):
        W.clear(self.info.body)
        if isinstance(rows, Exception):
            self.info.add(W.label(str(rows), "err-text"))
            return
        self.info.add(W.kv_grid(rows))

    def apply_dns(self):
        key = W.dd_value(self.dns)
        _k, name, v4, v6 = next(d for d in DNS if d[0] == key)
        if v4:
            mod = f"nmcli connection modify \"$CON\" ipv4.dns {shq(v4)} ipv4.ignore-auto-dns yes ipv6.dns {shq(v6)} ipv6.ignore-auto-dns yes"
        else:
            mod = "nmcli connection modify \"$CON\" ipv4.dns '' ipv4.ignore-auto-dns no ipv6.dns '' ipv6.ignore-auto-dns no"
        self.win.run(Task(f"DNS: {name}", [("Applying", [
            "ensure_pkg network-manager",
            "CON=$(nmcli -t -f NAME,DEVICE connection show --active | grep -v ':lo$' | head -n1 | cut -d: -f1)",
            '[ -n "$CON" ] || fail "No active NetworkManager connection."',
            mod, 'nmcli connection up "$CON"', "sleep 1; grep nameserver /etc/resolv.conf || true"])]))

    def set_hostname(self):
        name = self.host.get_text().strip().lower()
        if not re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", name):
            self.win.toast("Use letters, digits and hyphens only (max 63).", "err")
            return
        self.win.run(Task("Change hostname", [("hostnamectl", [
            f"hostnamectl set-hostname {name}",
            f"if grep -qE '^127\\.0\\.1\\.1' /etc/hosts; then sed -i -E 's/^127\\.0\\.1\\.1.*/127.0.1.1\\t{name}/' /etc/hosts; "
            f"else printf '127.0.1.1\\t{name}\\n' >> /etc/hosts; fi"])]))

    def mac(self, flag):
        iface = W.dd_value(self.iface)
        if not iface or not re.match(r"^[A-Za-z0-9_.:-]+$", iface):
            return
        self.win.run(Task(f"MAC address {iface}", [("macchanger", [
            "echo 'macchanger macchanger/automatically_run boolean false' | debconf-set-selections",
            "DEBIAN_FRONTEND=noninteractive ensure_pkg macchanger",
            f"ip link set dev {iface} down", f"macchanger {flag} {iface}", f"ip link set dev {iface} up"])]))
