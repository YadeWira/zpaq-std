<!-- markdownlint-disable MD041 -->

A slim, multi-architecture Docker image that compiles `zpaq-std`
from source on Ubuntu (glibc) and publishes it to GHCR.

Quick start

```bash
docker pull ghcr.io/fcorbelli/zpaq-std:latest

docker run --rm ghcr.io/fcorbelli/zpaq-std:latest version

docker run --rm \
  -v "$PWD:/data" \
  ghcr.io/fcorbelli/zpaq-std:latest \
  a backup.zpaq .
```

The container entrypoint is `zpaq-std`, so any additional arguments
are passed straight through to the tool.
The default working directory is `/data`, and the image runs as a
non-root user.

If you bind-mount a host directory and get permission errors, run the
container as your user:

```bash
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$PWD:/data" \
  ghcr.io/fcorbelli/zpaq-std:latest \
  a backup.zpaq .
```

Local build

The Docker build context is `docker/` (kept small on purpose), so you
need to stage `zpaq-std.cpp` into it:

```bash
cp zpaq-std.cpp docker/zpaq-std.cpp
docker build -t zpaq-std:local -f docker/Dockerfile docker
```

Tags and architectures

- `ghcr.io/fcorbelli/zpaq-std:latest` for `linux/amd64` and
  `linux/arm64` (most recent build).
- `ghcr.io/fcorbelli/zpaq-std:<version>` for `linux/amd64` and
  `linux/arm64` (specific zpaq-std tag, for example `64.4`).

How it stays up to date

- Publishing a new GitHub Release triggers the container build
  workflow, which builds multi-arch images with Docker Buildx and
  pushes them to GHCR.
