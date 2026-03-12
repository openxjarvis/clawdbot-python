---
summary: "Gateway-owned node pairing for remote nodes"
read_when:
  - Implementing node pairing approvals
  - Adding CLI flows for approving remote nodes
title: "Gateway-Owned Pairing"
---

# Gateway-owned pairing

In Gateway-owned pairing, the **Gateway** is the source of truth for which nodes
are allowed to join. UIs are just frontends that approve or reject pending requests.

## Concepts

- **Pending request**: a node asked to join; requires approval.
- **Paired node**: approved node with an issued auth token.

## How pairing works

1. A node connects to the Gateway WS and requests pairing.
2. The Gateway stores a **pending request** and emits `node.pair.requested`.
3. You approve or reject the request (CLI or UI).
4. On approval, the Gateway issues a **new token** (tokens are rotated on re-pair).
5. The node reconnects using the token and is now "paired".

Pending requests expire automatically after **5 minutes**.

## CLI workflow

```bash
openclaw nodes pending
openclaw nodes approve <requestId>
openclaw nodes reject <requestId>
openclaw nodes status
openclaw nodes rename --node <id|name|ip> --name "My Node"
```

## API surface (gateway protocol)

Events:

- `node.pair.requested` — emitted when a new pending request is created.
- `node.pair.resolved` — emitted when a request is approved/rejected/expired.

Methods:

- `node.pair.request` — create or reuse a pending request.
- `node.pair.list` — list pending + paired nodes.
- `node.pair.approve` — approve a pending request (issues token).
- `node.pair.reject` — reject a pending request.
- `node.pair.verify` — verify `{ nodeId, token }`.

## Python implementation

- `openclaw/cli/pairing_cmd.py` — `pairing` CLI commands
- `openclaw/gateway/handlers.py` — `node.pair.*` RPC handlers

## Related docs

- [Discovery](/gateway/discovery)
- [Authentication](/gateway/authentication)
