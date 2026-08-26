import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer, request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { dirname, extname, join, resolve, sep } from "node:path";
import { Transform } from "node:stream";
import { fileURLToPath } from "node:url";

const serverDirectory = dirname(fileURLToPath(import.meta.url));
const distributionDirectory = resolve(serverDirectory, "dist");
const port = Number.parseInt(process.env.PORT ?? "8080", 10);
const host = process.env.HOST ?? "0.0.0.0";
const maxRequestBodyBytes = 2 * 1024 * 1024;

function upstreamUrl() {
  if (process.env.API_UPSTREAM_URL) return new URL(process.env.API_UPSTREAM_URL);
  const upstreamHost = process.env.API_UPSTREAM_HOST;
  const upstreamPort = process.env.API_UPSTREAM_PORT ?? "8000";
  if (upstreamHost) return new URL(`http://${upstreamHost}:${upstreamPort}`);
  if (process.env.NODE_ENV === "production") {
    // Railway private network default: the backend service is named "api".
    // Override with API_UPSTREAM_URL if the service has a different name.
    return new URL(`http://api.railway.internal:${upstreamPort}`);
  }
  return new URL("http://127.0.0.1:8000");
}

const apiUpstream = upstreamUrl();
if (!new Set(["http:", "https:"]).has(apiUpstream.protocol)) {
  throw new Error("API upstream faqat http yoki https bo‘lishi mumkin");
}

const hopByHopHeaders = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function withoutHopByHopHeaders(source) {
  return Object.fromEntries(
    Object.entries(source).filter(([name]) => !hopByHopHeaders.has(name.toLowerCase())),
  );
}

const mimeTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".map", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".webp", "image/webp"],
  [".woff2", "font/woff2"],
]);

function setSecurityHeaders(response) {
  response.setHeader("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'");
  response.setHeader("Referrer-Policy", "same-origin");
  response.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("X-Frame-Options", "DENY");
}

function proxyApi(clientRequest, clientResponse) {
  const contentLength = Number.parseInt(clientRequest.headers["content-length"] ?? "0", 10);
  if (Number.isFinite(contentLength) && contentLength > maxRequestBodyBytes) {
    setSecurityHeaders(clientResponse);
    clientResponse.writeHead(413, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
    clientResponse.end(JSON.stringify({ code: "REQUEST_TOO_LARGE", message: "So‘rov hajmi juda katta" }));
    return;
  }
  const requestUrl = new URL(clientRequest.url ?? "/", "http://localhost");
  const target = new URL(apiUpstream);
  target.pathname = requestUrl.pathname;
  target.search = requestUrl.search;
  const forwardedFor = clientRequest.headers["x-forwarded-for"];
  const headers = {
    ...withoutHopByHopHeaders(clientRequest.headers),
    host: target.host,
    "x-forwarded-for": forwardedFor ?? clientRequest.socket.remoteAddress ?? "unknown",
    "x-forwarded-host": clientRequest.headers.host ?? "",
    "x-forwarded-proto": clientRequest.headers["x-forwarded-proto"] ?? "http",
  };

  const requestFunction = target.protocol === "https:" ? httpsRequest : httpRequest;
  let bodyTooLarge = false;
  const upstreamRequest = requestFunction(
    target,
    { method: clientRequest.method, headers },
    (upstreamResponse) => {
      clientResponse.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
      clientResponse.writeHead(
        upstreamResponse.statusCode ?? 502,
        withoutHopByHopHeaders(upstreamResponse.headers),
      );
      upstreamResponse.pipe(clientResponse);
    },
  );
  upstreamRequest.setTimeout(30_000, () => upstreamRequest.destroy(new Error("API timeout")));
  upstreamRequest.on("error", () => {
    if (clientResponse.headersSent) {
      clientResponse.destroy();
      return;
    }
    setSecurityHeaders(clientResponse);
    clientResponse.writeHead(bodyTooLarge ? 413 : 502, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
    clientResponse.end(JSON.stringify(bodyTooLarge ? { code: "REQUEST_TOO_LARGE", message: "So‘rov hajmi juda katta" } : { code: "API_UNAVAILABLE", message: "API bilan aloqa yo‘q" }));
  });
  let receivedBytes = 0;
  const bodyLimiter = new Transform({
    transform(chunk, _encoding, callback) {
      receivedBytes += chunk.length;
      if (receivedBytes > maxRequestBodyBytes) {
        bodyTooLarge = true;
        callback(new Error("Request body too large"));
        return;
      }
      callback(null, chunk);
    },
  });
  bodyLimiter.on("error", () => upstreamRequest.destroy());
  clientRequest.pipe(bodyLimiter).pipe(upstreamRequest);
}

async function serveStatic(request, response) {
  const requestUrl = new URL(request.url ?? "/", "http://localhost");
  let pathname;
  try {
    pathname = decodeURIComponent(requestUrl.pathname);
  } catch {
    response.writeHead(400);
    response.end("Bad request");
    return;
  }

  const relativePath = pathname === "/" ? "index.html" : pathname.replace(/^\/+/, "");
  let filePath = resolve(distributionDirectory, relativePath);
  if (filePath !== distributionDirectory && !filePath.startsWith(`${distributionDirectory}${sep}`)) {
    response.writeHead(400);
    response.end("Bad request");
    return;
  }

  try {
    const fileStat = await stat(filePath);
    if (!fileStat.isFile()) throw new Error("Not a file");
  } catch {
    filePath = join(distributionDirectory, "index.html");
  }

  const extension = extname(filePath);
  setSecurityHeaders(response);
  response.setHeader("Content-Type", mimeTypes.get(extension) ?? "application/octet-stream");
  response.setHeader(
    "Cache-Control",
    filePath.endsWith("index.html") ? "no-cache" : "public, max-age=31536000, immutable",
  );
  if (request.method === "HEAD") {
    response.end();
    return;
  }
  createReadStream(filePath)
    .on("error", () => {
      if (!response.headersSent) response.writeHead(404);
      response.end("Not found");
    })
    .pipe(response);
}

const server = createServer((request, response) => {
  const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
  if (pathname === "/healthz") {
    setSecurityHeaders(response);
    response.writeHead(200, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
    response.end(JSON.stringify({ status: "ok", service: "regurolog-web" }));
    return;
  }
  if (pathname === "/api" || pathname.startsWith("/api/")) {
    proxyApi(request, response);
    return;
  }
  if (request.method !== "GET" && request.method !== "HEAD") {
    response.writeHead(405, { Allow: "GET, HEAD" });
    response.end();
    return;
  }
  void serveStatic(request, response);
});

server.listen(port, host);

function shutdown() {
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
