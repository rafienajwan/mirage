import { NextResponse } from "next/server";

const SIMULATION_KINDS = new Set(["normal", "suspicious"]);

export async function POST(
  _request: Request,
  context: { params: Promise<{ kind: string }> },
) {
  const { kind } = await context.params;
  if (!SIMULATION_KINDS.has(kind)) {
    return NextResponse.json({ detail: "Unknown simulation" }, { status: 404 });
  }

  const gatewayUrl = process.env.MIRAGE_INTERNAL_API_URL;
  const apiKey = process.env.MIRAGE_API_KEY;
  if (!gatewayUrl || !apiKey) {
    return NextResponse.json(
      { detail: "Simulation service is not configured" },
      { status: 503 },
    );
  }

  try {
    const response = await fetch(
      `${gatewayUrl.replace(/\/$/, "")}/api/v1/simulate/${kind}`,
      {
        method: "POST",
        headers: { "X-Mirage-API-Key": apiKey },
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
