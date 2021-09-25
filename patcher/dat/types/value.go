package types

import "encoding/json"

type Value interface {
	json.Marshaler
}
