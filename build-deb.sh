#!/bin/bash
# Build debos-toolbox_<version>_all.deb from the debos-toolbox/ package tree.
# The version comes from the VERSION file and must match APP_VERSION in the script.
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(tr -d '[:space:]' < VERSION)
SCRIPT=debos-toolbox/usr/bin/debos-toolbox
grep -q "^APP_VERSION = \"$VERSION\"" "$SCRIPT" || { echo "APP_VERSION in $SCRIPT does not match VERSION ($VERSION)" >&2; exit 1; }
python3 -m py_compile "$SCRIPT" && rm -rf debos-toolbox/usr/bin/__pycache__

BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
cp -a debos-toolbox/. "$BUILD/"
find "$BUILD" -type d -exec chmod 0755 {} +
find "$BUILD" -type f -exec chmod 0644 {} +
chmod 0755 "$BUILD/usr/bin/debos-toolbox"
gzip -9n "$BUILD/usr/share/doc/debos-toolbox/changelog"

sed -i "s/^Version:.*/Version: $VERSION/" "$BUILD/DEBIAN/control"
SIZE=$(du -sk --exclude=DEBIAN "$BUILD" | cut -f1)
sed -i "/^Installed-Size:/d; /^Architecture:/a Installed-Size: $SIZE" "$BUILD/DEBIAN/control"

OUT="debos-toolbox_${VERSION}_all.deb"
rm -f debos-toolbox_*_all.deb
dpkg-deb --root-owner-group -Zxz --build "$BUILD" "$OUT"
echo "Built $OUT"
