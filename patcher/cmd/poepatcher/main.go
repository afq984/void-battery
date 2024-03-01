package main

import (
	"fmt"
	"net"
	"os"
	"strings"
	"time"

	_ "github.com/afq984/void-battery/patcher/cmd"
	"github.com/afq984/void-battery/patcher/poepatcher"
)

const TWPatchServer = "patch.pathofexile.tw:12999"
const GGGPatchServer = "pathofexile.com:12995"

func check(err error) {
	if err != nil {
		panic(err)
	}
}

func main() {
	conn, err := net.DialTimeout("tcp", TWPatchServer, time.Second)
	check(err)
	p := poepatcher.NewPatcher6(conn)
	fmt.Println("# Game version is", p.GameVersion())
	for _, path := range os.Args[1:] {
		if strings.HasSuffix(path, "/") {
			p.SyncRecursive(strings.TrimSuffix(path, "/"))
		} else {
			p.Sync(path)
		}
	}
	p.MakeLink()
}
