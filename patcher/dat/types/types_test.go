package types

import (
	"bytes"
	"testing"

	"github.com/google/go-cmp/cmp"
)

func buildFile(fixed, dynamic []byte) *File {
	return &File{
		ReaderAt:    bytes.NewReader(append(fixed, dynamic...)),
		DynamicBase: int64(len(fixed)),
	}
}

func TestValueAt(t *testing.T) {
	cases := []struct {
		ty      Type
		fixed   []byte
		dynamic []byte
		offset  int64
		output  interface{}
	}{
		{
			ty:     &Int32{},
			fixed:  []byte{0xff, 0xff, 0xff, 0xff},
			output: IntValue(-1),
		},
		{
			ty:     &Int32{},
			fixed:  []byte{0, 0, 0, 0},
			output: IntValue(0),
		},
		{
			ty:     &Int32{},
			fixed:  []byte{0, 0xff, 0xff, 0xff},
			output: IntValue(-256),
		},
		{
			ty:     &Int32{},
			fixed:  []byte{0xff, 0, 0, 0},
			output: IntValue(255),
		},
		{
			ty:     &Int32{},
			fixed:  []byte{1, 2, 3, 4},
			output: IntValue(0x4030201),
		},

		{
			ty:     &UInt16{},
			fixed:  []byte{0xff, 0xff},
			output: IntValue(0xffff),
		},
		{
			ty:     &UInt16{},
			fixed:  []byte{0, 0},
			output: IntValue(0),
		},
		{
			ty:     &UInt16{},
			fixed:  []byte{0xff, 0},
			output: IntValue(255),
		},
		{
			ty:     &UInt16{},
			fixed:  []byte{1, 2},
			output: IntValue(0x201),
		},

		{
			ty:     &UInt32{},
			fixed:  []byte{0xff, 0xff, 0xff, 0xff},
			output: IntValue(0xffffffff),
		},
		{
			ty:     &UInt32{},
			fixed:  []byte{0, 0, 0, 0},
			output: IntValue(0),
		},
		{
			ty:     &UInt32{},
			fixed:  []byte{0xff, 0, 0, 0},
			output: IntValue(255),
		},
		{
			ty:     &UInt32{},
			fixed:  []byte{1, 2, 3, 4},
			output: IntValue(0x4030201),
		},

		{
			ty:     &Bool{},
			fixed:  []byte{0},
			output: BoolValue(false),
		},
		{
			ty:     &Bool{},
			fixed:  []byte{1},
			output: BoolValue(true),
		},
		{
			ty:     &Bool{},
			fixed:  []byte{255},
			output: BoolValue(true),
		},

		{
			ty: &Pointer{&Int32{}},
			fixed: []byte{
				// ptr to 6
				6, 0, 0, 0, 0, 0, 0, 0,
			},
			dynamic: []byte{
				// padding
				0, 0, 0, 0, 0, 0,
				// value
				4, 3, 2, 1,
			},
			output: IntValue(0x1020304),
		},

		{
			ty: &Array{&Int32{}},
			fixed: []byte{
				// offset
				2, 0, 0, 0, 0, 0, 0, 0,
				// count
				2, 0, 0, 0, 0, 0, 0, 0,
			},
			dynamic: []byte{
				// arbitary padding
				0, 0,
				// a[0]
				1, 2, 3, 4,
				// a[1]
				5, 6, 7, 8,
			},
			output: &ArrayValue{
				IntValue(0x4030201),
				IntValue(0x8070605),
			},
		},

		{
			ty:    &Pointer{T: &UTF16LEString{}},
			fixed: []byte{0, 0, 0, 0, 0, 0, 0, 0},
			dynamic: []byte{
				'a', 0,
				'b', 0,
				'c', 0,
				0, 0,
			},
			output: StringValue("abc"),
		},
	}

	for _, c := range cases {
		t.Run("", func(t *testing.T) {
			r := buildFile(c.fixed, c.dynamic)
			val, err := c.ty.ValueAt(r, c.offset)
			if err != nil {
				t.Fatalf("unexpected error calling ValueAt:\nerr: %v\nc.ty: %v\nc.input: %v", err, c.ty, r)
			}
			if diff := cmp.Diff(c.output, val); diff != "" {
				t.Errorf("ty: %v\ninput: %v\ndiff (-want; +got)\n%s", c.ty, r, diff)
			}
		})
	}
}
