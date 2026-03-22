load("@rules_cc//cc:defs.bzl", "cc_library")

cc_library(
    name = "libooz",
    srcs = [
        "bitknit.cpp",
        "compr_entropy.cpp",
        "compr_kraken.cpp",
        "compr_leviathan.cpp",
        "compr_match_finder.cpp",
        "compr_mermaid.cpp",
        "compr_multiarray.cpp",
        "compr_tans.cpp",
        "compress.cpp",
        "kraken.cpp",
        "lzna.cpp",
        "stdafx.cpp",
    ],
    hdrs = [
        "bits_rev_table.h",
        "compr_entropy.h",
        "compr_kraken.h",
        "compr_leviathan.h",
        "compr_match_finder.h",
        "compr_mermaid.h",
        "compr_util.h",
        "compress.h",
        "log_lookup.h",
        "match_hasher.h",
        "qsort.h",
        "stdafx.h",
        "targetver.h",
    ],
    copts = [
        "-std=c++17",
        "-Wno-unused-variable",
        "-Wno-missing-braces",
        "-Wno-unknown-pragmas",
    ],
    defines = ["OOZ_DYNAMIC"],
    local_defines = [
        "OOZ_BUILD_DLL",
        # Chromium Clang's x86gprintrin.h doesn't define _rotl.
        # Force the fallback path in stdafx.h.
        "_rotl(x,n)=(((x)<<(n))|((x)>>(32-(n))))",
    ],
    visibility = ["//visibility:public"],
    deps = ["@simde"],
)

cc_library(
    name = "bunutil",
    srcs = [
        "fnv.cpp",
        "murmur.cpp",
        "path_rep.cpp",
        "utf.cpp",
        "util.cpp",
    ],
    hdrs = [
        "fnv.h",
        "murmur.h",
        "path_rep.h",
        "utf.h",
        "util.h",
    ],
    copts = ["-std=c++17"],
    visibility = ["//visibility:public"],
    deps = [
        "@libsodium",
        "@libunistring",
    ],
)

cc_library(
    name = "mio",
    hdrs = ["libpoe/mio/single_include/mio/mio.hpp"],
    strip_include_prefix = "libpoe/mio/single_include",
)

cc_library(
    name = "libpoe",
    srcs = [
        "libpoe/poe/format/ggpk.cpp",
        "libpoe/poe/util/install_location.cpp",
        "libpoe/poe/util/murmur2.cpp",
        "libpoe/poe/util/random_access_file.cpp",
        "libpoe/poe/util/sha256.cpp",
        "libpoe/poe/util/utf.cpp",
    ],
    hdrs = [
        "libpoe/poe/format/ggpk.hpp",
        "libpoe/poe/util/install_location.hpp",
        "libpoe/poe/util/murmur2.hpp",
        "libpoe/poe/util/random_access_file.hpp",
        "libpoe/poe/util/sha256.hpp",
        "libpoe/poe/util/utf.hpp",
    ],
    copts = ["-std=c++17"],
    strip_include_prefix = "libpoe",
    visibility = ["//visibility:public"],
    deps = [
        ":mio",
        "@libsodium",
        "@libunistring",
    ],
)

cc_library(
    name = "libbun",
    srcs = ["bun.cpp"],
    hdrs = ["bun.h"],
    copts = ["-std=c++17"],
    defines = ["BUN_DYNAMIC"],
    includes = ["."],
    linkopts = ["-ldl"],
    local_defines = ["BUN_BUILD_DLL"],
    visibility = ["//visibility:public"],
    deps = [
        ":bunutil",
        ":libpoe",
    ],
)
