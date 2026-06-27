import { NextResponse } from "next/server";

export async function POST() {
  const gatewayUrl = process.env.MIRAGE_INTERNAL_API_URL;
  const apiKey = process.env.MIRAGE_API_KEY;
  if (!gatewayUrl || !apiKey) {
    return NextResponse.json(
      { detail: "Retraining service is not configured" },
      { status: 503 },
    );
  }

  try {
    const response = await fetch(
      `${gatewayUrl.replace(/\/$/, "")}/api/v1/dashboard/training-data/retrain`,
      {
        method: "POST",
        headers: { "X-Mirage-API-Key": apiKey },
        cache: "no-store",
      },
    );
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Gateway is unavailable" },
      { status: 502 },
    );
  }
}
