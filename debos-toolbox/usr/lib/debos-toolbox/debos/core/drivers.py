"""Hardware detection through sysfs and driver/firmware recommendations for Debian."""

import glob
import os
import shlex

from .util import read_file, run, which

VENDORS = {
    "10de": "NVIDIA", "1002": "AMD", "1022": "AMD", "8086": "Intel", "14e4": "Broadcom", "10ec": "Realtek",
    "168c": "Qualcomm Atheros", "17cb": "Qualcomm", "14c3": "MediaTek", "1b4b": "Marvell", "1814": "Ralink",
    "15b3": "Mellanox", "80ee": "VirtualBox", "15ad": "VMware", "1af4": "Virtio", "1234": "QEMU", "1414": "Microsoft",
    "1b21": "ASMedia", "1179": "Toshiba", "144d": "Samsung", "1c5c": "SK hynix", "c0a9": "Micron", "1e0f": "KIOXIA",
}


def _cat(cls):
    base, sub = cls >> 16, (cls >> 8) & 0xFF
    if base == 0x03:
        return "gpu"
    if base == 0x02:
        return "wifi" if sub == 0x80 else "ethernet"
    if base == 0x04:
        return "audio"
    if base == 0x0D:
        return "wireless"
    if base == 0x01:
        return "storage"
    if base == 0x0C and sub == 0x03:
        return "usb"
    return "other"


def _lspci_names():
    code, text = run(["lspci", "-mm", "-nn"], timeout=10)
    names = {}
    for line in text.splitlines():
        try:
            parts = shlex.split(line)
        except ValueError:
            continue
        if len(parts) >= 4:
            strip = lambda s: s.rsplit(" [", 1)[0] if s.endswith("]") else s
            names[parts[0]] = (strip(parts[1]), strip(parts[2]), strip(parts[3]))
    return names


def pci_devices(root="/sys/bus/pci/devices"):
    names = _lspci_names()
    devices = []
    for path in sorted(glob.glob(os.path.join(root, "*"))):
        slot = os.path.basename(path)
        try:
            cls = int(read_file(os.path.join(path, "class"), "0x0").strip(), 16)
        except ValueError:
            continue
        vendor = read_file(os.path.join(path, "vendor")).strip().replace("0x", "")
        device = read_file(os.path.join(path, "device")).strip().replace("0x", "")
        drv = os.path.join(path, "driver")
        driver = os.path.basename(os.path.realpath(drv)) if os.path.exists(drv) else ""
        short = slot[5:] if slot.count(":") == 2 else slot
        cname, vname, dname = names.get(short, ("", VENDORS.get(vendor, vendor), device))
        devices.append({"slot": short, "class": cls, "category": _cat(cls), "vendor_id": vendor, "device_id": device,
                        "vendor": VENDORS.get(vendor, vname or vendor), "name": dname or f"{vendor}:{device}",
                        "class_name": cname, "driver": driver})
    return devices


def bluetooth_present():
    if glob.glob("/sys/class/bluetooth/hci*"):
        return True
    for path in glob.glob("/sys/bus/usb/devices/*/bInterfaceClass"):
        if read_file(path).strip().lower() == "e0":
            return True
    return False


def usb_printer_present():
    return any(read_file(p).strip() == "07" for p in glob.glob("/sys/bus/usb/devices/*/bInterfaceClass"))


def isenkram_suggestions():
    if not which("isenkram-lookup"):
        return None
    code, text = run(["isenkram-lookup"], timeout=60)
    return sorted({l.strip() for l in text.splitlines() if l.strip() and " " not in l.strip()}) if code == 0 else []


