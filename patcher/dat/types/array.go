package types

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
)

type Array struct {
	T Scalar
}

var _ Scalar = &Array{}

func (t *Array) Size() int64 {
	return 16
}

func (t *Array) ValueAt(r *File, off int64) (Value, error) {
	var arrayHeader struct {
		Count  int64
		Offset int64
	}
	err := binary.Read(
		io.NewSectionReader(r, off, t.Size()),
		binary.LittleEndian,
		&arrayHeader,
	)
	if err != nil {
		return nil, err
	}

	result := make(ArrayValue, arrayHeader.Count)
	elementOffset := r.DynamicBase + int64(arrayHeader.Offset)
	for i := 0; i < int(arrayHeader.Count); i++ {
		result[i], err = t.T.ValueAt(r, elementOffset)
		if err != nil {
			return nil, fmt.Errorf("read array[%d] failed: %v", i, err)
		}
		elementOffset += t.T.Size()
	}
	return &result, nil
}

type ArrayValue []Value

var _ Value = &ArrayValue{}

func (v *ArrayValue) MarshalJSON() ([]byte, error) {
	return json.Marshal([]Value(*v))
}
