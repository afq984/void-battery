package types

import "io"

type File struct {
	io.ReaderAt
	// Number of rows
	RowSize int64
	// The base offset of the free-form section
	DynamicBase int64
}
