package dat

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"io"

	"github.com/afq984/void-battery/patcher/dat/types"
)

type Dat struct {
	RowCount int64
	*types.File
}

func (d *Dat) RowOffset(i int64) int64 {
	if i >= d.RowCount {
		panic(fmt.Errorf("row index out of bounds: %d >= %d", i, d.RowCount))
	}
	return 4 + d.RowSize*i
}

func Parse(r io.ReaderAt, rowType *types.Struct) (*Dat, error) {
	var rowCount32 int32
	err := binary.Read(
		io.NewSectionReader(r, 0, 4),
		binary.LittleEndian,
		&rowCount32,
	)
	if err != nil {
		return nil, fmt.Errorf("cannot determine row count: %v", err)
	}
	rowCount := int64(rowCount32)

	rowSize, err := guessRowSize(r, rowCount)
	if err != nil {
		return nil, err
	}

	return &Dat{
		RowCount: rowCount,
		File: &types.File{
			ReaderAt:    r,
			RowSize:     rowSize,
			DynamicBase: 4 + rowCount*rowSize,
		},
	}, nil
}

func guessRowSize(r io.ReaderAt, rowCount int64) (int64, error) {
	for rowSize := int64(0); ; rowSize++ {
		var buf [8]byte
		n, err := r.ReadAt(buf[:], 4+rowSize*rowCount)
		if n != 8 {
			if err == io.EOF {
				return 0, errors.New("cannot guess row size, separator not found")
			}
			return 0, fmt.Errorf("ReadAt failed when guessing row size: %v", err)
		}
		if bytes.Equal(buf[:], []byte("\xbb\xbb\xbb\xbb\xbb\xbb\xbb\xbb")) {
			return rowSize, nil
		}
	}
}
