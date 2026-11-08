import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createLoginThrottle, loginClientKey } from "./login-throttle";

const MINUTE = 60_000;

function clock(start = 1_000_000) {
  let now = start;
  return {
    now: () => now,
    advance: (ms: number) => {
      now += ms;
    },
  };
}

describe("login throttle", () => {
  it("blocks a client after five failures", () => {
    const time = clock();
    const throttle = createLoginThrottle({ now: time.now });
    for (let i = 0; i < 4; i += 1) throttle.recordFailure("a");
    assert.equal(throttle.check("a").allowed, true);
    throttle.recordFailure("a");
    const result = throttle.check("a");
    assert.equal(result.allowed, false);
    assert.ok(result.retryAfterSeconds >= 1 && result.retryAfterSeconds <= 900);
  });

  it("unblocks once failures leave the window", () => {
    const time = clock();
    const throttle = createLoginThrottle({ now: time.now });
    for (let i = 0; i < 5; i += 1) throttle.recordFailure("a");
    time.advance(15 * MINUTE + 1);
    assert.equal(throttle.check("a").allowed, true);
  });

  it("clears a client on success", () => {
    const throttle = createLoginThrottle({ now: clock().now });
    for (let i = 0; i < 4; i += 1) throttle.recordFailure("a");
    throttle.recordSuccess("a");
    throttle.recordFailure("a");
    assert.equal(throttle.check("a").allowed, true);
  });

  it("blocks everyone after fifty failures in total", () => {
    const throttle = createLoginThrottle({ now: clock().now });
    for (let i = 0; i < 50; i += 1) throttle.recordFailure(`client-${i}`);
    assert.equal(throttle.check("fresh").allowed, false);
  });

  it("forgets the oldest client beyond the key cap", () => {
    const throttle = createLoginThrottle({
      now: clock().now,
      maxClients: 2,
      perClientLimit: 1,
      globalLimit: 100,
    });
    throttle.recordFailure("a");
    throttle.recordFailure("b");
    throttle.recordFailure("c");
    assert.equal(throttle.check("a").allowed, true);
    assert.equal(throttle.check("c").allowed, false);
  });
});

describe("login attempts", () => {
  it("counts attempts before their outcome is known", () => {
    const throttle = createLoginThrottle({ now: clock().now });
    for (let i = 0; i < 5; i += 1) {
      assert.equal(throttle.attempt("a").allowed, true);
    }
    assert.equal(throttle.attempt("a").allowed, false);
  });

  it("does not charge successful attempts to the global budget", () => {
    const throttle = createLoginThrottle({ now: clock().now, globalLimit: 2 });
    throttle.attempt("a");
    throttle.recordSuccess("a");
    assert.equal(throttle.attempt("b").allowed, true);
    assert.equal(throttle.attempt("c").allowed, true);
    assert.equal(throttle.attempt("d").allowed, false);
  });
});

describe("login client key", () => {
  it("uses the hop the trusted proxy appended, not one the client wrote", () => {
    const spoofed = new Headers({ "x-forwarded-for": "1.2.3.4, 198.51.100.7" });
    assert.equal(loginClientKey(spoofed, true), "198.51.100.7");
  });

  it("ignores forwarded headers unless trusted", () => {
    const headers = new Headers({ "x-forwarded-for": "203.0.113.9, 10.0.0.1" });
    assert.equal(loginClientKey(headers, false), "direct");
    assert.equal(loginClientKey(headers, true), "10.0.0.1");
    assert.equal(loginClientKey(new Headers(), true), "direct");
  });
});
