package main

import (
	"io"
	"log"
	"os"

	"github.com/oriath-net/pogo/poefs"
	"github.com/spf13/pflag"
)

var ggpkDir string
var path string
var out string

func main() {
	pflag.StringVar(&ggpkDir, "ggpkd", "", "GGPK directory")
	pflag.StringVar(&path, "path", "", "path within GGPK")
	pflag.StringVar(&out, "out", "", "output path")
	pflag.Parse()

	fs, err := poefs.Open(ggpkDir)
	if err != nil {
		log.Fatal(err)
	}

	r, err := fs.Open(path)
	if err != nil {
		log.Fatal(err)
	}

	w, err := os.Create(out)
	if err != nil {
		log.Fatal(err)
	}

	// https://github.com/oriath-net/pogo/blob/main/cmd/cat.go#L44
	n, err := io.CopyBuffer(w, r, make([]byte, 262144))
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("copied %d bytes to %s", n, out)
}
