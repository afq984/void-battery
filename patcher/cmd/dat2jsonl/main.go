package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/spf13/pflag"

	_ "github.com/afq984/void-battery/patcher/cmd"
	"github.com/afq984/void-battery/patcher/dat"
	"github.com/afq984/void-battery/patcher/dat/schema"
	"github.com/afq984/void-battery/patcher/dat/types"
)

var schemaFile string
var datFile string
var tableName string

func getTableName(path string) string {
	base := filepath.Base(path)
	return base[:len(base)-len(filepath.Ext(base))]
}

func main() {
	pflag.StringVar(&schemaFile, "schema", "", "")
	pflag.StringVar(&tableName, "table-name", "",
		`the name of the table as defined in the schema.
defaults to the name of the dat file`)
	pflag.StringVar(&datFile, "dat", "", "")
	pflag.Parse()

	b, err := os.ReadFile(schemaFile)
	if err != nil {
		log.Fatal(err)
	}
	defs, err := schema.Parse(b)
	if err != nil {
		log.Fatal(err)
	}

	if tableName == "" {
		tableName = getTableName(datFile)
	}
	def, ok := defs[tableName]
	if !ok {
		log.Fatalf("table name not found: %q", tableName)
	}

	f, err := os.Open(datFile)
	if err != nil {
		log.Fatal(err)
	}
	defer f.Close()

	rowType := &types.Struct{Fields: def.Fields}
	d, err := dat.Parse(f, rowType)
	if err != nil {
		log.Fatalf("error parsing %s: %v", datFile, err)
	}

	for i := int64(0); i < d.RowCount; i++ {
		k, err := rowType.ValueAt(d.File, d.RowOffset(i))
		if err != nil {
			log.Fatal(err)
		}
		j, err := k.MarshalJSON()
		if err != nil {
			log.Fatal(err)
		}
		fmt.Println(string(j))
	}
}
