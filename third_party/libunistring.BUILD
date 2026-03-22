load("@rules_cc//cc:defs.bzl", "cc_library")

cc_library(
    name = "libunistring",
    srcs = [
        # u16_to_u8 and dependencies
        "lib/unistr/u16-to-u8.c",
        "lib/unistr/u16-mbtoucr.c",
        "lib/unistr/u8-uctomb.c",
        "lib/unistr/u8-uctomb-aux.c",

        # u8_to_u16 and dependencies
        "lib/unistr/u8-to-u16.c",
        "lib/unistr/u8-mbtoucr.c",
        "lib/unistr/u16-uctomb.c",
        "lib/unistr/u16-uctomb-aux.c",

        # u16_tolower and dependencies
        "lib/unicase/u16-tolower.c",
        "lib/unicase/u16-casemap.c",
        "lib/unicase/tolower.c",
        "lib/unicase/special-casing.c",
        "lib/unicase/empty-prefix-context.c",
        "lib/unicase/empty-suffix-context.c",
        "lib/unicase/cased.c",
        "lib/unicase/ignorable.c",
        "lib/unictype/pr_soft_dotted.c",
        "lib/unictype/combiningclass.c",
        "lib/unistr/u16-mbtouc-unsafe.c",
        "lib/unistr/u16-mbtouc-unsafe-aux.c",
        "lib/unistr/u16-cpy.c",

        # Stub: u16_normalize is referenced by u16_casemap but never
        # called when nf==NULL (which is how u16_tolower invokes it).
        "lib/u16_normalize_stub.c",

        # Internal headers used by the .c files
        "lib/unicase/caseprop.h",
        "lib/unicase/cased.h",
        "lib/unicase/context.h",
        "lib/unicase/ignorable.h",
        "lib/unicase/simple-mapping.h",
        "lib/unicase/special-casing-table.h",
        "lib/unicase/tolower.h",
        "lib/unicase/u-casemap.h",
        "lib/unicase/unicasemap.h",
        "lib/unictype/bitmap.h",
        "lib/unictype/combiningclass.h",
        "lib/unictype/pr_soft_dotted.h",
        "lib/unistr/u-cpy.h",
        "lib/unistring-notinline.h",
        "lib/attribute.h",
    ],
    hdrs = [
        "lib/unicase.h",
        "lib/unistr.h",
        "lib/unitypes.h",
        "lib/uninorm.h",
        "lib/unictype.h",
        "lib/unistring/cdefs.h",
        "lib/unistring/inline.h",
        "lib/unistring/stdint.h",
        "lib/unistring/woe32dll.h",
    ],
    copts = [
        "-DHAVE_CONFIG_H",
        "-DIN_LIBUNISTRING",
        "-Wno-unused-parameter",
    ],
    includes = [
        ".",
        "lib",
    ],
    textual_hdrs = [
        "lib/unicase/special-casing.h",
        "lib/unicase/special-casing.in.h",
        "config.h",
    ],
    visibility = ["//visibility:public"],
)
