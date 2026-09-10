#!/bin/bash
# ============================================================================
# HARNESS DIFERENCIAL — Fase 0 del plan de migración a Rust.
#
# Corre DOS binarios de zpaq-std sobre el mismo corpus y verifica las cuatro
# propiedades que un refactor no puede romper:
#
#   1. bit-exactitud     A y B producen el MISMO archivo byte a byte
#   2. A lee lo de B     A extrae el archivo escrito por B == fuente
#   3. B lee lo de A     B extrae el archivo escrito por A == fuente
#   4. mismo veredicto   'l' y 't' coinciden (rc y salida)
#
# Sin esto, cada fase de la migración es una apuesta. Con esto, es una
# hipótesis verificable.
#
# CLAVE: -timestamp NO alcanza. Se creía que fijaba todo; no es así. Cada bloque
# journaling lleva una cabecera "jDC" + YYYYMMDDHHMMSS tomada del reloj, en 4
# lugares del archivo, y -timestamp no la cubre. Dos corridas que cruzan un
# segundo dan 4 bytes distintos en archivos por lo demás idénticos.
#   => la comparación 1 corría una CARRERA CONTRA EL RELOJ: pasaba con métodos
#      rápidos (ambas corridas en el mismo segundo) y daba divergencias falsas
#      con métodos lentos (bzip2, flzma2 sobre corpus grande).
# Ahora se normalizan esas fechas a ceros con norm_jdc.py antes de comparar.
# Descubierto 2026-09-09 comparando bzip2 en C contra bzip2 en Rust: los dos
# binarios diferían de sí mismos entre corridas, siempre en exactamente 4 bytes.
#
# LEER EL CSV POR COLUMNA, NO EL VEREDICTO. La bit-exactitud es un DIAGNOSTICO,
# no un requisito: con -ma el bloque va como 'store' y el codec se identifica por
# el comentario "zpaqstd-ma:<algo>:<lvl>:<orig>", igual venga de C o de Rust; y el
# dedup hashea los datos ORIGINALES por fragmento, asi que archivos nuevos con
# bytes distintos no degradan nada y un -append puede mezclar bloques de las dos
# implementaciones. La firma de "formato compatible, bytes distintos" es:
#
#   bit_exacto=NO  A_lee_B=SI  B_lee_A=SI  l_igual=SI  t_igual=SI
#
# y en ese caso el veredicto agregado dice DIVERGEN aunque la interoperabilidad
# sea perfecta. Lo que se pierde al aceptar bytes distintos es el ORACULO para
# refactors futuros, no la compatibilidad. Sin esta nota, la primera fase de la
# migracion que cambie un codec se lee como una falla.
#
# COMPLEMENTO OBLIGATORIO: este harness regenera el archivo de A con el binario
# de HOY, asi que no ancla nada a los bytes que existen en produccion. Para eso
# esta golden_gate.sh. Y no compara el stdout de a/x/t (solo el de 'l', filtrado):
# para los mensajes numerados y las formas de destino esta os_msgs.sh.
#
#   uso: difftest.sh <binarioA> <binarioB> [etiqueta]
# ============================================================================
set -u
A="$1"; B="$2"; TAG="${3:-diff}"
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
CORPUS=$W/corpus
OUT=$W/$TAG; rm -rf $OUT; mkdir -p $OUT
CSV=$OUT/difftest.csv; LOG=$OUT/difftest.log
TS=${TS:-2026-01-01_00:00:00}
TMO=${TMO:-900}   # 300 no alcanza: -m5 sobre bigtext (20 MB) tarda ~62 s, y hay casos peores

echo "caso,metodo,archA,archB,bit_exacto,A_lee_B,B_lee_A,l_igual,t_igual,resultado" > "$CSV"
: > "$LOG"
printf 'A = %s\nB = %s\ntimestamp fijo = %s\n\n' "$A" "$B" "$TS" | tee -a "$LOG"

norm(){ grep -viE 'zpaq-std-open|^[0-9.]+s \(|Large page|speed|MB/s|@ ' | sed 's/[0-9]\{1,\}\.[0-9]\{2\}s//g'; }

