package types

import (
	"encoding/binary"
	"encoding/json"
	"io"
)

type Int32 struct{}

var _ Scalar = &Int32{}

func (t *Int32) Size() int64 {
	return 4
}

func (t *Int32) ValueAt(r *File, off int64) (Value, error) {
	var result int32
	err := binary.Read(
		io.NewSectionReader(r, off, int64(t.Size())),
		binary.LittleEndian,
		&result,
	)
	if err != nil {
		return nil, err
	}
	return IntValue(result), nil
}

type IntValue int64

func (v IntValue) MarshalJSON() ([]byte, error) {
	return json.Marshal(int64(v))
}
