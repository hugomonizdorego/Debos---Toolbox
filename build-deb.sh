#!/bin/bash
# Build debos-toolbox_<version>_all.deb from the debos-toolbox/ package tree.
# The version comes from VERSION and must match VERSION in debos/__init__.py.
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(tr -d '[:space:]' < VERSION)
PKG=debos-toolbox/usr/lib/debos-toolbox
grep -q "^VERSION = \"$VERSION\"" "$PKG/debos/__init__.py" || { echo "VERSION ($VERSION) does not match $PKG/debos/__init__.py" >&2; exit 1; }
grep -q "^Version: $VERSION$" debos-toolbox/DEBIAN/control || sed -i "s/^Version:.*/Version: $VERSION/" debos-toolbox/DEBIAN/control

# syntax check for every Python file and shell script
python3 - "$PKG" <<'PY'
import ast, pathlib, sys
root = pathlib.Path(sys.argv[1])
for p in list(root.rglob("*.py")) + [root / "debos-helper", pathlib.Path("debos-toolbox/usr/bin/debos-toolbox")]:
    ast.parse(p.read_text(), str(p))
print("python syntax ok")
PY
for s in "$PKG/lib.sh" "$PKG/debos-launch" "$PKG/debos-root"; do bash -n "$s"; done

BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
cp -a debos-toolbox/. "$BUILD/"
find "$BUILD" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$BUILD" -type d -exec chmod 0755 {} +
find "$BUILD" -type f -exec chmod 0644 {} +
chmod 0755 "$BUILD/usr/bin/debos-toolbox" "$BUILD/usr/lib/debos-toolbox/debos-launch" \
           "$BUILD/usr/lib/debos-toolbox/debos-root" "$BUILD/usr/lib/debos-toolbox/debos-helper"
gzip -9n "$BUILD/usr/share/doc/debos-toolbox/changelog"
gzip -9n "$BUILD/usr/share/man/man1/debos-toolbox.1"

SIZE=$(du -sk --exclude=DEBIAN "$BUILD" | cut -f1)
sed -i "/^Installed-Size:/d; /^Architecture:/a Installed-Size: $SIZE" "$BUILD/DEBIAN/control"

OUT="debos-toolbox_${VERSION}_all.deb"
rm -f debos-toolbox_*_all.deb
dpkg-deb --root-owner-group -Zxz --build "$BUILD" "$OUT"
echo "Built $OUT"
