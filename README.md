# yt-dlp

Container images with [yt-dlp](https://github.com/yt-dlp/yt-dlp), installed from PyPI into a virtual environment on Ubuntu or Alpine. The default image adds FFmpeg and Deno, so merging formats, extracting audio and full YouTube support work without extra setup. The images are rebuilt when yt-dlp publishes a release and when the base image changes, for `linux/amd64` and `linux/arm64`.

This is an unofficial build, not affiliated with or endorsed by the yt-dlp project. Report problems with the image in this repository and problems with yt-dlp itself in the [yt-dlp issue tracker](https://github.com/yt-dlp/yt-dlp/issues).

## Quick start

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" \
  ghcr.io/randomcontainers/yt-dlp "https://www.youtube.com/watch?v=<id>"
```

The same images can also be pulled as `randomcontainers.com/yt-dlp`.

Extract the audio as MP3:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" \
  ghcr.io/randomcontainers/yt-dlp -x --audio-format mp3 "https://www.youtube.com/watch?v=<id>"
```

Downloads go to `/work`, the working directory. Other files yt-dlp uses:

- Configuration: mount a file at `/etc/yt-dlp.conf`, for example `-v "$PWD/yt-dlp.conf:/etc/yt-dlp.conf:ro"`.
- Cookies: pass `--cookies cookies.txt` with the file in `/work`. yt-dlp writes the updated cookies back to the same file, so it must be writable. `--cookies-from-browser` needs a browser profile, which the container does not have, so export the cookies to a file instead.
- Cache: yt-dlp keeps YouTube player data in `/cache`. Add `-v yt-dlp-cache:/cache` to keep it between runs.

## What is in the image

| | slim | default |
|---|---|---|
| yt-dlp and the Python packages of its `default` extra, including yt-dlp-ejs | yes | yes |
| curl_cffi, for `--impersonate` | yes | yes |
| FFmpeg and ffprobe, to merge formats and post-process | no | yes |
| Deno, the JavaScript runtime yt-dlp needs for full YouTube support | no | yes |

FFmpeg is the [randomcontainers/ffmpeg](https://github.com/randomcontainers/ffmpeg) build. On Ubuntu, Deno is the PyPI `deno` package at the version yt-dlp pins in its `pin-deno` extra, installed into yt-dlp's virtual environment. On Alpine it is Alpine's `deno` package, which is updated with Alpine releases and can be several Deno releases behind.

## Default or slim

The default image (`latest`) is recommended for general use, because common tasks such as merging video and audio or downloading from YouTube need nothing extra. Use `slim` as the base when you build your own image and want that base kept up to date. Without a JavaScript runtime, some YouTube formats are missing; yt-dlp uses Deno as soon as it is on `PATH`.

The default image is also published as `ghcr.io/randomcontainers/yt-dlp-ffmpeg`, built in the [yt-dlp-ffmpeg](https://github.com/randomcontainers/yt-dlp-ffmpeg) repository with the same contents and a different digest.

## Tags

`<version>` is a yt-dlp release such as `2026.08.19`.

| Default (with FFmpeg and Deno) | Slim | Base |
|---|---|---|
| `latest`, `<version>` | `slim`, `<version>-slim` | Ubuntu |
| `ubuntu`, `<version>-ubuntu` | `slim-ubuntu`, `<version>-slim-ubuntu` | Ubuntu |
| `<version>-ubuntu26.04` | `<version>-slim-ubuntu26.04` | Ubuntu 26.04 |
| `alpine`, `<version>-alpine` | `slim-alpine`, `<version>-slim-alpine` | Alpine |
| `<version>-alpine3.24` | `<version>-slim-alpine3.24` | Alpine 3.24 |

The images are currently built on Ubuntu 26.04 and Alpine 3.24. Tags without a distro version move to the next distro release when the project does; tags ending in `ubuntu26.04` or `alpine3.24` stay on that release and are no longer rebuilt once the project moves to the next one. Every tag of the current yt-dlp version, including the exact version, is rebuilt in place (see [Updates](#updates)), so pin a digest when you need the same bytes every time.

## Platforms

`linux/amd64` and `linux/arm64`, for both Ubuntu and Alpine. Both are built natively on GitHub-hosted runners, without emulation. The same `requirements.lock` is installed on all four combinations of distro and architecture. Its compiled packages come as glibc (`manylinux`) wheels on Ubuntu and musl (`musllinux`) wheels on Alpine.

## Files and permissions

The working directory is `/work`. The image runs as UID 1000, and any other UID works too: `HOME` is then `/`, and caches go to `/cache`, which anyone can write to. How to get output files owned by you depends on how you run containers:

| Runtime | Flag |
|---|---|
| Docker on Linux (rootful), GitHub Actions | `--user "$(id -u):$(id -g)"` |
| Rootless Podman | `--userns=keep-id` |
| Rootless Docker | `--user 0:0` (root in the container is your user on the host) |
| Docker Desktop on macOS or Windows | none, file ownership is mapped for you |

## Extending the slim image

Use a `slim` tag as the base for your own image. `slim`, `slim-ubuntu` and `slim-alpine` move to each new yt-dlp release and are rebuilt when the distro base image changes. yt-dlp lives in a virtual environment at `/usr/local/lib/yt-dlp` that uses the distro's `python3`, and only `yt-dlp` itself is linked into `/usr/local/bin`. The distro packages it needs are listed in `/usr/local/share/randomcontainers/yt-dlp/runtime-deps`. Switch to root to install more, then back:

```dockerfile
FROM ghcr.io/randomcontainers/yt-dlp:slim-ubuntu@sha256:...
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends aria2 \
 && rm -rf /var/lib/apt/lists/*
USER 1000:1000
```

On Alpine, use `apk add --no-cache aria2`. Python plugins go into the same virtual environment with `/usr/local/lib/yt-dlp/bin/pip install --no-cache-dir <plugin>==<version>`. The entrypoint is `["tini", "--", "yt-dlp"]`; set your own `ENTRYPOINT` if your image runs something else. To pick up new yt-dlp releases and base image fixes, let Dependabot or Renovate update the digest in your `FROM` line.

## Verifying

Each image has a build provenance attestation from this repository's GitHub Actions run, signed by the shared build workflow in `randomcontainers/ci`:

```sh
gh attestation verify oci://ghcr.io/randomcontainers/yt-dlp:latest \
  --repo randomcontainers/yt-dlp --signer-repo randomcontainers/ci
```

Images from `ghcr.io/randomcontainers/yt-dlp-ffmpeg` are built in that repository, so verify them with `--repo randomcontainers/yt-dlp-ffmpeg` and the same `--signer-repo`.

Each platform image also carries an SPDX SBOM that lists the distro and Python packages in it with their versions:

```sh
docker buildx imagetools inspect ghcr.io/randomcontainers/yt-dlp:latest --format '{{ json .SBOM }}'
```

The Python packages are installed with `pip --require-hashes --only-binary=:all:` from `requirements.lock`, which pins every wheel by SHA-256. The URL and hash of each installed wheel are in `/usr/local/share/randomcontainers/yt-dlp/source`, and the installed versions in `buildinfo` next to it.

## Updates

The project checks [yt-dlp on PyPI](https://pypi.org/project/yt-dlp/) every 15 minutes. A release is picked up once it is 24 hours old and its PyPI provenance shows it was published from the yt-dlp/yt-dlp repository. The new version and a regenerated `requirements.lock` are then committed to this repository and the images are rebuilt. Only the newest release is built; tags of older versions stay as they were last built. Nightly builds are not published.

yt-dlp's `pin` and `pin-curl-cffi` extras fix the version of every dependency, and `requirements.lock` adds their hashes. The lock is regenerated weekly at the same yt-dlp version, and only accepts dependency releases that are at least 7 days old. yt-dlp-ejs, and Deno in `requirements-deno.lock`, are exempt from that wait, because yt-dlp pins them exactly and a new yt-dlp release can require a version published the same day.

The images of the current version are also rebuilt when the Ubuntu or Alpine base image changes, the default ones when a new FFmpeg image is published, and all of them at least every 7 days, so distro security fixes reach the current tags.

## Building

```sh
docker build -f Dockerfile.ubuntu --build-arg VERSION=<version> -t yt-dlp:local .
```

Use `Dockerfile.alpine` for the Alpine image. `VERSION` must be the version in `package.yml`, because the build checks that `requirements.lock` installs it. The default image is generated from the `combos` section of `package.yml` by [randomcontainers/ci](https://github.com/randomcontainers/ci).

`requirements.lock` and `requirements-deno.lock` are produced by `uv pip compile --universal --generate-hashes --only-binary :all:` from yt-dlp's `pin` extras and are updated together with the version in `package.yml`. The second line of each file is the exact command. To regenerate one at the version in `package.yml`, run `rc lock requirements.lock` or `rc lock requirements-deno.lock` in this directory. `rc` is the command-line tool of [randomcontainers/ci](https://github.com/randomcontainers/ci), and it needs uv on `PATH`.

If a new lock changes the curl_cffi version, run `python3 scripts/bundled-licenses.py` to refresh `licenses/`. The build fails until those files match the installed curl_cffi.

## Licenses

yt-dlp is released under the [Unlicense](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE). The slim image adds Python packages under other licenses, among them mutagen (GPL-2.0-or-later), certifi (MPL-2.0) and requests (Apache-2.0). The complete SPDX expression is in the image's `org.opencontainers.image.licenses` label, and each package's license files are in `/usr/local/share/randomcontainers/yt-dlp/licenses/`.

curl_cffi's extension module links a static build of [curl-impersonate](https://github.com/lexiforest/curl-impersonate), which contains curl, BoringSSL, zlib, brotli, zstd, nghttp2, nghttp3, ngtcp2 and libidn2. The curl_cffi wheel ships only curl_cffi's own license, so this repository adds the license files of those libraries in [`licenses/`](licenses/), and the image has them in `/usr/local/share/randomcontainers/yt-dlp/licenses/curl_cffi/bundled/`. The `SOURCES` file there names the curl_cffi source release and the source archive of each library with its SHA-256. libidn2 is licensed under GPL-2.0-or-later or LGPL-3.0-or-later. The libidn2 archive is its source. The curl_cffi source release and the curl-impersonate archive, which has the patches and build scripts, are what you need to rebuild the extension module with a modified libidn2.

The default image also contains FFmpeg, which is built with `--enable-gpl --enable-version3` and licensed under GPL-3.0-or-later (see [randomcontainers/ffmpeg](https://github.com/randomcontainers/ffmpeg) for its source), and Deno, which is MIT licensed.

The files in this repository are available under the MIT license, see [LICENSE](LICENSE).

## Requesting a tool

To suggest another tool, use the [Request a tool](https://github.com/randomcontainers/.github/issues/new?template=tool-request.yml) form.
