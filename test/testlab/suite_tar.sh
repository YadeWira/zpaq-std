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
# Segunda parte, BUG-021 (heredado de 65.4m, igual en 65.11): un grupo de hard
# links se decidia dentro de cada add y los nombres sin cambios no se volvian a
# escribir. Un link nuevo, o borrar el primer nombre, y x -tar -until N daba
# copias sueltas. Cada version se compara con manifest.py (tipo, modo, tamano,
# mtime, sha1 y grupo de hard link de cada entrada).
#
#   uso: suite_tar.sh          (usa Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
RUN=${RUN:-tar}
M=$(cd "$(dirname "$0")" && pwd)/manifest.py
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
# --- BUG-021: grupos de hard links entre versiones ---
rm -rf h; mkdir -p h/d/s; cd h
echo "shared content" > d/s/000; for i in $(seq 1 200); do ln d/s/000 d/s/$(printf %03d $i); done
echo solo > d/solo
paso() { timeout 120 "$Z" a h.zpaq d -tar </dev/null >/dev/null 2>&1; cp -a d v$1; sleep 1.1; }
paso 1
ln d/s/000 d/nuevo; ln d/solo d/solo2; paso 2          # links nuevos en un grupo
rm d/s/000; paso 3                                      # se borra el primer nombre
rm d/solo; paso 4                                       # un grupo queda con un nombre
for v in 1 2 3 4; do
  rm -rf x; timeout 120 "$Z" x h.zpaq -to x -tar -until $v </dev/null >/dev/null 2>&1
  a=$(python3 "$M" v$v); b=$(python3 "$M" x/d 2>/dev/null)
  if [ -n "$a" ] && [ "$a" = "$b" ]; then r=ok; else r="DISTINTO"; malos=$((malos+1)); fi
  printf '  hardlinks -until %s %s\n' $v "$r"
done
cd ..
echo "--- 7 casos, $((7-malos)) bien, $malos a revisar ---"
echo DONE_TAR
