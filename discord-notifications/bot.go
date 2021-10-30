package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

const apiBaseURL = "https://discord.com/api/v9"

type bot struct {
	// token from discord.com/developers/applications/<appid>/bot
	token string
	// discord.com/channels/<guild_id>/<channel_id>
	channelID string
}

// https://discord.com/developers/docs/resources/channel#create-message
func (b *bot) createMessage(opts *createMessageOpts) error {
	reqBody, err := json.Marshal(opts)
	if err != nil {
		return fmt.Errorf("failed to encode to json: %w", err)
	}
	req, err := http.NewRequest(
		http.MethodPost,
		fmt.Sprintf("%s/channels/%s/messages", apiBaseURL, b.channelID),
		bytes.NewReader(reqBody),
	)
	if err != nil {
		panic(err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bot "+b.token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("bad status code %d; body: %s", resp.StatusCode, string(respBody))
	}
	return nil
}

type createMessageOpts struct {
	Content string  `json:"content"`
	Embeds  []embed `json:"embeds"`
}

type embed struct {
	Title       string  `json:"title"`
	Description string  `json:"description"`
	Fields      []field `json:"fields"`
}

type field struct {
	Name   string `json:"name"`
	Value  string `json:"value"`
	Inline bool   `json:"inline"`
}
