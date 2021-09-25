package types

type Pad struct {
	Bytes int64
}

var _ Scalar = &Pad{}

func (t *Pad) Size() int64 {
	return t.Bytes
}

func (t *Pad) ValueAt(r *File, off int64) (Value, error) {
	return NullValue{}, nil
}

type NullValue struct{}

var _ Value = NullValue{}

func (v NullValue) MarshalJSON() ([]byte, error) {
	return []byte("null"), nil
}
