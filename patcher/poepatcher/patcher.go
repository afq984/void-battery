package main // import "github.com/afq984/void-battery/patcher/poepatcher"

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path"
	"strings"
	"time"
	"unicode/utf8"

	"golang.org/x/text/encoding/unicode"
)

const SaveDir = "Content.ggpk.d"

func check(err error) {
	if err != nil {
		panic(err)
	}
}

var utf16le = unicode.UTF16(unicode.LittleEndian, unicode.IgnoreBOM)

type Patcher struct {
	conn        net.Conn
	rdbuf       *bufio.Reader
	servers     []string
	dirCache    map[string][]DirEntry
	sha256Cache map[string][sha256.Size]byte
}

const (
	File      = 0
	Directory = 1
)

type DirEntry struct {
	Type   byte
	Name   string
	Size   uint32
	Sha256 [sha256.Size]byte
}

func NewPatcher(conn net.Conn) *Patcher {
	p := Patcher{
		conn:        conn,
		rdbuf:       bufio.NewReader(conn),
		dirCache:    make(map[string][]DirEntry),
		sha256Cache: make(map[string][sha256.Size]byte),
	}
	return &p
}

func (p *Patcher) getServers() []string {
	_, err := p.conn.Write([]byte{1, 6})
	check(err)
	_, err = p.rdbuf.Discard(33)
	check(err)
	s0 := readSizedString(p.rdbuf)
	return []string{
		readSizedString(p.rdbuf),
		s0,
	}
}

func (p *Patcher) Servers() []string {
	if p.servers == nil {
		p.servers = p.getServers()
	}
	return p.servers
}

func (p *Patcher) listDir(path string) []DirEntry {
	writeHead := []byte{03, 00, 00}
	binary.BigEndian.PutUint16(writeHead[1:], uint16(utf8.RuneCountInString(path)))
	utf16path, err := utf16le.NewEncoder().String(path)
	check(err)
	_, err = p.conn.Write(append(writeHead, utf16path...))
	check(err)

	_, err = p.rdbuf.Discard(1)
	check(err)

	dirName := readSizedString(p.rdbuf)
	_ = dirName

	var memberLen uint32
	err = binary.Read(p.rdbuf, binary.BigEndian, &memberLen)
	check(err)

	entries := make([]DirEntry, memberLen)

	for i := uint32(0); i < memberLen; i++ {
		e := &entries[i]
		var err error
		e.Type, err = p.rdbuf.ReadByte()
		check(err)
		e.Name = readSizedString(p.rdbuf)
		check(binary.Read(p.rdbuf, binary.BigEndian, &e.Size))
		_, err = io.ReadFull(p.rdbuf, e.Sha256[:])
		check(err)
	}

	return entries
}

func (p *Patcher) ListDir(path string) []DirEntry {
	if _, ok := p.dirCache[path]; !ok {
		p.dirCache[path] = p.listDir(path)
	}
	return p.dirCache[path]
}

// GameVersion returns the game version on the patch server.
func (p *Patcher) GameVersion() string {
	s := p.Servers()
	u, err := url.Parse(s[0])
	check(err)
	return path.Base(u.Path)
}

// MakeLink creates a symbolic link from Content.ggpk.d/latest to the directory of the latest version.
func (p *Patcher) MakeLink() {
	target := p.GameVersion()
	link := path.Join(SaveDir, "latest")
	check(os.MkdirAll(SaveDir, 0777))
	dst, err := os.Readlink(link)
	if err != nil {
		if os.IsNotExist(err) {
			fmt.Printf("# Created symlink %s -> %s\n", link, target)
			os.Symlink(target, link)
		} else {
			panic(err)
		}
	} else {
		if dst != target {
			check(os.Remove(link))
			fmt.Printf("# Removed symlink %s -> %s\n", link, dst)
			check(os.Symlink(target, link))
			fmt.Printf("# Created symlink %s -> %s\n", link, target)
		} else {
			fmt.Printf("# Existing symlink %s -> %s\n", link, target)
		}
	}
}

// ResourceURL returns the URL of resource
func (p *Patcher) ResourceURL(resource string) string {
	return p.Servers()[0] + resource
}

