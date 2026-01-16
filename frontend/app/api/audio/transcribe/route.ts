export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
    try {
        const formData = await req.formData();

        const upstream = await fetch(`${BACKEND_URL}/audio/transcribe`, {
            method: "POST",
            body: formData,
        });

        if (!upstream.ok) {
            const errText = await upstream.text();
            return new Response(
                JSON.stringify({ error: `Backend error ${upstream.status}: ${errText}` }),
                { status: 500, headers: { "Content-Type": "application/json" } }
            );
        }

        const data = await upstream.json();
        return new Response(JSON.stringify(data), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
    } catch (e: any) {
        return new Response(
            JSON.stringify({ error: e?.message ?? String(e) }),
            { status: 500, headers: { "Content-Type": "application/json" } }
        );
    }
}
