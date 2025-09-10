import os, sys, json, asyncio, shutil
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

REQUIRED = [
    "project_id", "private_key_id", "private_key",
    "client_email", "client_id", "client_x509_cert_url",
]

def load_sa_json():
    p = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if p and os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

SA = load_sa_json()
def env_or_sa(k): return os.getenv(k) or SA.get(k)

def make_params(env: dict) -> StdioServerParameters:
    if shutil.which("uvx"):
        return StdioServerParameters(
            command="uvx",
            args=["google-sheets-mcp@latest"],
            env=env,
        )
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "gsheet_mcp_server"],
        env=env,
    )

async def main():
    # Build the child-process environment (what the server expects)
    server_env = {k: env_or_sa(k) for k in REQUIRED}
    miss = [k for k,v in server_env.items() if not v]
    if miss:
        raise SystemExit(f"Missing creds: {miss} "
                         "(put them in .env OR set GOOGLE_APPLICATION_CREDENTIALS to the SA JSON)")

    # If private_key is in .env, it must be ONE LINE with literal \n
    params = make_params(server_env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize (handle different mcp versions)
            initialized = False
            for kwargs in ({"environment": server_env}, {}):
                try:
                    await session.initialize(**kwargs)
                    initialized = True
                    break
                except TypeError:
                    continue
            if not initialized:
                raise RuntimeError("Failed to initialize MCP session (unexpected mcp version).")

            resp = await session.list_tools()
            tools = getattr(resp, "tools", []) or []
            print("Tools:")
            for t in tools:
                print("-", t.name)

if __name__ == "__main__":
    asyncio.run(main())
