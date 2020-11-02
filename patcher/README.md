# Patcher

This directory contains tools to update the game data.

### Install tools

Have these dependencies installed:

* bash
* python3
* go
* cmake

Then run:

```
./install.sh
```

#### or use Docker

```
./build-docker.sh
```

### Download the game files and extract them

```
./main.sh
```

#### or use Docker

```
./launch-docker ./main.sh
```

### Compare the current extracted data with the ones in `../web`:

```
./diff.sh
```

### Copy the extracted data to `../web`:

```
./release.sh
```
