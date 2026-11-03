# Debos - Toolbox shell library.
# Sourced by every generated task script.  Task scripts run as root unless
# they were generated as "user" tasks.  Every helper returns non-zero on
# failure so that the surrounding step (a subshell running with `set -e`)
# is reported as failed.

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export APT_LISTCHANGES_FRONTEND="${APT_LISTCHANGES_FRONTEND:-none}"
DEBOS_FAILED=0
DEBOS_DONE=0
DEBOS_TOTAL=0
DEBOS_FAILED_STEPS=""

_c() { printf '\033[%sm' "$1"; }
info() { printf '%s   %s%s\n' "$(_c '0;36')" "$*" "$(_c 0)"; }
ok()   { printf '%s ✔ %s%s\n' "$(_c '1;32')" "$*" "$(_c 0)"; }
warn() { printf '%s ⚠ %s%s\n' "$(_c '1;33')" "$*" "$(_c 0)" >&2; }
fail() { printf '%s ✖ %s%s\n' "$(_c '1;31')" "$*" "$(_c 0)" >&2; return 1; }

debos_begin() {
    DEBOS_TOTAL="$1"
    printf '%s%s%s\n' "$(_c '1;35')" "${DEBOS_TITLE:-Debos - Toolbox task}" "$(_c 0)"
    printf '%sStarted %s as %s on %s%s\n' "$(_c '0;37')" "$(date '+%Y-%m-%d %H:%M:%S')" "$(id -un)" "$(hostname)" "$(_c 0)"
}

__step() {
    DEBOS_DONE=$((DEBOS_DONE + 1))
    DEBOS_CURRENT="$1"
    printf '\n%s━━ [%s/%s] %s%s\n' "$(_c '1;34')" "$DEBOS_DONE" "$DEBOS_TOTAL" "$1" "$(_c 0)"
}

__done() {
    local rc="$1"
    if [ "$rc" -eq 0 ]; then
        ok "$DEBOS_CURRENT"
    else
        DEBOS_FAILED=$((DEBOS_FAILED + 1))
        DEBOS_FAILED_STEPS="${DEBOS_FAILED_STEPS}  • ${DEBOS_CURRENT} (exit ${rc})"$'\n'
        printf '%s ✖ %s failed (exit code %s)%s\n' "$(_c '1;31')" "$DEBOS_CURRENT" "$rc" "$(_c 0)" >&2
    fi
    return "$rc"
}

# debos_stop: used after a failed step when the remaining steps depend on it
debos_stop() {
    local left=$((DEBOS_TOTAL - DEBOS_DONE))
    [ "$left" -gt 0 ] && printf '\n%s ⚠ Skipping the remaining %s step(s): they depend on the failed one.%s\n' "$(_c '1;33')" "$left" "$(_c 0)" >&2
    debos_end
}

debos_end() {
    echo
    if [ "$DEBOS_FAILED" -gt 0 ]; then
        printf '%s%s of %s step(s) failed:%s\n%s' "$(_c '1;31')" "$DEBOS_FAILED" "$DEBOS_TOTAL" "$(_c 0)" "$DEBOS_FAILED_STEPS"
        printf 'Full log: %s\n' "${DEBOS_LOG:-/var/log/debos-toolbox/tasks.log}"
        exit 1
    fi
    printf '%s✔ All %s step(s) finished successfully.%s\n' "$(_c '1;32')" "$DEBOS_TOTAL" "$(_c 0)"
    exit 0
}

# ----------------------------------------------------------------- packages
is_installed() {
    dpkg-query -W -f='${db:Status-Abbrev}' "$1" 2>/dev/null | grep -q '^ii'
}

pkg_available() {
    local cand
    cand=$(apt-cache policy "$1" 2>/dev/null | awk '/Candidate:/ {print $2; exit}')
    [ -n "$cand" ] && [ "$cand" != "(none)" ]
}

apt_update() {
    local try
    for try in 1 2; do
        if apt-get update; then
            return 0
        fi
        [ "$try" -eq 1 ] && { warn "apt-get update failed, retrying in 3 seconds..."; sleep 3; }
    done
    warn "apt-get update reported errors. Open Repositories > Repository Doctor to fix them."
    return 1
}

apt_install() {
    apt-get install -y "$@"
}

# Install without debconf questions, keeping existing configuration files.
apt_install_quiet() {
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold "$@"
}

