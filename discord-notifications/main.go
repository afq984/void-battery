package main

// Discord notifier based on
// https://cloud.google.com/build/docs/configuring-notifications/create-notifier

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/GoogleCloudPlatform/cloud-build-notifiers/lib/notifiers"
	cbpb "google.golang.org/genproto/googleapis/devtools/cloudbuild/v1"
)

func main() {
	h := &logger{
		discordBot: bot{
			token:     mustGetEnv("DISCORD_BOT_TOKEN"),
			channelID: mustGetEnv("DISCORD_CHANNEL_ID"),
		},
	}
	if err := notifiers.Main(h); err != nil {
		log.Fatalf("fatal error: %v", err)
	}
}

func mustGetEnv(key string) string {
	val, ok := os.LookupEnv(key)
	if !ok {
		log.Fatalf("environment variable not set: %q", key)
	}
	return val
}

type application struct {
	Application string
	Commit      string
	Compatible  string
}

func liveVersion() *application {
	app := &application{
		Application: "<unknown>",
		Commit:      "<unknown>",
		Compatible:  "<unknown>",
	}
	resp, err := http.Get("https://void-battery.afq984.org/version.json")
	if err != nil {
		log.Printf("failed to get /version.json: %v", err)
		return app
	}
	if resp.StatusCode != http.StatusOK {
		log.Printf("bad status code from /version.json: %d", resp.StatusCode)
		return app
	}
	err = json.NewDecoder(resp.Body).Decode(app)
	if err != nil {
		log.Printf("failed to parse /version.json: %v", err)
		return app
	}
	return app
}

type logger struct {
	discordBot bot
}

func (h *logger) SetUp(ctx context.Context, _ *notifiers.Config, _ notifiers.SecretGetter, _ notifiers.BindingResolver) error {
	return nil
}

func (h *logger) SendNotification(ctx context.Context, build *cbpb.Build) error {
	switch build.Status {
	case cbpb.Build_STATUS_UNKNOWN, cbpb.Build_PENDING, cbpb.Build_QUEUED, cbpb.Build_WORKING:
		return nil
	}
	b := h.discordBot

	var content string
	if build.Status != cbpb.Build_SUCCESS {
		// mention myself if the build failed
		content = "<@581544983413260308>"
	}

	embeds := []embed{
		{
			Title:       fmt.Sprintf("Build %s", build.Status),
			Description: fmt.Sprintf("Build ID: [%s](%s)", build.Id[:8], build.LogUrl),
		},
	}
	if build.Status == cbpb.Build_SUCCESS {
		app := liveVersion()
		commit := app.Commit
		if commit != "<unknown>" {
			commit = fmt.Sprintf(
				"[%s](https://github.com/afq984/void-battery/commit/%s)",
				commit[:8], commit)
		}
		embeds[0].Fields = []field{
			{Name: "application", Value: app.Application, Inline: true},
			{Name: "commit", Value: commit, Inline: true},
			{Name: "compatible", Value: app.Compatible, Inline: true},
		}
	}

	return b.createMessage(&createMessageOpts{
		Content: content,
		Embeds:  embeds,
	})
}
