import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*70)
print("CALL AGENT CONFIGURATION TEST")
print("="*70)

# Check required environment variables
required_vars = {
    "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID"),
    "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN"),
    "TWILIO_FROM_NUMBER": os.getenv("TWILIO_FROM_NUMBER"),
    "PUBLIC_BASE_URL": os.getenv("PUBLIC_BASE_URL"),
}

print("\n📋 Environment Variables:")
print("-" * 70)
for key, value in required_vars.items():
    if value:
        if "TOKEN" in key or "AUTH" in key:
            display_value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
        else:
            display_value = value
        print(f"✅ {key}: {display_value}")
    else:
        print(f"❌ {key}: NOT SET")

# Derive URLs
public_base = required_vars["PUBLIC_BASE_URL"] or ""
if public_base:
    ws_base = public_base.replace("https://", "wss://").replace("http://", "ws://")
    
    print("\n🌐 Derived URLs:")
    print("-" * 70)
    print(f"TwiML Initiate: {public_base}/call/initiate")
    print(f"Status Callback: {public_base}/call/status")
    print(f"WebSocket Base: {ws_base}/call/media-stream/<call_sid>")
else:
    print("\n❌ PUBLIC_BASE_URL not set - cannot derive URLs")

# Test ngrok
print("\n🔍 Testing ngrok connectivity...")
print("-" * 70)

import requests
try:
    if public_base:
        response = requests.get(f"{public_base}/call/test", timeout=5)
        if response.status_code == 200:
            print(f"✅ ngrok is accessible: {response.json()}")
        else:
            print(f"⚠️ ngrok returned status {response.status_code}")
    else:
        print("❌ Cannot test - no PUBLIC_BASE_URL set")
except Exception as e:
    print(f"❌ Cannot reach ngrok: {e}")
    print("   Make sure your FastAPI server is running!")
    print("   Run: uvicorn src.api.main:app --reload")

# Test Twilio credentials
print("\n🔑 Testing Twilio credentials...")
print("-" * 70)

try:
    from twilio.rest import Client
    
    account_sid = required_vars["TWILIO_ACCOUNT_SID"]
    auth_token = required_vars["TWILIO_AUTH_TOKEN"]
    
    if account_sid and auth_token:
        client = Client(account_sid, auth_token)
        account = client.api.accounts(account_sid).fetch()
        print(f"✅ Twilio credentials valid")
        print(f"   Account: {account.friendly_name}")
        print(f"   Status: {account.status}")
    else:
        print("❌ Twilio credentials not set")
        
except Exception as e:
    print(f"❌ Twilio authentication failed: {e}")

print("\n" + "="*70)
print("CONFIGURATION CHECK COMPLETE")
print("="*70)

# Print setup instructions if issues found
missing = [k for k, v in required_vars.items() if not v]
if missing:
    print("\n⚠️ SETUP REQUIRED:")
    print("-" * 70)
    print("Missing environment variables:")
    for var in missing:
        print(f"  - {var}")
    print("\nAdd these to your .env file:")
    print("TWILIO_ACCOUNT_SID=your_account_sid")
    print("TWILIO_AUTH_TOKEN=your_auth_token")
    print("TWILIO_FROM_NUMBER=+1234567890")
    print("PUBLIC_BASE_URL=https://your-ngrok-url.ngrok-free.app")
else:
    print("\n✅ All environment variables are set!")
    print("\n📝 Next steps:")
    print("1. Make sure FastAPI is running: uvicorn src.api.main:app --reload")
    print("2. Make sure ngrok is running: ngrok http 8000")
    print("3. Run your agent: python main.py")
    print("4. Test: 'call younes at +4915906752100'")

print()