package types

import "encoding/json"

type StructField struct {
	Name string
	T    Scalar
}

type Struct struct {
	Fields []*StructField
}

var _ Scalar = &Struct{}

func (t *Struct) Size() (size int64) {
	for _, f := range t.Fields {
		size += f.T.Size()
	}
	return
}

func (t *Struct) ValueAt(r *File, off int64) (Value, error) {
	v := make(StructValue)
	for _, f := range t.Fields {
		var err error
		v[f.Name], err = f.T.ValueAt(r, off)
		if err != nil {
			return nil, err
		}
		off += f.T.Size()
	}
	return v, nil
}

type StructValue map[string]Value

func (v StructValue) MarshalJSON() ([]byte, error) {
	return json.Marshal(map[string]Value(v))
}
