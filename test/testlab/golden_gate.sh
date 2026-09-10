#!/bin/bash
# ============================================================================
# golden_gate.sh — archivos .zpaq de la ERA DE PRODUCCION como test de regresion.
#
# POR QUE EXISTE: difftest.sh compara dos binarios generando el archivo CON EL
# BINARIO C ACTUAL. Eso detecta divergencias entre A y B, pero no ancla nada a
# los bytes que realmente existen en produccion -- y hay archivos de 46 GB
# alla afuera (caso CLAAS). Hasta ahora ningun test agarraba un .zpaq escrito
# por una version PUBLICADA y verificaba que el build de hoy lo extrae bien.
#
# Es estrictamente mas fuerte que difftest para compatibilidad de formato:
# difftest regenera el archivo de A; el golden fija bytes historicos y sigue
# sirviendo para todas las fases futuras de la migracion a Rust.
#
# El corpus tiene que estar PINNEADO (pin_corpus.sh): las suites lo regeneran
# con `find | head`, que elige archivos distintos entre corridas, y un golden
# sobre datos que se mueven no verifica nada.
#
#   uso: golden_gate.sh gen   <binario-de-referencia> [subdir]
#        golden_gate.sh check <binario-candidato> [subdir]
#        golden_gate.sh list
# ============================================================================
set -u
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
G=$W/golden
CORPUS=$W/corpus
TMO=${TMO:-600}

# --- la matriz ---------------------------------------------------------------
# Casos chicos: los 7 de difftest (11 MB en total)
# Todo sobrescribible por entorno, para poder probar la matriz chica.
CASES_SMALL="${CASES_SMALL:-text bin img mixed intl edge precomp}"
# Casos estructurales/grandes (46 MB): solo con metodos representativos, para
# que el golden no pese un gigabyte
CASES_BIG="${CASES_BIG:-bigtext dupes many sparse}"
# Todos los metodos, sobre los casos chicos
METHODS_ALL="${METHODS_ALL:--store -m1 -m2 -m3 -m5 -ma:bzip2 -ma:bzip2:9 -ma:snappy -ma:lzfse -ma:lzfse:1 -ma:ppmd:2 -ma:ppmd:6 -ma:ppmd:32 -ma:brotli:1 -ma:brotli:5 -ma:brotli:11}"
# Metodos representativos, sobre los casos grandes
METHODS_REP="${METHODS_REP:--store -m1 -m3 -ma:bzip2 -ma:snappy -ma:ppmd:6}"

etiqueta() { echo "$1" | sed -e 's/^-//' -e 's/[:.]/_/g'; }

cmd="${1:?falta gen|check|list}"

if [ "$cmd" = "list" ]; then
    for d in "$G"/*/; do
        [ -d "$d" ] || continue
        printf '%-18s %4d archivos  %s\n' "$(basename "$d")" \
          "$(find "$d" -name '*.zpaq' | wc -l)" "$(du -sh "$d" | cut -f1)"
    done
    exit 0
fi

BIN="${2:?falta binario}"
SUB="${3:-$(basename "$BIN")}"
D=$G/$SUB

# wine para los .exe, transparente
export WINEDEBUG=-all
run() { case "$BIN" in *.exe) timeout $TMO wine "$BIN" "$@";; *) timeout $TMO "$BIN" "$@";; esac; }

if [ "$cmd" = "gen" ]; then
    bash "$W/pin_corpus.sh" verify >/dev/null || { echo "ABORTA: el corpus no coincide con el manifiesto"; exit 2; }
    rm -rf "$D"; mkdir -p "$D"
    cp "$CORPUS/MANIFEST.sha256" "$D/corpus.sha256"
    printf 'generado con: %s\nsha256 del binario: %s\nfecha: %s\n' \
      "$BIN" "$(sha256sum "$BIN" | cut -d' ' -f1)" "$(date -Is)" > "$D/ORIGEN.txt"
    n=0
    gen_uno() { # $1=metodo $2=caso
        local m="$1" c="$2" f="$D/$(etiqueta "$m")--$2.zpaq"
        [ -d "$CORPUS/$c" ] || return 0
        run a "$f" "$CORPUS/$c" "$m" -nomore -t1 >/dev/null 2>&1
        if [ -s "$f" ]; then n=$((n+1)); printf '.'; else printf 'x'; echo " FALLO: $m $c" >&2; fi
    }
    echo "== metodos completos x casos chicos =="
    for m in $METHODS_ALL; do for c in $CASES_SMALL; do gen_uno "$m" "$c"; done; done; echo
    echo "== metodos representativos x casos grandes =="
    for m in $METHODS_REP;  do for c in $CASES_BIG;   do gen_uno "$m" "$c"; done; done; echo
    sha256sum "$D"/*.zpaq | sed "s|$D/||" > "$D/golden.sha256"
    echo "$n archivos en $D ($(du -sh "$D" | cut -f1))"
    echo DONE_GEN
    exit 0
fi

# ---------------------------- check -----------------------------------------
[ -d "$D" ] || { echo "no hay golden en $D (corre 'gen' primero)"; exit 2; }
CSV=$D/check-$(basename "$BIN").csv
LOG=$D/check-$(basename "$BIN").log
echo "golden,x_rc,t_rc,contenido,resultado" > "$CSV"; : > "$LOG"

# integridad de los propios golden: si cambiaron, el test no vale
(cd "$D" && sha256sum -c golden.sha256 --quiet) || { echo "ABORTA: los golden cambiaron respecto de golden.sha256"; exit 2; }
cmp -s "$D/corpus.sha256" "$CORPUS/MANIFEST.sha256" \
  || { echo "ABORTA: el corpus no es el que se uso para generar estos golden"; exit 2; }

T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# Un binario de Windows bajo wine NO resuelve una ruta Linux desnuda como
# destino: getfreespace devuelve 0 y aborta con "00935! Not enough free space".
# wine mapea '/' en la unidad Z:, asi que hay que prefijarlo. Sin esto los tres
# .exe fallan el 100% de los golden por culpa del harness, no del binario.
case "$BIN" in *.exe) TOPFX="Z:";; *) TOPFX="";; esac
ok=0; bad=0
for f in "$D"/*.zpaq; do
    base=$(basename "$f" .zpaq); caso=${base##*--}
    rm -rf "$T/o"
    run x "$f" -to "$TOPFX$T/o/" -force -nomore >>"$LOG" 2>&1; xrc=$?
    run t "$f" -nomore >>"$LOG" 2>&1; trc=$?
    # el archivo guarda la ruta completa del corpus: buscar el arbol extraido
    ext=$(find "$T/o" -type d -name "$caso" 2>/dev/null | head -1)
    cont=OK
    if [ -z "$ext" ]; then cont=NO_EXTRAJO
    elif ! diff -r "$CORPUS/$caso" "$ext" >>"$LOG" 2>&1; then cont=DIFF; fi
    res=PASA
    { [ "$xrc" = 0 ] && [ "$trc" = 0 ] && [ "$cont" = OK ]; } || res=FALLA
    [ "$res" = PASA ] && ok=$((ok+1)) || { bad=$((bad+1)); printf '  FALLA %-34s x=%s t=%s %s\n' "$base" "$xrc" "$trc" "$cont"; }
    echo "$base,$xrc,$trc,$cont,$res" >> "$CSV"
done
echo
echo "===== $((ok+bad)) golden, $ok pasan, $bad fallan  ($(basename "$BIN")) ====="
echo "  csv: $CSV"
echo DONE_CHECK
[ "$bad" -eq 0 ]
