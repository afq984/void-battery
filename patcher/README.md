# Patcher

This directory contains tools to update the game data.

### Build tools

First have these dependencies installed:

* bash
* python3
* go
* curl
* gcc
* ninja

Then run:

```
./install.sh
```

### Download the game files and extract them

```
./main.sh
```

### Compare the current extracted data with the ones in `../web`:

```
./diff.sh
```

### Copy the extracted data to `../web`:

```
./release.sh
```
