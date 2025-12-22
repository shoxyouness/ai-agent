# run_api.py
import sys
import asyncio
import uvicorn

def main():
    # 1. FORCE WINDOWS TO USE THE CORRECT EVENT LOOP
    # This must happen before ANY async code is touched.
    if sys.platform == "win32":
        # Check if the policy is already set to prevent double-setting warnings
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            print("✅ Enforced WindowsProactorEventLoopPolicy for Browser Use")

    # 2. Run Uvicorn
    # IMPORTANT: reload=False. 
    # 'reload' spawns subprocesses that often reset the event loop on Windows.
    print("🚀 Starting API Server...")
    uvicorn.run(
        "src.api.api:app", 
        host="0.0.0.0", 
        port=8000, 
        loop="asyncio", # Explicitly tell Uvicorn to use the asyncio loop we just configured
        reload=False    # Must be False to keep the Proactor loop stable
    )

if __name__ == "__main__":
    main()