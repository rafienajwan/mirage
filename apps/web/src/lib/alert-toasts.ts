import type { FeedAlert } from "./api-types";

/**
 * Decide which alerts deserve a toast. The WebSocket snapshot and the poll
 * can return different windows of history, so "an id I have not seen" is not
 * the same as "new". Only alerts newer than the newest one already seen count.
 *
 * `watermark` is the newest alert time seen so far (ms), or null before the
 * first load; the first load never toasts.
 */
export function selectNewAlerts(
  alerts: FeedAlert[],
  watermark: number | null,
): { fresh: FeedAlert[]; watermark: number } {
  const timed = alerts
    .map((alert) => ({ alert, time: Date.parse(alert.timestamp) }))
    .filter(({ time }) => Number.isFinite(time));
  const newest = timed.reduce((max, { time }) => Math.max(max, time), watermark ?? 0);

  if (watermark === null) return { fresh: [], watermark: newest };
  return {
    fresh: timed.filter(({ time }) => time > watermark).map(({ alert }) => alert),
    watermark: newest,
  };
}
