import { NextResponse } from "next/server";

export async function GET() {
  const gatewayUrl = process.env.MIRAGE_INTERNAL_API_URL;
  const apiKey = process.env.MIRAGE_API_KEY;
  if (!gatewayUrl || !apiKey) {
    return NextResponse.json(
      { detail: "Training export service is not configured" },
      { status: 503 },
    );
  }

  try {
    const response = await fetch(
      `${gatewayUrl.replace(/\/$/, "")}/api/v1/dashboard/training-data/export`,
      {
        headers: { "X-Mirage-API-Key": apiKey },
        cache: "no-store",
      },
    );
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type": "application/x-ndjson",
        "Content-Disposition":
          response.headers.get("content-disposition") ??
          'attachment; filename="training_events.jsonl"',
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "Gateway is unavailable" },
      { status: 502 },
    );
  }
}
