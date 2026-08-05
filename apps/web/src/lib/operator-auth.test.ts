import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  createDashboardStreamTicket,
  createOperatorSession,
  isSameOriginRequest,
  verifyDashboardStreamTicket,
  verifyOperatorSession,
} from "./operator-auth";

const SESSION_SECRET = "session-secret-with-at-least-32-characters";
const TICKET_SECRET = "ticket-secret-with-at-least-32-characters!";

describe("operator authentication tokens", () => {
  it("accepts a valid operator session until its expiry", async () => {
    const token = await createOperatorSession({
      secret: SESSION_SECRET,
      now: 1_000,
      nonce: "session-nonce-0123456789",
    });

    assert.equal(
      await verifyOperatorSession(token, SESSION_SECRET, 1_001),
      true,
    );
    assert.equal(
      await verifyOperatorSession(token, SESSION_SECRET, 29_800),
      false,
    );
  });

  it("rejects operator sessions signed by another secret", async () => {
    const token = await createOperatorSession({
      secret: SESSION_SECRET,
      now: 1_000,
      nonce: "session-nonce-0123456789",
    });

    assert.equal(
      await verifyOperatorSession(
        token,
        "different-session-secret-with-32-characters",
        1_001,
      ),
      false,
    );
  });

  it("creates a 60-second dashboard stream ticket", async () => {
    const result = await createDashboardStreamTicket({
      secret: TICKET_SECRET,
      now: 2_000,
      nonce: "ticket-nonce-01234567890",
    });

    assert.equal(result.expiresAt, 2_060);
    assert.equal(
      await verifyDashboardStreamTicket(result.token, TICKET_SECRET, 2_059),
      true,
    );
    assert.equal(
      await verifyDashboardStreamTicket(result.token, TICKET_SECRET, 2_060),
      false,
    );
  });

  it("does not allow a session token to authenticate the stream", async () => {
    const session = await createOperatorSession({
      secret: SESSION_SECRET,
      now: 1_000,
      nonce: "session-nonce-0123456789",
    });

    assert.equal(
      await verifyDashboardStreamTicket(session, SESSION_SECRET, 1_001),
      false,
    );
  });

  it("rejects secrets shorter than 32 characters", async () => {
    await assert.rejects(
      createOperatorSession({
        secret: "too-short",
        now: 1_000,
        nonce: "session-nonce-0123456789",
      }),
      /at least 32 characters/,
    );
  });

  it("accepts the public host when Docker maps it to an internal port", () => {
    assert.equal(
      isSameOriginRequest({
        origin: "http://localhost:3001",
        host: "localhost:3001",
        protocol: "http:",
      }),
      true,
    );
  });

  it("rejects cross-origin and malformed login origins", () => {
    assert.equal(
      isSameOriginRequest({
        origin: "https://attacker.example",
        host: "localhost:3001",
        protocol: "http:",
      }),
      false,
    );
    assert.equal(
      isSameOriginRequest({
        origin: "not-a-valid-origin",
        host: "localhost:3001",
        protocol: "http:",
      }),
      false,
    );
  });
});
