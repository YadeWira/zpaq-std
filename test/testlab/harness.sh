#!/bin/bash
# zpaq-std — matriz extendida. add -> t -> x -> diff byte-exacto.
# Leccion de la sesion anterior: los flags de 'a' NO se pasan a 't'/'x'
# (p.ej. -test en extraccion es verificacion en seco => falso MISMATCH).
# Solo -key viaja a los comandos de lectura.
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
CORPUS=$W/corpus
RUN=${RUN:-run1}
OUT=$W/$RUN; mkdir -p $OUT
# CSV/LOG por SUITE: antes todas las suites compartian results.csv y la
# segunda truncaba los resultados de la primera al hacer source de este archivo.
CSV=$OUT/results_${SUITE:-x}.csv
LOG=$OUT/detail_${SUITE:-x}.log
TMO=${TMO:-300}

[ -s "$CSV" ] || echo "suite,case,method,orig,arch,ratio,add_s,ext_s,test,verify,nota" > "$CSV"
: > "$LOG"

# extrae solo los flags que 't'/'x' entienden (credenciales)
readflags() {
  local out=""
  set -- $1
  while [ $# -gt 0 ]; do
    case "$1" in
      -key) out="$out -key $2"; shift ;;
      -key*) out="$out $1" ;;
    esac
    shift
  done
  echo "$out"
}

run() { # suite case_dir add_flags label [nota]
  local suite="$1" cdir="$2" af="$3" label="$4" nota="${5:-}"
  local src="$CORPUS/$cdir"
  local w="$OUT/w.$suite.$(echo "$cdir$label"|tr -c 'A-Za-z0-9._-' '_')"
  rm -rf "$w"; mkdir -p "$w"
  local arch="$w/a.zpaq"
  local rf=$(readflags "$af")
  local orig; orig=$(du -sb "$src" 2>/dev/null | cut -f1)

  echo "### $suite | $cdir | $label" >> "$LOG"
  local t0 t1 t2 t3
  t0=$(date +%s.%N)
  if ! timeout $TMO $Z a "$arch" "$src" $af -summary >>"$LOG" 2>&1; then
    echo "$suite,$cdir,$label,$orig,,,,,ADD_FAIL,ADD_FAIL,$nota" >> "$CSV"
    printf '%-4s %-8s %-26s ADD_FAIL\n' "$suite" "$cdir" "$label"; rm -rf "$w"; return
  fi
  t1=$(date +%s.%N)
  local asz; asz=$(stat -c%s "$arch" 2>/dev/null || echo 0)

  local tok=OK
  timeout $TMO $Z t "$arch" $rf >>"$LOG" 2>&1 </dev/null || tok=FAIL

  t2=$(date +%s.%N)
  if ! timeout $TMO $Z x "$arch" -to "$w/out/" -force $rf -summary >>"$LOG" 2>&1 </dev/null; then
    echo "$suite,$cdir,$label,$orig,$asz,,,,$tok,EXT_FAIL,$nota" >> "$CSV"
    printf '%-4s %-8s %-26s EXT_FAIL\n' "$suite" "$cdir" "$label"; rm -rf "$w"; return
  fi
  t3=$(date +%s.%N)

  # Algunos flags cambian el layout a proposito (-nopath, filtros de tamano,
  # -norecursion): ahi el diff byte-exacto no aplica y solo se exige que el
  # round-trip no falle. Se marcan con nota "nodiff".
  local ver=MATCH
  if [ "${nota#nodiff}" != "$nota" ]; then
    local nf; nf=$(find "$w/out" -type f 2>/dev/null | wc -l)
    if [ "$nf" -gt 0 ]; then ver=NODIFF-OK; else ver=NODIFF-VACIO; fi
  else
    diff -r --no-dereference "$src" "$w/out$src" >>"$LOG" 2>&1 || ver=MISMATCH
  fi

  local ratio; ratio=$(echo "scale=4; if ($orig>0) $asz/$orig else 0" | bc)
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' "$suite" "$cdir" "$label" "$orig" "$asz" \
    "$ratio" "$(echo "$t1-$t0"|bc)" "$(echo "$t3-$t2"|bc)" "$tok" "$ver" "$nota" >> "$CSV"
  printf '%-4s %-8s %-26s %11s -> %11s  %s %s\n' "$suite" "$cdir" "$label" "$orig" "$asz" "$tok" "$ver"
  rm -rf "$w"
}
