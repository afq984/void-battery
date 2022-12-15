package types

import (
	"encoding/binary"
	"io"
)

type Pointer struct {
	T Type
}

var _ Scalar = &Pointer{}

func (t *Pointer) Size() int64 {
	return 8
}

func (t *Pointer) ValueAt(r *File, off int64) (Value, error) {
	var ptr int64
	err := binary.Read(
		io.NewSectionReader(r, off, t.Size()),
		binary.LittleEndian,
		&ptr,
	)
	if err != nil {
		return nil, err
	}
	return t.T.ValueAt(r, int64(ptr)+r.DynamicBase)
}
