package types

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"math"

	"golang.org/x/text/encoding/unicode"
)

type UTF16LEString struct{}

var _ Type = &UTF16LEString{}

var utf16leenc = unicode.UTF16(unicode.LittleEndian, unicode.IgnoreBOM)

func (t *UTF16LEString) ValueAt(r *File, off int64) (Value, error) {
	sr := io.NewSectionReader(r, off, math.MaxInt64-off)
	var count int64
	for ; ; count += 2 {
		var c uint16
		err := binary.Read(sr, binary.LittleEndian, &c)
		if err != nil {
			return nil, fmt.Errorf("looking for end of string: %v", err)
		}
		if c == 0 {
			break
		}
	}

	b, err := io.ReadAll(utf16leenc.NewDecoder().Reader(io.NewSectionReader(r, off, count)))
	if err != nil {
		return nil, fmt.Errorf("decode UTF16LE: %v", err)
	}

	return StringValue(b), nil
}

type StringValue string

var _ Value = StringValue("")

func (v StringValue) MarshalJSON() ([]byte, error) {
	return json.Marshal(string(v))
}
