import { NextResponse } from "next/server";

const STATUSES = new Set(["open", "investigating", "closed"]);

export async function PATCH(
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

  const payload = await request.json().catch(() => null);
  if (!payload || !STATUSES.has(payload.status)) {
    return NextResponse.json({ detail: "Invalid actor case status" }, { status: 422 });
  }

  try {
    const response = await fetch(
      `${gatewayUrl.replace(/\/$/, "")}/api/v1/dashboard/actor-case-workflows/${encodeURIComponent(caseId)}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-Mirage-API-Key": apiKey,
        },
        body: JSON.stringify({
          status: payload.status,
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
