// Load balancer health check for the self-hosted server (hosting/README.md). No outside calls.
export const dynamic = "force-static";

export function GET() {
  return new Response("ok", { headers: { "content-type": "text/plain" } });
}
