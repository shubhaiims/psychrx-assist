import { NextRequest, NextResponse } from "next/server";

const DEFAULT_LOCAL_API_BASE_URL = "http://127.0.0.1:8000";
const configuredApiBaseUrl = process.env.API_BASE_URL?.trim();
const API_BASE_URL = (configuredApiBaseUrl || DEFAULT_LOCAL_API_BASE_URL).replace(/\/+$/, "");

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

async function proxyRequest(request: NextRequest, context: RouteContext) {
  if (process.env.VERCEL && !configuredApiBaseUrl) {
    return NextResponse.json(
      {
        detail:
          "Frontend is deployed, but API_BASE_URL is not set. Add your live backend URL in the frontend Vercel project environment variables, then redeploy.",
      },
      { status: 503 },
    );
  }

  const { path } = await context.params;
  const targetUrl = new URL(`${API_BASE_URL}/${path.join("/")}`);

  request.nextUrl.searchParams.forEach((value, key) => {
    targetUrl.searchParams.append(key, value);
  });

  const headers = new Headers();
  const accept = request.headers.get("accept");
  const contentType = request.headers.get("content-type");

  if (accept) {
    headers.set("accept", accept);
  }
  if (contentType) {
    headers.set("content-type", contentType);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
  };

  if (!["GET", "HEAD"].includes(request.method)) {
    init.body = await request.text();
  }

  try {
    const response = await fetch(targetUrl, init);
    const responseContentType = response.headers.get("content-type");

    if (!response.ok && responseContentType?.includes("text/html")) {
      const text = await response.text();
      if (text.includes("DEPLOYMENT_NOT_FOUND")) {
        return NextResponse.json(
          {
            detail:
              "The backend URL configured in API_BASE_URL does not point to a live Vercel deployment. Copy the exact backend domain from Vercel Project > Settings > Domains, update API_BASE_URL, and redeploy the frontend.",
            configuredBackend: API_BASE_URL,
          },
          { status: 502 },
        );
      }

      return new NextResponse(text, {
        status: response.status,
        headers: { "content-type": responseContentType },
      });
    }

    const responseHeaders = new Headers();
    if (responseContentType) {
      responseHeaders.set("content-type", responseContentType);
    }

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          "Unable to reach the backend API. Start the FastAPI service or set API_BASE_URL.",
      },
      { status: 502 },
    );
  }
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}
