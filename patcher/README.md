# Patcher

This directory contains tools to update the game data.

Dependency:

* sh or bash
* python3
* go

Install tools:

```
sh install.sh
```

Download the game files and extract them:

```
sh main.sh
```

Compare the current extracted data with the ones in `../web`:

```
sh diff.sh
```

Copy the extracted data to `../web`:

```
sh release.sh
```