// AltResourceURL returns the alternative URL of resource
func (p *Patcher) AltResourceURL(resource string) string {
	return p.Servers()[1] + resource
}

// DirName returns the directory of the given resource path
func DirName(resource string) string {
	if strings.Contains(resource, "/") {
		return path.Dir(resource)
	}
	return ""
}

// Sha256 returns the sha256 checksum of the given resource.
func (p *Patcher) Sha256(resource string) [sha256.Size]byte {
	if sum, ok := p.sha256Cache[resource]; ok {
		return sum
	}
	base := path.Base(resource)
	for _, entry := range p.ListDir(DirName(resource)) {
		if entry.Name == base {
			p.sha256Cache[resource] = entry.Sha256
			return entry.Sha256
		}
	}
	panic(fmt.Errorf("No such resource at remote: %q", resource))
}

// SyncPath returns the synchronized path of Patcher.Sync(resource).
func (p *Patcher) SyncPath(resource string) string {
	return path.Join(SaveDir, p.GameVersion(), resource)
}

// Sync synchronizes the resource of the given path.
func (p *Patcher) Sync(resource string) {
	resourceURL := p.ResourceURL(resource)
	syncPath := p.SyncPath(resource)

	localSha256 := sha256File(syncPath)
	remoteSha256 := p.Sha256(resource)
	if bytes.Equal(localSha256, remoteSha256[:]) {
		fmt.Printf("Sha256 matched: %s\n", resource)
		return
	}

	check(os.MkdirAll(path.Dir(syncPath), 0777))

	file, err := os.Create(syncPath)
	check(err)
	defer file.Close()

	resp, err := http.Get(resourceURL)
	check(err)
	defer resp.Body.Close()

	n, err := io.Copy(file, resp.Body)
	if err != nil {
		panic(err)
	}

	fmt.Printf("Downloaded %d bytes: %s\n", n, resource)
}

// SyncRecursive synchronizes the directory recursively.
func (p *Patcher) SyncRecursive(dir string) {
	for _, sub := range p.ListDir(dir) {
		var subpath string
		if dir == "" {
			subpath = sub.Name
		} else {
			subpath = dir + "/" + sub.Name
		}
		if sub.Type == Directory {
			if subpath == "Art" {
				continue
			}
			p.SyncRecursive(subpath)
		} else {
			p.Sync(subpath)
		}
	}
}

func (p *Patcher) AriaRecursive(dir string) {
	for _, sub := range p.ListDir(dir) {
		var subpath string
		if dir == "" {
			subpath = sub.Name
		} else {
			subpath = dir + "/" + sub.Name
		}
		if sub.Type == Directory {
			p.AriaRecursive(subpath)
		} else {
			resourceURL := p.ResourceURL(subpath)
			syncPath := p.SyncPath(subpath)
			remoteSha256 := p.Sha256(subpath)
			fmt.Printf("%v\t%v\n\tout=%v\n\tchecksum=sha-256=%x\n",
				resourceURL, p.AltResourceURL(subpath), syncPath, remoteSha256)
		}
	}
}

// sha256File returns the sha256 checksum of the file at the given path.
// if the file does not exist, nil is returned
func sha256File(path string) []byte {
	f, err := os.Open(path)
	if os.IsNotExist(err) {
		return nil
	}
	check(err)
	defer f.Close()

	h := sha256.New()
	_, err = io.Copy(h, f)
	check(err)

	return h.Sum(nil)
}

func readSizedString(r *bufio.Reader) string {
	lenU16, err := r.Peek(2)
	check(err)
	stringSize := int(binary.BigEndian.Uint16(lenU16)) * 2
	_, err = r.Discard(2)
	check(err)
	utf16b := make([]byte, stringSize)
	_, err = io.ReadFull(r, utf16b)
	check(err)
	utf8s, err := utf16le.NewDecoder().String(string(utf16b))
	check(err)
	return utf8s
}

func main() {
	conn, err := net.DialTimeout("tcp4", "login.tw.pathofexile.com:12999", time.Second)
	// conn, err := net.DialTimeout("tcp", "pathofexile.com:12995", time.Second)
	check(err)
	p := NewPatcher(conn)
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
