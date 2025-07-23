import os 
import webbrowser
import msal
from dotenv import load_dotenv

MS_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

def get_access_token(application_id, client_secret, scopes ):
    client = msal.ConfidentialClientApplication(
        client_id = application_id,
        client_credential = client_secret,
        authority = f"https://login.microsoftonline.com/consumers"
    )

    refresh_token = None
    if os.path.exists("refresh_token.txt"):
        with open("refresh_token.txt", "r") as file:
            refresh_token = file.read().strip()
    if refresh_token:
        token_response = client.acquire_token_by_refresh_token(refresh_token, scopes=scopes)

    else:
        print("Using existing refresh token.")
        authorization_url = client.get_authorization_request_url(
            scopes=scopes,        )
        webbrowser.open(authorization_url)
        print("Please sign in to your Microsoft account in the browser.")
        print("After signing in, paste the authorization code here:")
        authorization_code = input("Authorization code: ")
        token_response = client.acquire_token_by_authorization_code(
            code=authorization_code,
            scopes=scopes
        )
    if 'access_token' in token_response:
        if 'refresh_token' in token_response:
            with open("refresh_token.txt", "w") as file:
                file.write(token_response['refresh_token'])
        return token_response['access_token']
    else:
        raise Exception("Failed to obtain access token: " + str(token_response))
        
def main():
    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRECT")
    scopes = ['User.Read', 'Mail.Read', 'Mail.Send', 'Mail.ReadWrite']
    
    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        
        headers = {
           'Authorization': f'Bearer {access_token}', }
        print(headers)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()  