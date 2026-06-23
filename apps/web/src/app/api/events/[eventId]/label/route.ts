import { NextResponse } from "next/server";

const LABELS = new Set([
  "normal",
  "suspicious",
  "false_positive",
  "false_negative",
]);

export async function PATCH(
  request: Request,
  context: { params: Promise<{ eventId: string }> },
) {
  const { eventId } = await context.params;
  const gatewayUrl = process.env.MIRAGE_INTERNAL_API_URL;
  const apiKey = process.env.MIRAGE_API_KEY;
  if (!gatewayUrl || !apiKey) {
    return NextResponse.json(
      { detail: "Event labeling service is not configured" },
      { status: 503 },
    );
  }

  const payload = await request.json().catch(() => null);
  if (!payload || !LABELS.has(payload.label)) {
    return NextResponse.json({ detail: "Invalid analyst label" }, { status: 422 });
  }

  try {
    const response = await fetch(
      `${gatewayUrl.replace(/\/$/, "")}/api/v1/dashboard/events/${encodeURIComponent(eventId)}/label`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-Mirage-API-Key": apiKey,
        },
        body: JSON.stringify({
          label: payload.label,
          note: payload.note ?? "",
        }),
        cache: "no-store",
      },
    );
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "Gateway is unavailable" },
      { status: 502 },
    );
  }
}
