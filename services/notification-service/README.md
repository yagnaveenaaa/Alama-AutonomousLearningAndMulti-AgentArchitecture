# notification-service

Async multi-channel delivery: email, Slack/Teams, webhooks, in-app
(LLD §2.13 / §4.8 / §3.3). Port **8111**.

## Responsibility

| Type | Role |
|---|---|
| `Notifier` | Channel send adapter |
| `NotificationDispatcher` | Preference routing + retries |
| `DeliveryAttemptRepository` | Attempt tracking |
| `PreferenceService` | Per-recipient channel prefs |

## API (prefix `/v1`)

- `POST /notifications` — dispatch (202) / idempotent replay (200)
- `GET /notifications` — inbox for caller (`X-Subject-Id`)
- `GET /notifications/{id}` — detail + attempts
- `POST /notifications/{id}/read` — mark read
- `GET|PUT /notifications/preferences` — channel prefs

Headers: `X-Subject-Id`, `X-Tenant-Id`.

Retries: 8 attempts, exponential backoff up to 1h (`RetryPolicy.notification`).

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/notification-service[dev]
notification-service
```

## Docker

```bash
cd services/notification-service
docker compose up --build
```

Postgres for the `notification` DB is on host port **5440**.