def scan(installed, cpu_vendor="", virt="", secure_boot="disabled"):
    """Return {'devices': [...], 'recs': [...]} where each rec is
    {id, title, detail, packages, script, status, category, device}."""
    devices = pci_devices()
    recs = []

    def add(rid, title, detail, packages=(), script=None, category="system", device=None, needs_nonfree=True,
            satisfied=None):
        pk = list(packages)
        if satisfied is None:
            satisfied = bool(pk) and all(p in installed for p in pk if not p.startswith("linux-headers"))
        recs.append({"id": rid, "title": title, "detail": detail, "packages": pk, "script": script,
                     "status": "installed" if satisfied else "recommended", "category": category,
                     "device": device, "nonfree": needs_nonfree})

    gpus = [d for d in devices if d["category"] == "gpu"]
    for d in gpus:
        name = f"{d['vendor']} {d['name']}"
        if d["vendor_id"] == "10de":
            if d["driver"] == "nvidia":
                add("nvidia", "NVIDIA proprietary driver", f"In use for {name}.", ["nvidia-driver"], category="gpu",
                    device=d, satisfied=True)
            else:
                script = [
                    "ensure_pkg nvidia-detect || true",
                    "PKG=$(nvidia-detect 2>/dev/null | grep -oE 'nvidia-(tesla-[0-9]+-)?driver' | head -n1)",
                    "PKG=${PKG:-nvidia-driver}",
                    'info "Installing $PKG (recommended by nvidia-detect)"',
                    'apt_install "linux-headers-$(uname -r)" || apt_install "linux-headers-$ARCH"',
                    'apt_install "$PKG" firmware-misc-nonfree',
                    "if secure_boot_enabled && [ -f /var/lib/dkms/mok.pub ]; then",
                    "  warn 'Secure Boot is on: enroll the DKMS signing key, then choose \"Enroll MOK\" at the next boot.'",
                    "  mokutil --import /var/lib/dkms/mok.pub || true",
                    "fi",
                    "ok 'Reboot to start the NVIDIA driver.'",
                ]
                detail = f"{name} uses {'the open-source Nouveau driver' if d['driver'] == 'nouveau' else 'no driver'}. " \
                         "The proprietary driver gives full 3D performance, CUDA and NVENC."
                if secure_boot == "enabled":
                    detail += " Secure Boot is on: you will be asked to enroll a signing key (MOK)."
                add("nvidia", "NVIDIA proprietary driver", detail, ["nvidia-driver"], script=script, category="gpu", device=d)
        elif d["vendor_id"] in ("1002", "1022"):
            add("amd-gpu", "AMD graphics firmware and Vulkan", f"{name} ({d['driver'] or 'no driver'}): firmware, RADV Vulkan and VA-API video decoding.",
                ["firmware-amd-graphics", "mesa-vulkan-drivers", "mesa-va-drivers", "libgl1-mesa-dri"], category="gpu", device=d)
        elif d["vendor_id"] == "8086":
            script = ["if pkg_available firmware-intel-graphics; then apt_install firmware-intel-graphics; else apt_install firmware-misc-nonfree; fi",
                      "apt_install_available intel-media-va-driver-non-free mesa-vulkan-drivers libgl1-mesa-dri"]
            add("intel-gpu", "Intel graphics media driver and Vulkan", f"{name}: hardware video decoding (VA-API), ANV Vulkan and GPU firmware.",
                ["intel-media-va-driver-non-free", "mesa-vulkan-drivers"], script=script, category="gpu", device=d)

    for d in devices:
        cat, vid, name = d["category"], d["vendor_id"], f"{d['vendor']} {d['name']}"
        if cat == "wifi" or (cat == "wireless"):
            if vid == "8086":
                add("fw-iwlwifi", "Intel Wi-Fi firmware", f"{name}", ["firmware-iwlwifi"], category="network", device=d)
            elif vid == "10ec":
                add("fw-realtek", "Realtek Wi-Fi firmware", f"{name}", ["firmware-realtek"], category="network", device=d)
            elif vid == "14e4":
                if d["driver"] in ("brcmfmac", "brcmsmac", "b43", "bcma"):
                    add("fw-broadcom", "Broadcom Wi-Fi firmware", f"{name} ({d['driver']})", ["firmware-brcm80211"],
                        category="network", device=d)
                else:
                    add("broadcom-sta", "Broadcom STA (wl) driver", f"{name} has no working driver; broadcom-sta builds the 'wl' module.",
                        ["broadcom-sta-dkms"], script=['apt_install "linux-headers-$(uname -r)" broadcom-sta-dkms',
                                                       "modprobe -r b44 b43 b43legacy ssb brcmsmac bcma 2>/dev/null || true",
                                                       "modprobe wl || true"], category="network", device=d)
            elif vid in ("168c", "17cb"):
                add("fw-atheros", "Qualcomm Atheros Wi-Fi firmware", name, ["firmware-atheros"], category="network", device=d)
            elif vid == "14c3":
                add("fw-mediatek", "MediaTek Wi-Fi firmware", name, ["firmware-mediatek"],
                    script=["if pkg_available firmware-mediatek; then apt_install firmware-mediatek; else apt_install firmware-misc-nonfree; fi"],
                    category="network", device=d)
        elif cat == "ethernet" and vid == "10ec" and d["driver"] == "r8169":
            add("fw-realtek-nic", "Realtek network firmware", f"{name}: firmware for the r8169 driver.", ["firmware-realtek"],
                category="network", device=d)
        elif cat == "audio" and vid == "8086" and (d["driver"].startswith("sof") or not d["driver"]):
            add("fw-sof", "Intel Sound Open Firmware", f"{name}: modern Intel laptops need SOF firmware for speakers and microphones.",
                ["firmware-sof-signed"], category="audio", device=d)

    if cpu_vendor == "intel":
        add("microcode", "Intel CPU microcode", "Security and stability fixes for your processor, loaded at boot.", ["intel-microcode"], category="cpu")
    elif cpu_vendor == "amd":
        add("microcode", "AMD CPU microcode", "Security and stability fixes for your processor, loaded at boot.", ["amd64-microcode"], category="cpu")

    if bluetooth_present():
        add("bluetooth", "Bluetooth support", "Bluetooth hardware was found.", ["bluez", "bluez-firmware"], category="bluetooth",
            needs_nonfree=False)
    if usb_printer_present():
        add("printing", "Printer support", "A USB printer is connected: CUPS and printer drivers.", ["cups", "printer-driver-all", "system-config-printer"],
            category="printer", needs_nonfree=False)
    if virt in ("kvm", "qemu"):
        add("guest-qemu", "QEMU/KVM guest tools", "Better graphics, clipboard sharing and shutdown handling inside the VM.",
            ["qemu-guest-agent", "spice-vdagent"], category="vm", needs_nonfree=False)
    elif virt == "vmware":
        add("guest-vmware", "VMware guest tools", "open-vm-tools for clipboard, resizing and shared folders.", ["open-vm-tools-desktop"],
            category="vm", needs_nonfree=False)
    elif virt == "microsoft":
        add("guest-hyperv", "Hyper-V guest services", "hyperv-daemons for Hyper-V integration.", ["hyperv-daemons"], category="vm",
            needs_nonfree=False)

    missing = [d for d in devices if not d["driver"] and d["category"] in ("gpu", "wifi", "ethernet", "audio", "wireless")]
    for d in missing:
        if not any(r["device"] is d for r in recs):
            add(f"nodriver-{d['slot']}", f"No driver for {d['vendor']} {d['name']}",
                "Install isenkram to look up the right package in the Debian hardware database.", ["isenkram-cli"],
                script=["apt_install isenkram-cli", "isenkram-autoinstall-firmware || true", "isenkram-lookup || true"],
                category="other", device=d, needs_nonfree=True, satisfied=False)
    return {"devices": devices, "recs": recs}
