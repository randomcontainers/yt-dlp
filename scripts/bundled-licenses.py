"""Collect the license files of the libraries linked into curl_cffi.

Usage: bundled-licenses.py

curl_cffi's Linux wheels link a static build of curl-impersonate, which
contains curl and the libraries curl uses, but they ship only curl_cffi's own
license. This reads the curl_cffi version from requirements.lock, reads the
curl-impersonate version it is built with from the curl_cffi source release,
finds the library versions that curl-impersonate release uses, and writes
their license files and the URLs and SHA-256 of their source archives to
licenses/curl_cffi-<version>/bundled/. Run it whenever the curl_cffi pin in
requirements.lock changes.
"""

import hashlib
import io
import json
import pathlib
import re
import shutil
import sys
import tarfile
import textwrap
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
GITHUB = "https://raw.githubusercontent.com/{repo}/{ref}/{file}"
GITLAB = "https://gitlab.com/{repo}/-/raw/{ref}/{file}"

# name: (host, repository, ref template, license files). The ref template is
# filled from the variables of curl-impersonate's CMakeLists.txt and Makefile.
LIBRARIES = {
    "curl": (GITHUB, "curl/curl", "{CURL_VERSION}", ["COPYING"]),
    "boringssl": (GITHUB, "google/boringssl", "{BORINGSSL_COMMIT}", ["LICENSE"]),
    "brotli": (GITHUB, "google/brotli", "v{BROTLI_VERSION}", ["LICENSE"]),
    "nghttp2": (GITHUB, "nghttp2/nghttp2", "v{NGHTTP2_VERSION}", ["COPYING"]),
    "nghttp3": (GITHUB, "ngtcp2/nghttp3", "v{NGHTTP3_VERSION}", ["COPYING"]),
    "ngtcp2": (GITHUB, "ngtcp2/ngtcp2", "v{NGTCP2_VERSION}", ["COPYING"]),
    "zlib": (GITHUB, "madler/zlib", "v{ZLIB_VERSION}", ["LICENSE"]),
    "zstd": (GITHUB, "facebook/zstd", "v{ZSTD_VERSION}", ["LICENSE"]),
    "libidn2": (
        GITLAB,
        "libidn/libidn2",
        "v{LIBIDN2_VERSION}",
        ["COPYING", "COPYINGv2", "COPYING.LESSERv3", "COPYING.unicode"],
    ),
}


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def sha256(url):
    return hashlib.sha256(fetch(url)).hexdigest()


def variables(text, pattern):
    found = {name: value for name, value in re.findall(pattern, text, re.M)}
    for name, value in found.items():
        found[name] = re.sub(r"\$[{(](\w+)[})]", lambda m: found.get(m.group(1), m.group(0)), value)
    return found


def main():
    lock = (ROOT / "requirements.lock").read_text()
    match = re.search(r"^curl-cffi==([^\s;]+)", lock, re.M)
    if not match:
        sys.exit("requirements.lock does not pin curl-cffi")
    cffi = match.group(1)

    release = json.loads(fetch(f"https://pypi.org/pypi/curl-cffi/{cffi}/json"))
    sdists = [f for f in release["urls"] if f["packagetype"] == "sdist"]
    if len(sdists) != 1:
        sys.exit(f"curl_cffi {cffi} has {len(sdists)} source releases on PyPI")
    sdist = sdists[0]
    data = fetch(sdist["url"])
    if hashlib.sha256(data).hexdigest() != sdist["digests"]["sha256"]:
        sys.exit(f"{sdist['url']} does not match its SHA-256 on PyPI")
    top = sdist["filename"].removesuffix(".tar.gz")
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        try:
            build = tar.extractfile(f"{top}/scripts/build.py").read().decode()
        except KeyError:
            sys.exit(f"{sdist['filename']} has no scripts/build.py")
    match = re.search(r'^__version__ = "([^"]+)"', build, re.M)
    if not match:
        sys.exit(f"no curl-impersonate version in curl_cffi {cffi} scripts/build.py")
    impersonate = match.group(1)
    upstream, ref = "lexiforest/curl-impersonate", f"v{impersonate}"
    cmake = fetch(GITHUB.format(repo=upstream, ref=ref, file="CMakeLists.txt")).decode()
    make = fetch(GITHUB.format(repo=upstream, ref=ref, file="Makefile")).decode()
    values = variables(cmake, r'^set\((\w+) "([^"]*)"\)')
    values.update(variables(make, r"^(LIBIDN2_\w+) \?= (\S+)$"))

    # A dependency added upstream needs its license files here too.
    projects = set(re.findall(r"^\s*ExternalProject_Add\((\w+)", cmake, re.M))
    if "USE_LIBIDN2" in cmake:
        projects.add("libidn2")
    unknown = sorted(projects - set(LIBRARIES))
    if unknown:
        sys.exit(f"curl-impersonate {impersonate} builds libraries this script does not know: {unknown}")
    if "curl" not in projects:
        sys.exit(f"curl-impersonate {impersonate}: no curl project in CMakeLists.txt")

    archive = f"https://github.com/{upstream}/archive/refs/tags/{ref}.tar.gz"
    intro = (
        f"curl_cffi {cffi} links libcurl-impersonate statically into its extension module. "
        f"curl-impersonate {impersonate} built that library from the sources listed after it. "
        "The license files of curl-impersonate and of each library are in the directory of "
        "the same name. libidn2, which includes its own copy of libunistring, is licensed "
        "under GPL-2.0-or-later or LGPL-3.0-or-later. The libidn2 archive is its source. "
        "The curl_cffi source release and the curl-impersonate archive, which has the "
        "patches and build scripts, are what you need to rebuild the extension module "
        "with a modified libidn2."
    )
    sources = [textwrap.fill(intro, 76, break_on_hyphens=False), ""]
    sources += [f"curl_cffi {cffi}", f"  {sdist['url']}", f"  sha256:{sdist['digests']['sha256']}"]
    sources += [f"curl-impersonate {impersonate}", f"  {archive}", f"  sha256:{sha256(archive)}"]
    own = GITHUB.format(repo=upstream, ref=ref, file="LICENSE")
    urls = {"curl-impersonate": {"LICENSE": own}}
    for name in sorted(projects):
        host, repo, template, files = LIBRARIES[name]
        prefix = name.upper()
        version = values.get(f"{prefix}_VERSION") or values[f"{prefix}_COMMIT"]
        if name == "curl":
            version = version.removeprefix("curl-").replace("_", ".")
        url = values[f"{prefix}_URL"]
        digest = values.get(f"{prefix}_URL_HASH", "")
        digest = digest.removeprefix("SHA256=") if digest.startswith("SHA256=") else sha256(url)
        sources += [f"{name} {version}", f"  {url}", f"  sha256:{digest}"]
        lib_ref = template.format(**values)
        urls[name] = {file: host.format(repo=repo, ref=lib_ref, file=file) for file in files}
    texts = {name: {file: fetch(url) for file, url in files.items()} for name, files in urls.items()}

    base = ROOT / "licenses"
    for old in base.glob("curl_cffi-*"):
        shutil.rmtree(old)
    out = base / f"curl_cffi-{cffi}" / "bundled"
    for name, files in texts.items():
        (out / name).mkdir(parents=True)
        for file, content in files.items():
            (out / name / file).write_bytes(content)
    (out / "SOURCES").write_text("\n".join(sources) + "\n")
    print(f"wrote {out.relative_to(ROOT)} for curl-impersonate {impersonate}")


if __name__ == "__main__":
    main()