ensure_pkg() {
    local p missing=()
    for p in "$@"; do
        is_installed "$p" || missing+=("$p")
    done
    [ ${#missing[@]} -eq 0 ] && return 0
    info "Installing: ${missing[*]}"
    apt-get install -y "${missing[@]}"
}

# Install only the packages that exist in the configured repositories.
apt_install_available() {
    local p ok_list=() skipped=()
    for p in "$@"; do
        if pkg_available "$p"; then ok_list+=("$p"); else skipped+=("$p"); fi
    done
    [ ${#skipped[@]} -gt 0 ] && warn "Not available for this Debian release, skipped: ${skipped[*]}"
    [ ${#ok_list[@]} -eq 0 ] && { warn "Nothing to install."; return 0; }
    apt-get install -y "${ok_list[@]}"
}

need_arch() {
    local a
    for a in "$@"; do
        [ "$ARCH" = "$a" ] && return 0
    done
    fail "Only available for: $* (this system is $ARCH)."
}

# ------------------------------------------------------------- repositories
download() {  # download <url> <dest>
    curl -fL --retry 3 --retry-delay 2 --connect-timeout 20 -o "$2" "$1"
}

# add_key <url> <destination>: store an OpenPGP key for Signed-By.
# Armored keys are kept as .asc, binary keys are dearmored to .gpg.
add_key() {
    local url="$1" dest="$2" tmp
    tmp=$(mktemp)
    if ! download "$url" "$tmp"; then
        rm -f "$tmp"
        fail "Could not download key from $url"
        return 1
    fi
    if ! gpg --show-keys "$tmp" >/dev/null 2>&1; then
        rm -f "$tmp"
        fail "$url is not a valid OpenPGP key"
        return 1
    fi
    install -d -m 0755 "$(dirname "$dest")"
    case "$dest" in
        *.asc) install -m 0644 "$tmp" "$dest" ;;
        *) gpg --dearmor < "$tmp" > "$dest.tmp" 2>/dev/null || cp "$tmp" "$dest.tmp"
           install -m 0644 "$dest.tmp" "$dest"; rm -f "$dest.tmp" ;;
    esac
    rm -f "$tmp"
    info "Key saved: $dest"
}

# write_source <name> : read a deb822 stanza from stdin into sources.list.d/<name>.sources
write_source() {
    local file="/etc/apt/sources.list.d/$1.sources"
    cat > "$file.tmp" && install -m 0644 "$file.tmp" "$file" && rm -f "$file.tmp"
    info "Repository file written: $file"
}

backup_apt_sources() {
    local dest
    dest="/var/backups/debos-toolbox/apt-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$dest"
    cp -a /etc/apt/sources.list /etc/apt/sources.list.d /etc/apt/keyrings /etc/apt/trusted.gpg.d "$dest"/ 2>/dev/null || true
    [ -f /etc/apt/trusted.gpg ] && cp -a /etc/apt/trusted.gpg "$dest"/ 2>/dev/null
    info "APT configuration backed up to $dest"
}

debos_helper() {
    /usr/bin/python3 -I "$DEBOS_HELPER_PATH" "$@"
}

enable_components() {
    if [ $# -eq 0 ]; then
        set -- contrib non-free non-free-firmware
    fi
    debos_helper enable-components "$@"
}

# extrepo_enable <name> [policy]: enable a Debian-curated third-party repository.
extrepo_enable() {
    local name="$1" policy="${2:-main}" conf=/etc/extrepo/config.yaml
    ensure_pkg extrepo || return 1
    if [ "$policy" != main ] && [ -f "$conf" ]; then
        if ! grep -Eq "^[[:space:]]*-[[:space:]]*${policy}[[:space:]]*$" "$conf"; then
            sed -i -E "s/^#[[:space:]]*-[[:space:]]*($policy)[[:space:]]*$/- \1/" "$conf"
            grep -Eq "^[[:space:]]*-[[:space:]]*${policy}[[:space:]]*$" "$conf" || \
                sed -i -E "/^enabled_policies:/a - $policy" "$conf"
            info "extrepo: allowed '$policy' repositories in $conf"
        fi
    fi
    extrepo enable "$name" && info "extrepo: $name enabled"
}

extrepo_has() {
    command -v extrepo >/dev/null 2>&1 || return 1
    extrepo search "^$1\$" 2>/dev/null | grep -q "^Found $1:"
}

# ------------------------------------------------------------------ misc
as_user() {  # run a command as the desktop user
    if [ "$(id -u)" -eq 0 ] && [ -n "${TARGET_USER:-}" ] && [ "$TARGET_USER" != root ]; then
        runuser -u "$TARGET_USER" -- "$@"
    else
        "$@"
    fi
}

running() { pgrep -x "$1" >/dev/null 2>&1; }

secure_boot_enabled() {
    command -v mokutil >/dev/null 2>&1 && mokutil --sb-state 2>/dev/null | grep -qi enabled
}

free_space_gb() {  # free_space_gb <path>
    df -Pk "$1" 2>/dev/null | awk 'NR==2 {printf "%d", $4/1024/1024}'
}
