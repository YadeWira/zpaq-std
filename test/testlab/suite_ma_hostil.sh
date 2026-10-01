#!/bin/bash
# ============================================================================
# suite_ma_hostil.sh -- bloques -ma que LZ NO puede comprimir, en bloques enteros.
#
# Hasta pre45, -ma:lz5 (nivel 9 en adelante, 9 es su default) y -ma:lz6 (10+)
# escribian hasta 732 KB despues de su buffer de salida con 16 MB de base64 de
# bytes aleatorios: los parsers HC de LZ5/lz6 no respetan LZ6_compressBound y
# zpaq-std les pasaba justo el bound (con el que no controlan la salida). 'a'
# abortaba (free(): invalid size / double free). Las suites de siempre usan
# entradas chicas o comprimibles y no lo veian. Arreglo: el tope es el original.
#
# Uso: Z=<binario> bash suite_ma_hostil.sh     (con un build ASan detecta tambien
# los desbordes que no llegan a abortar)
# ============================================================================
export TMPDIR=${TMPDIR:-/mnt/IA_LAB/agentes/ZPAQ-STD/int/tmpdir}
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=${RUN:-$TMPDIR/ma_hostil}; rm -rf $W; mkdir -p $W/in; cd $W
# base64 de bytes pseudoaleatorios con semilla fija: siempre la misma entrada
openssl enc -aes-128-ctr -pass pass:zpaq-std-hostil -nosalt -pbkdf2 < /dev/zero 2>/dev/null | head -c 12582912 | base64 -w 76 > in/b64.txt
malos=0; n=0
for s in lz5 lz5:9 lz5:15 lz5hc:12 lz5hc:15 lz5f:1 lz6:0 lz6:2 lz6:10 lz6:12 lz6:15 lizard:19 lizard:49 lz4:12 lzav:1 snappy:1 kanzi:1 kanzi:2 kanzi:5 kanzi:6; do
  n=$((n+1)); rm -rf a.zpaq x
  timeout 900 $Z a a.zpaq in -ma:$s </dev/null >a.log 2>&1; ra=$?
  timeout 900 $Z x a.zpaq -to x </dev/null >x.log 2>&1; rx=$?
  d=$(find x -type d -name in 2>/dev/null | head -1)
  if [ $ra -ne 0 ] || [ $rx -ne 0 ] || grep -q AddressSanitizer a.log x.log || ! diff -r "$d" in >/dev/null 2>&1; then
    malos=$((malos+1)); echo "FALLA -ma:$s a=$ra x=$rx"; else echo "ok    -ma:$s"; fi
done
echo "== suite_ma_hostil: $n casos, $malos falla(s)"
