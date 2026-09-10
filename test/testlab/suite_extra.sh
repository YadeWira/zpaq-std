#!/bin/bash
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
CORPUS=$W/corpus
OUT=$W/${RUN:-run1}; mkdir -p $OUT
CSV=$OUT/extra.csv; LOG=$OUT/extra.log
echo "suite,prueba,detalle,rc,resultado" > "$CSV"
: > "$LOG"
ok(){ printf '%-4s %-30s %-34s rc=%-4s %s\n' "$1" "$2" "$3" "$4" "$5"; echo "$1,$2,$3,$4,$5" >> "$CSV"; }
T(){ timeout 300 "$@" >>"$LOG" 2>&1 </dev/null; }

########## G: multiparte con -chunk (el caso CLAAS nunca estuvo en la matriz) ##########
echo "### G: archivos multiparte (-chunk)"
for chunk in 1000000 5000000 20000000; do
  for m in "-m1" "-m3" "-ma:zstd"; do
    d=$OUT/g_$chunk; rm -rf $d; mkdir -p $d
    T $Z a "$d/p??.zpaq" "$CORPUS/text" "$CORPUS/img" $m -chunk $chunk -summary
    rca=$?
    parts=$(ls $d/p*.zpaq 2>/dev/null | wc -l)
    T $Z l "$d/p??.zpaq"; rcl=$?
    T $Z t "$d/p??.zpaq"; rct=$?
    T $Z x "$d/p??.zpaq" -to "$d/out/" -force -summary; rcx=$?
    res=MATCH
    diff -r "$CORPUS/text" "$d/out$CORPUS/text" >>"$LOG" 2>&1 || res=MISMATCH
    diff -r "$CORPUS/img"  "$d/out$CORPUS/img"  >>"$LOG" 2>&1 || res=MISMATCH
    ok G "chunk=$chunk $m" "partes=$parts l=$rcl t=$rct x=$rcx" "$rca" "$res"
    rm -rf $d
  done
done

########## H: versionado, dedup incremental, -until ##########
echo "### H: versionado / dedup / -until"
d=$OUT/h; rm -rf $d; mkdir -p $d/src
cp -r $CORPUS/text/. $d/src/
T $Z a "$d/v.zpaq" "$d/src" -m3 -summary; s1=$(stat -c%s $d/v.zpaq)
cp -r $d/src $d/snap1
T $Z a "$d/v.zpaq" "$d/src" -m3 -summary; s2=$(stat -c%s $d/v.zpaq)
ok H "v2 con contenido identico" "delta=$((s2-s1)) bytes (0 = dedup perfecto)" 0 "$([ $((s2-s1)) -eq 0 ] && echo DEDUP-OK || echo DEDUP-DELTA)"
echo "// cambio v3" >> "$d/src/$(ls $d/src|head -1)"
T $Z a "$d/v.zpaq" "$d/src" -m3 -summary; s3=$(stat -c%s $d/v.zpaq)
rm -f "$d/src/$(ls $d/src|tail -2|head -1)"
T $Z a "$d/v.zpaq" "$d/src" -m3 -summary; s4=$(stat -c%s $d/v.zpaq)
ok H "v3 (1 archivo modificado)" "delta=$((s3-s2))" 0 OK
ok H "v4 (1 archivo borrado)"    "delta=$((s4-s3))" 0 OK
T $Z x "$d/v.zpaq" -to "$d/o1/" -until 1 -force -summary; r=$?
res=MATCH; diff -r $d/snap1 "$d/o1$d/src" >>"$LOG" 2>&1 || res=MISMATCH
ok H "rollback -until 1" "restaura la version 1" "$r" "$res"
T $Z x "$d/v.zpaq" -to "$d/o4/" -force -summary; r=$?
res=MATCH; diff -r $d/src "$d/o4$d/src" >>"$LOG" 2>&1 || res=MISMATCH
ok H "extraer HEAD (v4)" "estado final" "$r" "$res"
nv=$(timeout 60 $Z l "$d/v.zpaq" 2>/dev/null </dev/null | grep -oE '[0-9]+ versions' | head -1)
ok H "conteo de versiones" "$nv" 0 "$([ "${nv%% *}" = "4" ] && echo OK || echo REVISAR)"
rm -rf $d
echo DONE_EXTRA
