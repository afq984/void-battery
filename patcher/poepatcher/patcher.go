package poepatcher

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
	"unicode/utf8"

	"github.com/pierrec/lz4/v4"
	"golang.org/x/text/encoding/unicode"
)

const SaveDir = "Content.ggpk.d"

func check(err error) {
	if err != nil {
		panic(err)
	}
}

func checkN(n int, err error) {
	if err != nil {
		panic(err)
	}
}

var utf16le = unicode.UTF16(unicode.LittleEndian, unicode.IgnoreBOM)

func readBE16SizedString(r io.Reader) string {
	lenRaw := make([]byte, 2)
	checkN(io.ReadFull(r, lenRaw))
	stringSize := int(binary.BigEndian.Uint16(lenRaw)) * 2
	utf16b := make([]byte, stringSize)
	checkN(io.ReadFull(r, utf16b))
	utf8s, err := utf16le.NewDecoder().String(string(utf16b))
	check(err)
	return utf8s
}

func writeBE16SizedString(w io.Writer, s string) {
	check(binary.Write(w, binary.BigEndian, uint16(utf8.RuneCountInString(s))))
	utf16s, err := utf16le.NewEncoder().String(s)
	check(err)
	checkN(w.Write([]byte(utf16s)))
}

func readLE32SizedString(r io.Reader) string {
	lenRaw := make([]byte, 4)
	checkN(io.ReadFull(r, lenRaw))
	stringSize := int(binary.LittleEndian.Uint32(lenRaw)) * 2
	utf16b := make([]byte, stringSize)
	checkN(io.ReadFull(r, utf16b))
	utf8s, err := utf16le.NewDecoder().String(string(utf16b))
	check(err)
	return utf8s
}

type Patcher6DirHeader struct {
	Unknown          byte
	CompressedSize1  uint32
	DecompressedSize uint32
	CompressedSize2  uint32
}

type Patcher6FileHeader struct {
	Type byte
	Size uint32
}

type Patcher6 struct {
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
	Patcher6FileHeader
	Name   string
	Sha256 [sha256.Size]byte
}

func NewPatcher6(conn net.Conn) *Patcher6 {
	p := Patcher6{
		conn:        conn,
		rdbuf:       bufio.NewReader(conn),
		dirCache:    make(map[string][]DirEntry),
		sha256Cache: make(map[string][sha256.Size]byte),
	}
	p.servers = p.getServers()
	return &p
}

func (p *Patcher6) getServers() []string {
	_, err := p.conn.Write([]byte{1, 6})
	check(err)
	_, err = p.rdbuf.Discard(33)
	check(err)
	s0 := readBE16SizedString(p.rdbuf)
	return []string{
		readBE16SizedString(p.rdbuf),
		s0,
	}
}

func (p *Patcher6) Servers() []string {
	return p.servers
}

func (p *Patcher6) listDir(path string) []DirEntry {
	checkN(p.conn.Write([]byte{3}))
	writeBE16SizedString(p.conn, path)

	var dirHeader Patcher6DirHeader
	check(binary.Read(p.rdbuf, binary.BigEndian, &dirHeader))

	if dirHeader.CompressedSize1 > 16777216 {
		panic(fmt.Errorf("compressed size too large: %d", dirHeader.CompressedSize1))
	}
	if dirHeader.DecompressedSize > 16777216 {
		panic(fmt.Errorf("decompressed size too large: %d", dirHeader.DecompressedSize))
	}
	compressed := make([]byte, dirHeader.CompressedSize1)
	uncompressed := make([]byte, dirHeader.DecompressedSize)
	checkN(io.ReadFull(p.rdbuf, compressed))
	checkN(lz4.UncompressBlock(compressed, uncompressed))
	r := bytes.NewBuffer(uncompressed)

	dirName := readLE32SizedString(r)
	_ = dirName

	var memberLen uint32
	check(binary.Read(r, binary.LittleEndian, &memberLen))

	entries := make([]DirEntry, memberLen)

	for i := uint32(0); i < memberLen; i++ {
		e := &entries[i]
		check(binary.Read(r, binary.LittleEndian, &e.Patcher6FileHeader))
		e.Name = readLE32SizedString(r)
		checkN(io.ReadFull(r, e.Sha256[:]))
	}

	return entries
}

func (p *Patcher6) ListDir(path string) []DirEntry {
	if _, ok := p.dirCache[path]; !ok {
		p.dirCache[path] = p.listDir(path)
	}
	return p.dirCache[path]
}

// GameVersion returns the game version on the patch server.
func (p *Patcher6) GameVersion() string {
	s := p.Servers()
	u, err := url.Parse(s[0])
	check(err)
	return path.Base(u.Path)
}

// MakeLink creates a symbolic link from Content.ggpk.d/latest to the directory of the latest version.
func (p *Patcher6) MakeLink() {
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
func (p *Patcher6) ResourceURL(resource string) string {
	return p.Servers()[0] + resource
}

// AltResourceURL returns the alternative URL of resource
func (p *Patcher6) AltResourceURL(resource string) string {
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
func (p *Patcher6) Sha256(resource string) [sha256.Size]byte {
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
func (p *Patcher6) SyncPath(resource string) string {
	return path.Join(SaveDir, p.GameVersion(), resource)
}

// Sync synchronizes the resource of the given path.
func (p *Patcher6) Sync(resource string) {
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
func (p *Patcher6) SyncRecursive(dir string) {
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

func (p *Patcher6) AriaRecursive(dir string) {
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
