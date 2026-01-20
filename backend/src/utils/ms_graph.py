import os
import json
import webbrowser
import msal
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

MS_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
# Token storage file is relative to this script
TOKEN_FILE_PATH = Path(__file__).parent / "ms_graph_tokens.json"

def _load_tokens():
    """Load tokens from local JSON file."""
    if TOKEN_FILE_PATH.exists():
        try:
            with open(TOKEN_FILE_PATH, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def _save_tokens(token_data):
    """Save tokens to local JSON file."""
    # We only care about saving the persistent parts (refresh_token) 
    # and maybe the current access_token to save a request if it's still valid.
    with open(TOKEN_FILE_PATH, "w") as f:
        json.dump(token_data, f, indent=2)

def get_access_token(application_id=None, client_secret=None, scopes=None):
    """
    Get a valid access token silently.
    
    This function:
    1. Loads the refresh token from disk.
    2. Requests a new access token from Microsoft.
    3. Updates the token file with the new refresh token (rotation).
    
    It does NOT open a browser or prompt for input. If it fails, it raises an exception.
    """
    if not application_id:
        application_id = os.getenv("APPLICATION_ID")
    if not client_secret:
        client_secret = os.getenv("CLIENT_SECRET")
    
    if not application_id or not client_secret:
        raise ValueError("Missing APPLICATION_ID or CLIENT_SECRET in environment variables.")

    if scopes is None:
        scopes = ['User.Read', 'Mail.Read', 'Mail.Send', 'Mail.ReadWrite']

    client = msal.ConfidentialClientApplication(
        client_id=application_id,
        client_credential=client_secret,
        authority="https://login.microsoftonline.com/consumers"
    )

    tokens = _load_tokens()
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        raise FileNotFoundError(
            f"No refresh token found in {TOKEN_FILE_PATH}. "
            "Please run this script manually to perform initial setup: 'python src/utils/ms_graph.py'"
        )

    # Acquire new access token using the refresh token
    token_response = client.acquire_token_by_refresh_token(refresh_token, scopes=scopes)

    if "error" in token_response:
        raise Exception(f"Failed to refresh token: {token_response.get('error_description')}")

    # Success! Save the new tokens (Microsoft often rotates the refresh token)
    if "refresh_token" in token_response:
        tokens["refresh_token"] = token_response["refresh_token"]
    
    if "access_token" in token_response:
        tokens["access_token"] = token_response["access_token"] # Cache current access token if we wanted to reuse it locally
    
    _save_tokens(tokens)

    return token_response["access_token"]

def perform_initial_setup():
    """
    Interactive setup to get the first refresh token.
    Run this manually in your terminal.
    """
    print("--- MS Graph Initial Setup ---")
    
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scopes = ['User.Read', 'Mail.Read', 'Mail.Send', 'Mail.ReadWrite']

    if not application_id or not client_secret:
        print("ERROR: APPLICATION_ID or CLIENT_SECRET not found in .env file.")
        return

    client = msal.ConfidentialClientApplication(
        client_id=application_id,
        client_credential=client_secret,
        authority="https://login.microsoftonline.com/consumers"
    )

    redirect_uri = os.getenv("REDIRECT_URI", "http://localhost")
    
    authorization_url = client.get_authorization_request_url(
        scopes=scopes,
        redirect_uri=redirect_uri
    )
    
    print("Step 1: I will open the login page in your browser.")
    print(f"URL: {authorization_url}")
    webbrowser.open(authorization_url)
    
    print("\nStep 2: Sign in and consent to permissions.")
    print(f"Step 3: You will be redirected to a blank page.") 
    print(f"        (Look for address starting with {redirect_uri}?code=...)")
    print("Step 4: Copy the code from the address bar (everything after 'code=' up to any '&' symbol).")
    
    authorization_code = input("\nPaste the Authorization Code here: ").strip()
    
    if not authorization_code:
        print("Error: No code entered.")
        return

    print("Acquiring token...")
    # Clean the code just in case user pasted the whole URL or suffix
    if "code=" in authorization_code:
        authorization_code = authorization_code.split("code=")[1]
    if "&" in authorization_code:
        authorization_code = authorization_code.split("&")[0]

    # Decode URL-encoded characters (e.g., %24 -> $)
    from urllib.parse import unquote
    authorization_code = unquote(authorization_code)

    try:
        token_response = client.acquire_token_by_authorization_code(
            code=authorization_code,
            scopes=scopes,
            redirect_uri=redirect_uri
        )
    except Exception as e:
        print(f"CRITICAL ERROR during token exchange: {e}")
        return

    if "access_token" in token_response:
        print("Success! Token acquired.")
        # Save to JSON
        tokens = {
            "refresh_token": token_response.get("refresh_token"),
            "access_token": token_response.get("access_token")
        }
        _save_tokens(tokens)
        print(f"Tokens saved to {TOKEN_FILE_PATH}")
        print("You can now run your agent.")
    else:
        print(f"Failed to obtain token: {token_response}")

if __name__ == "__main__":
    perform_initial_setup()