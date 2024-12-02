package schema

// Package schema parses DAT schema defined in:
// https://github.com/poe-tool-dev/dat-schema/releases

import (
	"encoding/json"
	"fmt"

	"github.com/afq984/void-battery/patcher/dat/types"
)

type schema struct {
	Version   int
	CreatedAt int
	Tables    []table
}

type table struct {
	Name    string
	Columns []column
}

type column struct {
	Name  string
	Array bool
	Type  string
}

func (c *column) asStructField() (*types.StructField, error) {
	var t types.Scalar
	switch c.Type {
	case "bool":
		t = &types.Bool{}
	case "i16":
		t = &types.Int16{}
	case "i32":
		t = &types.Int32{}
	case "f32":
		t = &types.Pad{Bytes: 4}
	case "foreignrow":
		t = &types.Pad{Bytes: 16}
	case "enumrow":
		t = &types.Pad{Bytes: 4}
	case "string":
		t = &types.Pointer{T: &types.UTF16LEString{}}
	case "row":
		t = &types.Pad{Bytes: 8}
	case "array":
		t = &types.Pad{Bytes: (&types.Array{}).Size()}
	default:
		return nil, fmt.Errorf("unknown type: %q", c.Type)
	}
	if c.Array {
		t = &types.Array{T: t}
	}
	return &types.StructField{
		Name: c.Name,
		T:    t,
	}, nil
}

func Parse(data []byte) (map[string]*types.Struct, error) {
	var sch schema
	err := json.Unmarshal(data, &sch)
	if err != nil {
		return nil, err
	}

	m := make(map[string]*types.Struct)
	for _, table := range sch.Tables {
		st := &types.Struct{}
		for _, column := range table.Columns {
			sf, err := column.asStructField()
			if err != nil {
				return nil, err
			}
			st.Fields = append(st.Fields, sf)
		}

		m[table.Name] = st
	}

	return m, nil
}
