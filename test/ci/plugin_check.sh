#!/bin/bash
# CI: the Free Pascal plugins (sylz with sylzec, and pja), built with make fpc-plugins,
# load in the full program, and sylz and sylzec compress and extract a fixed tree at
# several levels. The archives' SHA-256 go to plughashes-<platform>.txt, for
# same_bytes.sh. pja: its five codecs must be listed by codecinfo.
#   test/ci/plugin_check.sh <zpaq-std binary> <codecs dir> <platform name>
set -u
Z=$1; C=$2; PLAT=$3
W=ci-plug; rm -rf "$W"; mkdir -p "$W/codecs" "$W/data/sub"
cp "$Z" "$W/zpaq-std"; cp "$C"/sylz.* "$C"/pja.* "$W/codecs/"
cp README.md CHANGELOG.md LICENSE "$W/data/"; cp compressors/bsc/PATCHES "$W/data/sub/"
head -c 300000 THIRD-PARTY-LICENSES.txt > "$W/data/sub/tpl.txt"
find "$W/data" -exec touch -d '2026-01-01T12:00:00Z' {} +
cd "$W" || exit 1
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -c1-64; }
bad=0; n=0; : > "../plughashes-$PLAT.txt"
info=$(./zpaq-std codecinfo 2>&1 | tr -d '\r')
for c in sylz sylzec; do
  echo "$info" | grep -E "^$c " | grep -v MISSING | grep -q "codecs/sylz" || { echo "FAIL $c not loaded from codecs/"; bad=$((bad+1)); }
done
for c in pja pjax pjall pjals pjalsx; do
  echo "$info" | grep -qE "^ +pja:$c +pja stream" || { echo "FAIL pja:$c not loaded"; bad=$((bad+1)); }
done
for m in sylz:0 sylz:1 sylz:5 sylz:10 sylzec:0 sylzec:1 sylzec:9; do
  n=$((n+1)); f=p$n.zpaq
  if ! ./zpaq-std a $f data -ma:$m -timestamp 2026-01-01_00:00:00 -noattributes -nomore >a.log 2>&1; then echo "FAIL a $m"; tail -3 a.log; bad=$((bad+1)); continue; fi
  rm -rf x; ./zpaq-std x $f -to x -nomore >/dev/null 2>&1
  diff -r data x/data >/dev/null 2>&1 || { echo "FAIL x $m"; bad=$((bad+1)); }
  echo "-ma:$m $(sha256 $f)" >> "../plughashes-$PLAT.txt"
done
echo "$PLAT plugins: $n methods, $bad failures"
[ $bad = 0 ]
