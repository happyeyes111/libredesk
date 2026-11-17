// Live View (Phase 3, Chatwoot-style visitor monitoring, rebuilt in Libredesk's idiom).
//
// The widget already sends a heartbeat (`ping` every 10s, which updates the
// visitor's last_active_at) and `page_visit` events (stored in Redis and
// broadcast to agents as contact updates). What was missing was a single
// place for agents to see *who is on the site right now*. This file keeps
// that state in memory only — no DB migration, no geo lookup in v1:
//
//   - a visitor is registered when its widget WS connection joins an inbox,
//   - its current page is updated on every `page_visit`,
//   - its last-seen time is refreshed on every `ping`,
//   - entries with no heartbeat for 60s are pruned (a closed tab disappears
//     from Live View within about a minute).
//
// GET /api/v1/live-view (agent permission `conversations:read`) returns the
// currently-online visitors, newest first, each with the inbox/site, the page
// it is on, seconds on site, and the UUID of its latest open conversation
// (if any) so the agent can jump straight into the chat.
//
// Limitation (documented): the registry is per-process and in-memory, so it
// does not survive a server restart, and a visitor with two tabs open counts
// once per connection — the connection counter below keeps the entry alive
// while at least one tab is connected.

package main

import (
	"database/sql"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/zerodha/fastglue"
)

// liveViewStaleAfter is how long a visitor may go without a widget heartbeat
// before it is treated as gone. The widget pings every 10s and the WS read
// deadline is 20s, so 60s leaves room for a missed beat.
const liveViewStaleAfter = 60 * time.Second

// liveVisitor is one currently-online website visitor.
type liveVisitor struct {
	ContactID        int       `json:"contact_id"`
	Name             string    `json:"name"`
	Email            string    `json:"email"`
	InboxID          int       `json:"inbox_id"`
	InboxUUID        string    `json:"inbox_uuid"`
	InboxName        string    `json:"inbox_name"`
	URL              string    `json:"url"`
	Title            string    `json:"title"`
	FirstSeen        time.Time `json:"first_seen"`
	LastSeen         time.Time `json:"last_seen"`
	SecondsOnSite    int64     `json:"seconds_on_site"`
	ConversationUUID string    `json:"conversation_uuid,omitempty"`

	connections int
}

var (
	liveViewMu       sync.RWMutex
	liveViewVisitors = map[int]*liveVisitor{}
)

// liveViewDisplayName builds the name shown for a visitor from the contact
// record. Visitors that never gave a name fall back to their email, then to
// a plain "Visitor #id" label.
func liveViewDisplayName(firstName, lastName, email string, contactID int) string {
	name := strings.TrimSpace(strings.TrimSpace(firstName) + " " + strings.TrimSpace(lastName))
	if name != "" {
		return name
	}
	if email != "" {
		return email
	}
	return "Visitor #" + itoa(contactID)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}

// liveViewTrackJoin registers (or refreshes) a visitor when its widget
// connection joins an inbox. The contact name/email and inbox name are
// loaded once here so the list handler stays cheap.
func liveViewTrackJoin(app *App, userID int, inboxUUID string, inboxID int, inboxName string) {
	if userID == 0 || inboxUUID == "" {
		return
	}
	name, email := "", ""
	if user, err := app.user.Get(userID, "", []string{}); err == nil {
		name = liveViewDisplayName(user.FirstName, user.LastName, user.Email.String, userID)
		email = user.Email.String
	}
	if name == "" {
		name = liveViewDisplayName("", "", email, userID)
	}
	now := time.Now()
	liveViewMu.Lock()
	defer liveViewMu.Unlock()
	if v, ok := liveViewVisitors[userID]; ok {
		v.connections++
		v.LastSeen = now
		v.InboxUUID = inboxUUID
		v.InboxID = inboxID
		v.InboxName = inboxName
		v.Name = name
		v.Email = email
		return
	}
	liveViewVisitors[userID] = &liveVisitor{
		ContactID:   userID,
		Name:        name,
		Email:       email,
		InboxID:     inboxID,
		InboxUUID:   inboxUUID,
		InboxName:   inboxName,
		FirstSeen:   now,
		LastSeen:    now,
		connections: 1,
	}
}

// liveViewTrackPage updates a visitor's current page after a page_visit
// event. Unknown visitors (e.g. a connection that joined before a restart)
// are registered on the spot from the page event alone.
func liveViewTrackPage(userID int, url, title string) {
	if userID == 0 || url == "" {
		return
	}
	now := time.Now()
	liveViewMu.Lock()
	defer liveViewMu.Unlock()
	v, ok := liveViewVisitors[userID]
	if !ok {
		liveViewVisitors[userID] = &liveVisitor{
			ContactID:   userID,
			Name:        liveViewDisplayName("", "", "", userID),
			URL:         url,
			Title:       title,
			FirstSeen:   now,
			LastSeen:    now,
			connections: 1,
		}
		return
	}
	v.URL = url
	v.Title = title
	v.LastSeen = now
}

// liveViewTrackPing refreshes a visitor's last-seen time on a widget
// heartbeat. A missing entry is ignored — the next page_visit re-registers it.
func liveViewTrackPing(userID int) {
	if userID == 0 {
		return
	}
	liveViewMu.Lock()
	defer liveViewMu.Unlock()
	if v, ok := liveViewVisitors[userID]; ok {
		v.LastSeen = time.Now()
	}
}

// liveViewTrackLeave drops one connection for a visitor; the entry is removed
// only when its last connection closes.
func liveViewTrackLeave(userID int) {
	if userID == 0 {
		return
	}
	liveViewMu.Lock()
	defer liveViewMu.Unlock()
	v, ok := liveViewVisitors[userID]
	if !ok {
		return
	}
	v.connections--
	if v.connections <= 0 {
		delete(liveViewVisitors, userID)
	}
}

// liveViewSnapshot returns the currently-online visitors, newest first,
// pruning entries whose heartbeat stopped more than liveViewStaleAfter ago.
// The open-conversation UUID is resolved per visitor with one cheap query;
// a visitor with no open conversation simply has an empty UUID.
func liveViewSnapshot(app *App) []*liveVisitor {
	now := time.Now()
	liveViewMu.Lock()
	for id, v := range liveViewVisitors {
		if now.Sub(v.LastSeen) > liveViewStaleAfter {
			delete(liveViewVisitors, id)
		}
	}
	visitors := make([]*liveVisitor, 0, len(liveViewVisitors))
	for _, v := range liveViewVisitors {
		cp := *v
		cp.SecondsOnSite = int64(now.Sub(v.FirstSeen) / time.Second)
		visitors = append(visitors, &cp)
	}
	liveViewMu.Unlock()

	sort.Slice(visitors, func(i, j int) bool {
		return visitors[i].FirstSeen.After(visitors[j].FirstSeen)
	})

	for _, v := range visitors {
		var convUUID string
		err := app.db.Get(&convUUID, `
			SELECT c.uuid FROM conversations c
			JOIN conversation_statuses s ON s.id = c.status_id
			WHERE c.contact_id = $1 AND s.category = 'open'
			ORDER BY c.updated_at DESC LIMIT 1`, v.ContactID)
		if err == nil {
			v.ConversationUUID = convUUID
		} else if err != sql.ErrNoRows {
			app.lo.Warn("error looking up open conversation for live view", "contact_id", v.ContactID, "error", err)
		}
	}
	return visitors
}

// handleLiveView serves GET /api/v1/live-view for agents.
func handleLiveView(r *fastglue.Request) error {
	app := r.Context.(*App)
	return r.SendEnvelope(liveViewSnapshot(app))
}
