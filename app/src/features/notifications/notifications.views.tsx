import { useState } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Status } from "../../components/Status";
import { NOTIFICATION_FIXTURE_NOTE, seedNotifications } from "./notifications.fixtures";

export function NotificationsInbox() {
  const [notices, setNotices] = useState(seedNotifications());

  function markRead(id: string) {
    setNotices((previous) => previous.map((notice) =>
      notice.id === id ? { ...notice, read: true, statusText: "Read" } : notice,
    ));
  }

  const unread = notices.filter((notice) => !notice.read).length;
  return (
    <section aria-labelledby="notif-h">
      <h2 id="notif-h">Notifications{unread > 0 ? ` (${unread} unread)` : ""}</h2>
      <p role="note" className="badge">{NOTIFICATION_FIXTURE_NOTE}</p>
      {notices.length === 0 ? (
        <EmptyState title="No notifications" body="Plan, evidence, and source events will appear here." />
      ) : (
        <ul className="cards">
          {notices.map((notice) => (
            <li key={notice.id}>
              <article className="card" aria-label={notice.title}>
                <h3>{notice.title}</h3>
                <Status label={notice.statusText} tone={notice.read ? "info" : "warn"} />
                <p>{notice.reason}</p>
                <p className="hint">{notice.time}</p>
                <p className="row">
                  <a href={notice.href}>Open related record</a>
                  {!notice.read && (
                    <Button variant="secondary" onClick={() => markRead(notice.id)}>
                      Mark read
                    </Button>
                  )}
                </p>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function NotificationCard({ noticeId }: { noticeId: string }) {
  const notice = seedNotifications().find((item) => item.id === noticeId);
  if (!notice) return <p role="alert">Notification not found. <a href="#/notifications">Back to Notifications</a>.</p>;
  return (
    <Card title={notice.title}>
      <p>{notice.reason}</p>
      <p className="hint">{notice.time} · {notice.statusText}</p>
      <p><a href={notice.href}>Open related record</a></p>
    </Card>
  );
}
