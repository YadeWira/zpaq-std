# Rama `upstream` — snapshots de zpaqfranz, sin modificar

Esta rama **no se compila y no se toca a mano**. Es un único archivo: el fuente
de [zpaqfranz](https://github.com/fcorbelli/zpaqfranz) tal como lo publica
fcorbelli, un commit por release.

## Para qué

zpaq-std es un fork vendorizado de zpaqfranz. Sin esta rama, cada actualización
de upstream era arqueología: había que adivinar de qué versión partía el fork,
bajar dos tarballs y hacer un `git merge-file` a mano. Con ella, `main` y
`upstream` comparten historia y traer una versión nueva es:

    git checkout upstream
    curl -L -o zpaq-std.cpp https://github.com/fcorbelli/zpaqfranz/releases/download/<TAG>/zpaqfranz.cpp
    git commit -am "upstream: zpaqfranz <TAG>"
    git checkout main && git merge upstream

y git calcula la base común solo.

## Por qué el archivo se llama `zpaq-std.cpp` y no `zpaqfranz.cpp`

Porque git empareja por RUTA. Si acá se llamara `zpaqfranz.cpp`, el merge vería
un archivo borrado y otro creado en vez de una modificación, y no habría fusión a
tres bandas. El contenido es el de upstream, byte a byte y sin editar.

## Regla

Nada de cambios propios acá. Esta rama existe para responder "¿qué decía upstream
exactamente?" — si se la edita, deja de poder responderlo.
