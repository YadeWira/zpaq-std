#!/bin/bash
# ============================================================================
# suite_tar.sh -- -tar (zpaqfranz 65.4, *nix): symlinks, hard links, FIFOs y
# permisos tienen que volver como eran, con el pool de prefetch activo.
#
# POR QUE EXISTE: al fusionar 65.4, el pool de prefetch de zpaq-std (pre20) abria
# con fopen() todo archivo del add. Con -tar eso guardaba lo APUNTADO por un
# symlink en vez del link, y en un FIFO se quedaba esperando PARA SIEMPRE (el
# add no terminaba nunca). Upstream lo evita en su add(); el pool no lo sabia.
# Con -t1 (sin pool) andaba, por eso hay que probarlo con varios hilos.
#
#   uso: suite_tar.sh          (usa Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
RUN=${RUN:-tar}
OUT=$W/$RUN; rm -rf "$OUT"; mkdir -p "$OUT/tsrc/sub"; cd "$OUT"
python3 -c "
import random; random.seed(7); w='alfa beta gamma delta'.split()
open('tsrc/a.txt','w').write(' '.join(random.choice(w) for _ in range(40000)))"
ln -s a.txt tsrc/enlace; ln -s sub tsrc/enlace_dir; ln tsrc/a.txt tsrc/duro; mkfifo tsrc/fifo
chmod 640 tsrc/a.txt; chmod 750 tsrc/sub; cp tsrc/a.txt tsrc/sub/b.txt
malos=0
for t in "" "-t1" "-t4"; do
  rm -rf t.zpaq o
  timeout 120 "$Z" a t.zpaq tsrc -tar $t </dev/null >/dev/null 2>&1; rc=$?
  if [ $rc = 124 ]; then echo "  add $t: COLGADO (timeout)"; malos=$((malos+1)); continue; fi
  timeout 120 "$Z" x t.zpaq -to o -tar </dev/null >/dev/null 2>&1
  r="ok"
  [ -L o/tsrc/enlace ] && [ "$(readlink o/tsrc/enlace)" = a.txt ] || r="symlink-mal"
  [ -L o/tsrc/enlace_dir ] || r="$r symlink-dir-mal"
  [ -p o/tsrc/fifo ] || r="$r fifo-mal"
  [ "$(stat -c %i o/tsrc/a.txt 2>/dev/null)" = "$(stat -c %i o/tsrc/duro 2>/dev/null)" ] || r="$r hardlink-mal"
  [ "$(stat -c %a o/tsrc/a.txt 2>/dev/null)" = 640 ] && [ "$(stat -c %a o/tsrc/sub 2>/dev/null)" = 750 ] || r="$r permisos-mal"
  cmp -s o/tsrc/a.txt tsrc/a.txt && cmp -s o/tsrc/sub/b.txt tsrc/sub/b.txt || r="$r datos-mal"
  [ "$r" = ok ] || malos=$((malos+1))
  printf '  -tar %-4s %s\n' "${t:-(def)}" "$r"
done
echo "--- 3 casos, $((3-malos)) bien, $malos a revisar ---"
echo DONE_TAR
