package types

type Type interface {
	ValueAt(r *File, off int64) (Value, error)
}

type Scalar interface {
	Type
	Size() int64
}
