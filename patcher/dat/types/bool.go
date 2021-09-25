package types

import "encoding/json"

type Bool struct{}

var _ Scalar = &Bool{}

func (t *Bool) Size() int64 {
	return 1
}

func (t *Bool) ValueAt(r *File, off int64) (Value, error) {
	var buf [1]byte
	n, err := r.ReadAt(buf[:], off)
	if n != 1 {
		return nil, err
	}
	return BoolValue(buf[0] != 0), nil
}

type BoolValue bool

var _ Value = BoolValue(false)

func (v BoolValue) MarshalJSON() ([]byte, error) {
	return json.Marshal(bool(v))
}
