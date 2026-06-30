import { NextResponse } from "next/server";

export async function POST(
  request: Request,
  context: { params: Promise<{ caseId: string }> },
) {
  const { caseId } = await context.params;
  const gatewayUrl = process.env.MIRAGE_INTERNAL_API_URL;
  const apiKey = process.env.MIRAGE_API_KEY;
  if (!gatewayUrl || !apiKey) {
    return NextResponse.json(
      { detail: "Actor case service is not configured" },
      { status: 503 },
    );
  }

  const payload = await request.json().catch(() => ({}));

  try {
    const response = await fetch(
      `${gatewayUrl.replace(/\/$/, "")}/api/v1/dashboard/actor-cases/${encodeURIComponent(caseId)}/open`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Mirage-API-Key": apiKey,
        },
        body: JSON.stringify({
          note: payload.note ?? "",
          assigned_to: payload.assigned_to ?? "",
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
