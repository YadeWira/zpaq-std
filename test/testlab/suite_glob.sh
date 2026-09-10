#!/bin/bash
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
OUT=$W/${RUN:-run1}; mkdir -p $OUT
CSV=$OUT/glob.csv; echo "prueba,esperado,obtenido,resultado" > "$CSV"
ok(){ printf '  %-30s esperado=%-6s obtenido=%-6s %s\n' "$1" "$2" "$3" "$4"; echo "$1,$2,$3,$4" >> "$CSV"; }
d=$OUT/gl; rm -rf $d; mkdir -p $d/data/sub; mkdir -p $d/work
for i in 1 2 3 4 5; do printf 'c%s\n' $i > $d/data/f$i.c; done
for i in 1 2 3; do printf 'h%s\n' $i > $d/data/f$i.h; done
printf 'x\n' > $d/data/sub/anidado.c
# los esperados se calculan del arbol real: "*" tambien matchea sub/ y recursa
E_C=$(ls $d/data/*.c | wc -l)
E_H=$(ls $d/data/*.h | wc -l)
E_ALL=$(find $d/data -type f | wc -l)
E_DIR=$E_ALL
cd $d/data
n(){ echo "${1:-0}" | grep -oE '[0-9]+' | head -1; }
# sum: cuenta archivos
for pat in "*.c:$E_C" "*.h:$E_H" "*:$E_ALL" "f?.c:$E_C" 'f1.*:2' '*.noexiste:0'; do
  p=${pat%%:*}; exp=${pat##*:}
  got=$(n "$($Z sum "$p" 2>&1 </dev/null | grep -oE '[0-9]+ +files' | head -1)")
  ok "sum \"$p\"" "$exp" "${got:-0}" "$([ "${got:-0}" = "$exp" ] && echo OK || echo FALLA)"
done
# add: cuenta archivos agregados
for pat in "*.c:$E_C" "*:$E_ALL"; do
  p=${pat%%:*}; exp=${pat##*:}; rm -f $d/work/a.zpaq
  got=$(n "$($Z a $d/work/a.zpaq "$p" -m1 -summary 2>&1 </dev/null | grep -oE 'Files added \+[0-9]+' | head -1)")
  ok "a \"$p\"" "$exp" "${got:-0}" "$([ "${got:-0}" = "$exp" ] && echo OK || echo FALLA)"
done
# cp
$Z cp "$d/data/*.c" -to "$d/work/dst" >/dev/null 2>&1 </dev/null
got=$(ls $d/work/dst 2>/dev/null | wc -l); ok 'cp "*.c" -to dst' "$E_C" "$got" "$([ "$got" = "$E_C" ] && echo OK || echo FALLA)"
# que lo que ya andaba siga andando
got=$(n "$($Z sum "$d/data" 2>&1 </dev/null | grep -oE '[0-9]+ +files'|head -1)")
ok "sum <directorio>" "$E_DIR" "${got:-0}" "$([ "${got:-0}" = "$E_DIR" ] && echo OK || echo FALLA)"
got=$(n "$($Z sum "$d/data/f1.c" 2>&1 </dev/null | grep -oE '[0-9]+ +files'|head -1)")
ok "sum <archivo puntual>" 1 "${got:-0}" "$([ "${got:-0}" = "1" ] && echo OK || echo FALLA)"
cd /; rm -rf $d
echo DONE_GLOB
