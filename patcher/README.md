# Patcher

Tools for downloading and extracting game data from the PoE TW patch server.

## Prerequisites

* [Bazelisk](https://github.com/bazelbuild/bazelisk) installed as `bazel`
* `curl`

## Usage

### Fetch game data

Downloads the schema and game files from the patch server:

```
bash fetch.sh
```

### Build release files

Runs the Bazel pipeline (extract → dat2jsonl → release JSON):

```
bash main.sh
```

### Compare with current web data

```
bash diff.sh
```

### Copy release files to the web app

```
bash release.sh
```

## Running tests

```
bazel test //patcher/...
```
