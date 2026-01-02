export const runtime = "nodejs"; // IMPORTANT for streaming stability

export async function POST(req: Request) {
  const body = await req.text(); // forward raw JSON
  const upstream = await fetch("http://localhost:8000/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
    },
    body,
  });

  // Pass-through the stream + SSE headers
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "Connection": "keep-alive",
    },
  });
}