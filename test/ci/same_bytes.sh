#!/bin/bash
# CI: every platform must write the same archive as the first one, method by method,
# except the differences listed in test/ci/known_differences.txt ("<platform> <method>":
# both archives are valid and every platform reads both; only the bytes differ).
#   test/ci/same_bytes.sh <reference platform> <platform>...
set -u
REF=$1; shift
K=test/ci/known_differences.txt
bad=0
[ -s "hashes-$REF.txt" ] || { echo "no hashes for $REF"; exit 1; }
for p in "$@"; do
  [ "$p" = "$REF" ] && continue
  [ -s "hashes-$p.txt" ] || { echo "$p: no hashes"; bad=$((bad+1)); continue; }
  same=0; known=0
  while read -r m h; do
    o=$(awk -v m="$m" '$1==m {print $2}' "hashes-$p.txt")
    if [ -z "$o" ]; then echo "$p $m: missing"; bad=$((bad+1))
    elif [ "$o" = "$h" ]; then same=$((same+1))
    elif grep -qxF "$p $m" "$K" 2>/dev/null; then known=$((known+1)); echo "$p $m: differs (known)"
    else echo "$p $m: DIFFERS from $REF"; bad=$((bad+1)); fi
  done < "hashes-$REF.txt"
  echo "$p: $same identical to $REF, $known known differences"
done
[ $bad = 0 ]
