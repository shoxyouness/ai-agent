export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
    try {
        const body = await req.json();

        const upstream = await fetch(`${BACKEND_URL}/audio/tts`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
        });

        if (!upstream.ok) {
            const errText = await upstream.text();
            return new Response(
                JSON.stringify({ error: `Backend error ${upstream.status}: ${errText}` }),
                { status: 500, headers: { "Content-Type": "application/json" } }
            );
        }

        const audioBlob = await upstream.blob();
        return new Response(audioBlob, {
            status: 200,
            headers: {
                "Content-Type": "audio/mpeg",
                "Content-Disposition": 'attachment; filename="response.mp3"'
            },
        });
    } catch (e: any) {
        return new Response(
            JSON.stringify({ error: e?.message ?? String(e) }),
            { status: 500, headers: { "Content-Type": "application/json" } }
        );
    }
}
