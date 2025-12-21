import os
import requests
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv
from src.utils.ms_graph import get_access_token, MS_GRAPH_BASE_URL
from bs4 import BeautifulSoup



class Email(BaseModel):
    """A schema for a single email message."""
    sender: str = Field(description="The name and email address of the sender.")
    subject: str = Field(description="The subject line of the email.")
    body_preview: str = Field(description="A snippet of the email body.")
    message_id: str = Field(description="The unique identifier of the email message.")


    
@tool
def send_email(to: str, subject: str, body: str, cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None) -> str:
    """
    Sends an email using Microsoft Graph API.
    Returns a success message or error details.
    args:
        to (str): The recipient's email address.
        subject (str): The subject of the email.
        body (str): The body content of the email (plain text).
        cc (Optional[List[str]]): List of CC recipients (optional).
        bcc (Optional[List[str]]): List of BCC recipients (optional).
    """
    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    # Scopes required for sending mail
    scopes = ['User.Read', 'Mail.Read', 'Mail.Send', 'Mail.ReadWrite']

    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        if not access_token:
            return "Failed to obtain access token. Cannot send email."

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Prepare the email payload
        email_payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body
                },
                "toRecipients": [{"emailAddress": {"address": recipient.strip()}} for recipient in to.split(',')],
                "ccRecipients": [{"emailAddress": {"address": recipient.strip()}} for recipient in cc] if cc else [],
                "bccRecipients": [{"emailAddress": {"address": recipient.strip()}} for recipient in bcc] if bcc else []
            },
            "saveToSentItems": "true"
        }

        # Microsoft Graph API endpoint for sending mail
        graph_url = f"{MS_GRAPH_BASE_URL}/me/sendMail"
        
        response = requests.post(graph_url, headers=headers, json=email_payload)
        response.raise_for_status() # Raise an exception for HTTP errors

        return "Email sent successfully."

    except Exception as e:
        return f"An error occurred while sending the email: {e}"




@tool
def reply_to_email(message_id: str, comment: str) -> str:
    """
    Replies to a specific email using its message ID.
     args:
        message_id (str): The unique ID of the email message to reply to.
        comment (str): The body content of the reply (plain text).
    """
    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scopes = ['User.Read', 'Mail.Read', 'Mail.Send', 'Mail.ReadWrite']

    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        if not access_token:
            return "Failed to obtain access token. Cannot send reply."

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # The payload for a reply is simpler
        reply_payload = {
            "comment": comment
        }

        # Use the specific "reply" endpoint for the given message ID
        graph_url = f"{MS_GRAPH_BASE_URL}/me/messages/{message_id}/reply"
        
        response = requests.post(graph_url, headers=headers, json=reply_payload)
        response.raise_for_status() # Raise an exception for HTTP errors

        return f"Successfully replied to message ID: {message_id}."

    except Exception as e:
        return f"An error occurred while replying to the email: {e}"



@tool
def mark_email_as_read(message_id: str) -> str:
    """
    Marks a specific email as read using its message ID.
    Returns a success message or error details.
    
    args:
        message_id (str): The unique ID of the email message to mark as read.
    """
    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scopes = ['User.Read', 'Mail.Read', 'Mail.ReadWrite']

    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        if not access_token:
            return "Failed to obtain access token. Cannot update email status."

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        graph_url = f"{MS_GRAPH_BASE_URL}/me/messages/{message_id}"
        update_payload = {"isRead": True}

        response = requests.patch(graph_url, headers=headers, json=update_payload)
        response.raise_for_status()

        return f"Email with ID {message_id} was successfully marked as read."


    except requests.exceptions.HTTPError as e:
        
        try:
            error_details = e.response.json()
            detailed_message = error_details.get('error', {}).get('message', 'No detailed message found.')
        except ValueError: # If response is not JSON
            detailed_message = e.response.text
        
        return f"An error occurred while marking the email as read: {e}\nDetails: {detailed_message}"
    except Exception as e:
        return f"A general error occurred: {e}"



@tool
def get_unread_emails() -> List[dict]:
    """
    Fetches unread emails from the Outlook inbox using Microsoft Graph API.
    Returns a list of emails, each containing the sender, subject, the full body content, and message ID.
    """
    
    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scopes = ['User.Read', 'Mail.Read', 'Mail.Send', 'Mail.ReadWrite']

    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        if not access_token:
            return "Failed to obtain access token. Cannot fetch emails."

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        graph_url = f"{MS_GRAPH_BASE_URL}/me/mailFolders('inbox')/messages?$filter=isRead eq false&$top=10&$select=sender,subject,body,id"
        
        response = requests.get(graph_url, headers=headers)
        response.raise_for_status()

        data = response.json()
        messages = data.get('value', [])

        if not messages:
            return []

        emails = []
        for message in messages:
            sender_info = message.get('sender', {}).get('emailAddress', {})
            sender_name = sender_info.get('name', 'Unknown Sender')
            sender_address = sender_info.get('address', 'unknown@example.com')

            full_body_html = message.get('body', {}).get('content', '')
            soup = BeautifulSoup(full_body_html, 'html.parser')
            full_body_text = soup.get_text(separator='\n', strip=True)
            email_data = Email(
                sender=f"{sender_name} <{sender_address}>",
                subject=message.get('subject', 'No Subject'),
                body_preview=full_body_text, 
                message_id=message.get('id')
            )
            emails.append(email_data.model_dump())
        
        return emails

    except Exception as e:
        return f"An error occurred while fetching emails: {e}"
    

EMAIL_OUTLOOK_TOOLS = [
    get_unread_emails,
    send_email,
    reply_to_email,
    mark_email_as_read
]

# --- TEST BLOCK ---
def main():
    print("--- Starting Tool Test ---")
    
    # Step 1: Fetch unread emails to get a valid message_id
    print("\nFetching unread emails...")
    # Use .func to call the original Python function directly
    emails = get_unread_emails.func() 
    
    if isinstance(emails, str) or not emails:
        print("Test cannot proceed: No unread emails found or an error occurred.")
        print(f"Result: {emails}")
        return

    # Step 2: Take the first email and try to mark it as read
    first_email = emails[0]
    message_id_to_mark = first_email['message_id']
    
    print(f"\nFound email '{first_email['subject']}' from '{first_email['sender']}'.")
    print(f"Attempting to mark message with ID: {message_id_to_mark} as read...")
    
    # Step 3: Call the mark_email_as_read function
    status = mark_email_as_read.func(message_id=message_id_to_mark)
    
    print(f"\n--- Result ---")
    print(status)
    print("----------------")


if __name__ == "__main__":
    main()