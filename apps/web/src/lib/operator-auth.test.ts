import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  createDashboardStreamTicket,
  createOperatorSession,
  isSameOriginRequest,
  readOperatorSession,
  verifyOperatorSession,
} from "./operator-auth";

const SESSION_SECRET = "session-secret-with-at-least-32-characters";
const ALICE = { sub: "alice", role: "analyst" } as const;

function base64Url(bytes: Uint8Array) {
  return Buffer.from(bytes).toString("base64url");
}

// Signs arbitrary claims with the session secret, so claim checks are tested
// apart from the signature check.
async function signClaims(claims: Record<string, unknown>) {
  const payload = base64Url(new TextEncoder().encode(JSON.stringify(claims)));
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(SESSION_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
  return `${payload}.${base64Url(new Uint8Array(signature))}`;
}

const BASE_CLAIMS = {
  aud: "mirage-operator-session",
  iat: 1_000,
  exp: 2_000,
  nonce: "session-nonce-0123456789",
};

const TICKET_SECRET = "ticket-secret-with-at-least-32-characters!";

describe("operator authentication tokens", () => {
  it("accepts a valid operator session until its expiry", async () => {
    const token = await createOperatorSession({
      secret: SESSION_SECRET,
      now: 1_000,
      nonce: "session-nonce-0123456789",
      operator: ALICE,
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
      operator: ALICE,
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
  });

  it("rejects secrets shorter than 32 characters", async () => {
    await assert.rejects(
      createOperatorSession({
        secret: "too-short",
        now: 1_000,
        nonce: "session-nonce-0123456789",
        operator: ALICE,
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

  it("reads the operator back from a session", async () => {
    const token = await createOperatorSession({
      secret: SESSION_SECRET,
      now: 1_000,
      nonce: "session-nonce-0123456789",
      operator: ALICE,
    });
    assert.deepEqual(await readOperatorSession(token, SESSION_SECRET, 1_001), {
      sub: "alice",
      role: "analyst",
    });
  });

  it("rejects sessions from before operator accounts", async () => {
    const token = await signClaims(BASE_CLAIMS);
    assert.equal(await readOperatorSession(token, SESSION_SECRET, 1_001), null);
    assert.equal(await verifyOperatorSession(token, SESSION_SECRET, 1_001), false);
  });

  it("rejects malformed usernames and unknown roles", async () => {
    const badName = await signClaims({ ...BASE_CLAIMS, sub: "Bad!", role: "analyst" });
    const badRole = await signClaims({ ...BASE_CLAIMS, sub: "alice", role: "root" });
    assert.equal(await readOperatorSession(badName, SESSION_SECRET, 1_001), null);
    assert.equal(await readOperatorSession(badRole, SESSION_SECRET, 1_001), null);
  });

  it("rejects a session whose payload was altered", async () => {
    const token = await createOperatorSession({
      secret: SESSION_SECRET,
      now: 1_000,
      nonce: "session-nonce-0123456789",
      operator: ALICE,
    });
    const [, signature] = token.split(".");
    const forged = base64Url(
      new TextEncoder().encode(JSON.stringify({ ...BASE_CLAIMS, sub: "alice", role: "admin" })),
    );
    assert.equal(
      await readOperatorSession(`${forged}.${signature}`, SESSION_SECRET, 1_001),
      null,
    );
  });
});
