package main

// Backfilled media download.
//
// handleMessage downloads media as it arrives live. handleHistorySync did not:
// it stored the row (URL, media key, hashes) but never fetched the bytes, so any
// message that reached us through a backfill instead of a live event left no file
// on disk. WhatsApp's CDN links expire after roughly two weeks, so those images
// were quietly lost once the window closed.
//
// This downloads history-synced media too. A history sync can carry thousands of
// messages at once, so unlike the live path — which fires one goroutine per
// message at human message rates — downloads here run through a bounded worker
// pool. Failures are logged and skipped: an expired link is expected for old
// history and must not stall the rest of the sync.

import (
	"go.mau.fi/whatsmeow"
	waLog "go.mau.fi/whatsmeow/util/log"
)

// historyDownloadConcurrency caps simultaneous backfill downloads. Chosen to
// keep a large sync from saturating the uplink or opening thousands of sockets,
// while still clearing a chunk faster than serial fetching would.
const historyDownloadConcurrency = 4

// historyDownloadSem is package-level so that overlapping history sync events
// share one budget rather than each opening its own pool.
var historyDownloadSem = make(chan struct{}, historyDownloadConcurrency)

// queueHistoryMediaDownload fetches media for a history-synced message in the
// background. It returns immediately; the caller keeps processing the sync.
//
// The row must already be stored: downloadMedia reads the URL and media key back
// out of the database by (messageID, chatJID).
func queueHistoryMediaDownload(
	client *whatsmeow.Client,
	messageStore *MessageStore,
	messageID, chatJID, mediaType string,
	logger waLog.Logger,
) {
	if messageID == "" || mediaType == "" || mediaType == "reaction" {
		return
	}

	go func() {
		historyDownloadSem <- struct{}{}
		defer func() { <-historyDownloadSem }()

		success, _, _, path, err := downloadMedia(client, messageStore, messageID, chatJID)
		if success && err == nil {
			logger.Infof("✅ Backfilled %s media: %s", mediaType, path)
			return
		}
		// Expired CDN links are the normal outcome for older history. Log at
		// debug so a large first sync does not flood the warning stream.
		logger.Debugf("Backfill download skipped for %s (%s): %v", messageID, mediaType, err)
	}()
}
