"""Macros for the patcher data processing pipeline."""

_GAMEDATA = "@gamedata//:all"
_INDEX_BIN = "@gamedata//:Bundles2/_.index.bin"
_EXTRACT = "//patcher/extract"
_DAT2JSONL = "//patcher/cmd/dat2jsonl"
_SCHEMA = "//patcher:schema.min.json"
_GGPKD = "$$(dirname $$(dirname $(location @gamedata//:Bundles2/_.index.bin)))"

def patcher_extract(name, path, out):
    """Extract a file from game bundles."""
    native.genrule(
        name = name,
        srcs = [_GAMEDATA, _INDEX_BIN],
        outs = [out],
        cmd = "$(location {extract}) {ggpkd} '{path}' $@".format(
            extract = _EXTRACT,
            ggpkd = _GGPKD,
            path = path,
        ),
        tools = [_EXTRACT],
    )

def patcher_dat2jsonl(name, table_name, lang):
    """Extract a .datc64 file and convert it to .jsonl.

    Creates two targets: extract_{name} and dat2jsonl_{name}.
    """
    datfiles = {"en": "", "tc": "traditional chinese/"}
    extract_name = "extract_%s" % name
    datfile = "%sdata/%s%s.datc64" % ("", datfiles[lang], table_name.lower())

    patcher_extract(
        name = extract_name,
        path = datfile,
        out = "extracted/%s.%s.datc64" % (table_name, lang),
    )

    native.genrule(
        name = "dat2jsonl_%s" % name,
        srcs = [":%s" % extract_name, _SCHEMA],
        outs = ["extracted/%s.%s.jsonl" % (table_name, lang)],
        cmd = "$(location {dat2jsonl}) --dat=$(location :{extract}) --table-name={table} --schema=$(location {schema}) > $@".format(
            dat2jsonl = _DAT2JSONL,
            extract = extract_name,
            table = table_name,
            schema = _SCHEMA,
        ),
        tools = [_DAT2JSONL],
    )
