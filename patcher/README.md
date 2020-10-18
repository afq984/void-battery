# Patcher

This directory contains tools to update the game data.

### Install tools

* bash
* python3
* go
* cmake

```
./install.sh
```

#### or use Docker

```
./launch-docker
```

### Download the game files and extract them

```
./main.sh
```

#### or use Docker

```
# in the container
./main.sh

# out of the container
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
