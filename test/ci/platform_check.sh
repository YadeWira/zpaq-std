#!/bin/bash
# CI: every built-in method (-m1..-m5, -m8 the default, and each -ma switch that is not plugin-only)
# compresses a fixed tree and extracts it back identical. The archives' SHA-256 go to
# hashes-<platform>.txt, so a later job can check that every platform writes the same
# bytes.
#   test/ci/platform_check.sh <zpaq-std binary> <platform name>
set -u
Z=$1; PLAT=$2
W=ci-work; rm -rf "$W"; mkdir -p "$W/data/sub"
# a fixed tree from the repository itself: text, C, a binary-ish file and an empty one
cp README.md CHANGELOG.md LICENSE "$W/data/"
cp compressors/zpaqsylz3/gen.py compressors/bsc/PATCHES "$W/data/sub/"
head -c 300000 THIRD-PARTY-LICENSES.txt > "$W/data/sub/tpl.txt"
: > "$W/data/sub/empty"
# fixed dates, and no attributes (-noattributes below): Unix modes and Windows
# attributes differ by nature, and the archive must be the same everywhere
fixdates() { find data -exec touch -d '2026-01-01T12:00:00Z' {} +; }   # GNU and BSD touch
# Windows archives also store each file's and folder's creation date: set it here, on
# data/ itself too (it was created by this run)
case $(uname -s) in MINGW*|MSYS*|CYGWIN*)
  (cd "$W" && powershell -NoProfile -Command "@(Get-Item data) + @(Get-ChildItem -Recurse data) | ForEach-Object { \$_.CreationTimeUtc = [datetime]'2026-01-01T12:00:00' }") ;;
esac
cd "$W" || exit 1
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -c1-64; }
"$Z" 2>&1 | grep -m1 "zpaq-std v" || { echo "the binary does not run"; exit 1; }
methods="-m1 -m2 -m3 -m4 -m5 -m8"
for c in $("$Z" codecinfo 2>/dev/null | tr -d '\r' | awk '/^[a-z0-9]+ +(stable|experimental) /{print $1}'); do
  case $c in sylz|sylzec) ;; *) methods="$methods -ma:$c";; esac
done
n=0; bad=0; : > "../hashes-$PLAT.txt"
for m in $methods; do
  n=$((n+1)); f=a$n.zpaq
  fixdates
# -nofast: no VFILE-info record (zpaqfranz 65.x), which names the OS: the bytes compared are the data
  if ! "$Z" a $f data $m -timestamp 2026-01-01_00:00:00 -nofast -noattributes -nomore >a.log 2>&1; then echo "FAIL a $m"; tail -3 a.log; bad=$((bad+1)); continue; fi
  rm -rf x; "$Z" x $f -to x -nomore >x.log 2>&1
  if ! diff -r data x/data >/dev/null 2>&1; then echo "FAIL x $m"; tail -3 x.log; bad=$((bad+1)); fi
  "$Z" t $f -nomore >/dev/null 2>&1 || { echo "FAIL t $m"; bad=$((bad+1)); }
  echo "$m $(sha256 $f)" >> "../hashes-$PLAT.txt"
done
echo "$PLAT: $n methods, $bad failures"
[ $bad = 0 ]