one(){ # caso metodo
  local c="$1" m="$2"
  local src=$CORPUS/$c
  local d=$OUT/w; rm -rf $d; mkdir -p $d
  local ok=1 note=""

  timeout $TMO "$A" a "$d/A.zpaq" "$src" $m -timestamp $TS -summary >>"$LOG" 2>&1 </dev/null; local rca=$?
  timeout $TMO "$B" a "$d/B.zpaq" "$src" $m -timestamp $TS -summary >>"$LOG" 2>&1 </dev/null; local rcb=$?
  local sa=$(stat -c%s "$d/A.zpaq" 2>/dev/null || echo 0)
  local sb=$(stat -c%s "$d/B.zpaq" 2>/dev/null || echo 0)
  if [ "$rca" != "$rcb" ]; then note="rc_add A=$rca B=$rcb"; ok=0; fi

  # 1) bit-exactitud (con las fechas jDC normalizadas: ver la cabecera)
  local bit=SI
  python3 "$W/norm_jdc.py" "$d/A.zpaq" "$d/A.norm" >/dev/null 2>&1
  python3 "$W/norm_jdc.py" "$d/B.zpaq" "$d/B.norm" >/dev/null 2>&1
  if [ -s "$d/A.norm" ] && [ -s "$d/B.norm" ]; then
    cmp -s "$d/A.norm" "$d/B.norm" || { bit=NO; ok=0; note="${note:+$note; }archivos distintos"; }
  else
    cmp -s "$d/A.zpaq" "$d/B.zpaq" || { bit=NO; ok=0; note="${note:+$note; }archivos distintos (sin normalizar)"; }
  fi

  # 2) A lee lo de B   3) B lee lo de A
  local ab=SI
  timeout $TMO "$A" x "$d/B.zpaq" -to "$d/oAB/" -force -summary >>"$LOG" 2>&1 </dev/null || { ab=EXT_FAIL; ok=0; }
  diff -r "$src" "$d/oAB$src" >>"$LOG" 2>&1 || { ab=NO; ok=0; note="${note:+$note; }A no reprodujo lo de B"; }
  local ba=SI
  timeout $TMO "$B" x "$d/A.zpaq" -to "$d/oBA/" -force -summary >>"$LOG" 2>&1 </dev/null || { ba=EXT_FAIL; ok=0; }
  diff -r "$src" "$d/oBA$src" >>"$LOG" 2>&1 || { ba=NO; ok=0; note="${note:+$note; }B no reprodujo lo de A"; }

  # 4) mismo veredicto
  local li=SI ti=SI
  timeout $TMO "$A" l "$d/A.zpaq" -nomore 2>/dev/null </dev/null | norm > "$d/la.txt"
  timeout $TMO "$B" l "$d/A.zpaq" -nomore 2>/dev/null </dev/null | norm > "$d/lb.txt"
  cmp -s "$d/la.txt" "$d/lb.txt" || { li=NO; ok=0; note="${note:+$note; }listados distintos"; }
  timeout $TMO "$A" t "$d/A.zpaq" >>"$LOG" 2>&1 </dev/null; local ta=$?
  timeout $TMO "$B" t "$d/A.zpaq" >>"$LOG" 2>&1 </dev/null; local tb=$?
  [ "$ta" = "$tb" ] || { ti="A=$ta B=$tb"; ok=0; }

  local res=$([ $ok -eq 1 ] && echo IGUALES || echo DIVERGEN)
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' "$c" "$m" "$sa" "$sb" "$bit" "$ab" "$ba" "$li" "$ti" "$res" >> "$CSV"
  printf '  %-8s %-16s A=%-9s B=%-9s bit=%-3s A<-B=%-3s B<-A=%-3s l=%-3s t=%-8s %s%s\n' \
    "$c" "$m" "$sa" "$sb" "$bit" "$ab" "$ba" "$li" "$ti" "$res" "${note:+  [$note]}"
  rm -rf $d
}

CASES="${CASES:-text bin img mixed intl edge precomp}"
METHODS="${METHODS:--m1 -m2 -m3 -m5 -ma:zstd -ma:flzma2 -ma:ppmd -ma:bsc -ma:brotli -ma:lz4 -ma:bzip2 -ma:snappy -ma:lzfse -store}"
for c in $CASES; do for m in $METHODS; do one "$c" "$m"; done; done

tot=$(($(wc -l < "$CSV")-1))
div=$(grep -c DIVERGEN "$CSV" || true)
echo
printf '=== %s comparaciones, %s divergencias ===\n' "$tot" "$div"
[ "$div" != "0" ] && grep DIVERGEN "$CSV" | head -20
echo DONE_DIFF
