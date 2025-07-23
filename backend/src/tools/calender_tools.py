
from pydantic import BaseModel, Field, create_model
from typing import Optional, List
import os
from dotenv import load_dotenv
from src.utils.ms_graph import get_access_token , MS_GRAPH_BASE_URL
from langchain_core.tools import tool
import datetime
import requests
import pytz
from bs4 import BeautifulSoup

# --- Pydantic Input Schema for the Calendar Tool ---
# --- Dynamic Schema Generation Function ---
# def create_dynamic_calendar_input_schema() -> BaseModel:
#     """
#     Dynamically creates the Pydantic input model for get_calendar_events.
#     This function calculates the current date and timezone offset for the
#     'Europe/Berlin' timezone and injects it into the Field descriptions as an example.
#     """
#     try:
#         # 1. Calculate the dynamic info
#         local_tz = pytz.timezone("Europe/Berlin")
#         now_local = datetime.datetime.now(local_tz)
        
#         # Format the timezone offset correctly (e.g., +02:00)
#         tz_offset_str = now_local.strftime('%z')
#         if len(tz_offset_str) == 5: # Handles standard '+HHMM' format
#              tz_offset_str = f"{tz_offset_str[:3]}:{tz_offset_str[3:]}"
        
#         # Create date and full example strings
#         date_example = now_local.strftime('%Y-%m-%d')
#         start_example = f"{date_example}T00:00:00{tz_offset_str}"
#         end_example = f"{date_example}T23:59:59{tz_offset_str}"

#         # 2. Create the dynamic descriptions
#         start_desc = (
#             f"The start date for the event search. MUST be a timezone-aware ISO 8601 string. "
#             f"Example for the current user's timezone: '{start_example}'."
#         )
#         end_desc = (
#             f"The end date for the event search. MUST be a timezone-aware ISO 8601 string. "
#             f"Example for the current user's timezone: '{end_example}'."
#         )
#     except Exception as e:
#         # Fallback to static descriptions if pytz or datetime fails for any reason
#         print(f"Warning: Could not generate dynamic schema, falling back to static. Error: {e}")
#         start_desc = "The start date. Must be a timezone-aware ISO 8601 string (e.g., '2024-08-21T00:00:00+02:00')."
#         end_desc = "The end date. Must be a timezone-aware ISO 8601 string (e.g., '2024-08-21T23:59:59+02:00')."

#     # 3. Create the Pydantic model at runtime using the create_model factory
#     DynamicModel = create_model(
#         'GetCalendarEventsInput',  # The name of the new class
#         start_date=(Optional[str], Field(default=None, description=start_desc)),
#         end_date=(Optional[str], Field(default=None, description=end_desc)),
#         __base__=BaseModel # It must inherit from BaseModel
#     )
#     return DynamicModel

# # --- Assign the dynamically created model to the name the @tool decorator will use ---
# # This line executes when the module is first imported.
# GetCalendarEventsInput = create_dynamic_calendar_input_schema()

class CalendarEventsInput(BaseModel):
    start_date: str = Field(..., description=(
        "The start date for the event search. MUST be a timezone-aware ISO 8601 string. "
        "Example: '2024-08-21T00:00:00+02:00' for Berlin time."
    ))
    end_date: str = Field(..., description=(
        "The end date for the event search. MUST be a timezone-aware ISO 8601 string. "
        "Example: '2024-08-21T23:59:59+02:00'."
    ))
@tool(args_schema=CalendarEventsInput)
def get_calendar_events(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """
    Fetches detailed calendar events for a specific date range.
    IMPORTANT: This tool requires timezone-aware ISO 8601 strings for start_date and end_date.
    The agent is responsible for calculating these dates based on the current UTC time and the user's request.
    The output from this tool will be in the user's local timezone ('W. Europe Standard Time').

    Returns a detailed schedule of events in the specified date range, including:
    - Event ID
    - Subject
    - Start and end times (formatted) in timezone="W. Europe Standard Time"
    - Organizer and attendees
    - Description/body of the event (cleaned from HTML)
    - A summary of the schedule
    If no events are found, it returns a message indicating that.
    If an error occurs, it returns a detailed error message.

    """

    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scopes = ['User.Read', 'Mail.ReadWrite', 'Calendars.Read']

    print(f"Fetching calendar events from {start_date} to {end_date}...")

    print(start_date)

    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        if not access_token:
            return "Failed to obtain access token. Cannot fetch calendar events."

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Prefer': 'outlook.timezone="W. Europe Standard Time"'

        }

        if not start_date or not end_date:
            # Define the user's local timezone
            local_tz = pytz.timezone("Europe/Berlin")
            print(f"Using local timezone: {local_tz}")
            # Get the current time in that timezone
            now_local = datetime.datetime.now(local_tz)
            
            # Calculate the start and end of the day in the local timezone
            start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Convert these timezone-aware datetimes to ISO 8601 strings.
            # The API will receive the full datetime and timezone offset.
            start_date = start_of_day_local.isoformat()
            end_date = end_of_day_local.isoformat()
            print(f"Using default date range: {start_date} to {end_date}")

        base_graph_url = f"{MS_GRAPH_BASE_URL}/me/calendarview"
        
        # --- CHANGE 1: Add 'id' to the $select parameter ---
        # Although 'id' is often returned by default, explicitly asking for it is best practice.
        params = {
            'startDateTime': start_date,
            'endDateTime': end_date,
            '$select': 'id,subject,start,end,organizer,attendees,body', # Added 'id' here
            '$orderby': 'start/dateTime'
        }
        
        response = requests.get(base_graph_url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        events = data.get('value', [])

        if not events:
            return f"No events found between {start_date} and {end_date}."

        full_schedule = [f"Here is your detailed schedule for the requested period:"]
        
        for i, event in enumerate(events):
            full_schedule.append(f"\n--- Event {i+1} ---")

            # --- CHANGE 2: Get the event ID and add it to the output ---
            event_id = event.get('id', 'Not Found')
            subject = event.get('subject', 'No Subject')
            organizer_info = event.get('organizer', {}).get('emailAddress', {})
            organizer = f"{organizer_info.get('name', 'N/A')} <{organizer_info.get('address', 'N/A')}>"
            
            # Format time (no change here)
            start_time_str = event.get('start', {}).get('dateTime', '')
            end_time_str = event.get('end', {}).get('dateTime', '')
            try:
                start_dt = datetime.datetime.fromisoformat(start_time_str)
                end_dt = datetime.datetime.fromisoformat(end_time_str)
                formatted_time = f"{start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%H:%M')}"
            except ValueError:
                formatted_time = "All day"
            
            # Format attendees (no change here)
            attendees = event.get('attendees', [])
            attendee_list = [f"{a.get('emailAddress', {}).get('name')} <{a.get('emailAddress', {}).get('address')}>" for a in attendees]
            
            # Format body/description (no change here)
            body_html = event.get('body', {}).get('content', '')
            soup = BeautifulSoup(body_html, 'html.parser')
            body_text = soup.get_text(separator='\n', strip=True)

            # Append all details to the output string, including the ID
            full_schedule.append(f"ID: {event_id}") # <-- THE NEW LINE
            full_schedule.append(f"Subject: {subject}")
            full_schedule.append(f"Time: {formatted_time} (W. Europe Standard Time) ")
            full_schedule.append(f"Organizer: {organizer}")
            if attendee_list:
                full_schedule.append(f"Attendees:\n - " + "\n - ".join(attendee_list))
            if body_text:
                full_schedule.append(f"Description:\n{body_text}")
        
        full_schedule.append("\n--- End of Schedule ---")
        return "\n".join(full_schedule)

    except requests.exceptions.HTTPError as e:
        error_details = e.response.json()
        detailed_message = error_details.get('error', {}).get('message', 'No detailed message.')
        return f"An error occurred while fetching calendar events: {e}\nDetails: {detailed_message}"
    except Exception as e:
        return f"A general error occurred: {e}"


# --- Pydantic Input Schema for the Create Event Tool ---
class CreateCalendarEventInput(BaseModel):
    subject: str = Field(..., description="The subject or title of the event.")
    start_time: str = Field(..., description="The start time for the event in ISO 8601 format (e.g., '2024-08-21T10:00:00').")
    end_time: str = Field(..., description="The end time for the event in ISO 8601 format (e.g., '2024-08-21T11:00:00').")
    attendees: Optional[List[str]] = Field(default=None, description="A list of attendee email addresses to invite.")
    body: Optional[str] = Field(default=None, description="The body or description of the event. Can be plain text.")
    location: Optional[str] = Field(default=None, description="The location of the event (e.g., a physical address or a meeting link).")

# --- The New Create Calendar Event Tool ---
@tool(args_schema=CreateCalendarEventInput)
def create_calendar_event(subject: str, start_time: str, end_time: str, attendees: Optional[List[str]] = None, body: Optional[str] = None, location: Optional[str] = None) -> str:


    """
    Creates a new event in the user's Outlook calendar and sends invitations to attendees.
    """
    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    # Calendars.ReadWrite scope is essential for this operation
    scopes = ['User.Read', 'Mail.ReadWrite', 'Calendars.ReadWrite']

    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        if not access_token:
            return "Failed to obtain access token. Cannot create calendar event."

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Construct the event payload for the API
        event_payload = {
            "subject": subject,
            "body": {
                "contentType": "Text", # Assuming plain text body for simplicity
                "content": body or ""
            },
            "start": {
                "dateTime": start_time,
                "timeZone": "UTC" # It's best practice to create events in UTC
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "UTC"
            },
            "location": {
                "displayName": location or ""
            },
            "attendees": [
                {"emailAddress": {"address": email.strip()}, "type": "required"}
                for email in attendees
            ] if attendees else []
        }

        # API endpoint for creating events
        graph_url = f"{MS_GRAPH_BASE_URL}/me/events"

        response = requests.post(graph_url, headers=headers, json=event_payload)
        response.raise_for_status()

        return f"Successfully created event '{subject}' and sent invitations if any."

    except requests.exceptions.HTTPError as e:
        error_details = e.response.json()
        detailed_message = error_details.get('error', {}).get('message', 'No detailed message.')
        return f"An error occurred while creating the event: {e}\nDetails: {detailed_message}"
    except Exception as e:
        return f"A general error occurred: {e}"
    

# --- Pydantic Input Schema for the Update Event Tool ---
class UpdateCalendarEventInput(BaseModel):
    event_id: str = Field(..., description="The unique ID of the calendar event to update. This must be obtained first by using the 'get_calendar_events' tool.")
    new_subject: Optional[str] = Field(default=None, description="The new subject or title for the event.")
    new_start_time: Optional[str] = Field(default=None, description="The new start time in ISO 8601 format.")
    new_end_time: Optional[str] = Field(default=None, description="The new end time in ISO 8601 format.")
    add_attendees: Optional[List[str]] = Field(default=None, description="A list of NEW attendee email addresses to add to the event.")
    new_body: Optional[str] = Field(default=None, description="The new body or description for the event. This will REPLACE the old one.")
    new_location: Optional[str] = Field(default=None, description="The new location for the event.")
    cancel_event: bool = Field(default=False, description="Set to True to cancel and delete the event from the calendar.")

@tool(args_schema=UpdateCalendarEventInput)
def update_calendar_event(event_id: str, **kwargs) -> str:
    """
    Updates or cancels an existing calendar event using its unique ID.
    To get the event_id, first use the 'get_calendar_events' tool.
    Time-related arguments should be in ISO 8601 format. The event will be updated in 'W. Europe Standard Time' (Berlin/Paris).
    You can update specific fields like time, subject, or attendees, or cancel the event entirely.
    """
    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scopes = ['Calendars.ReadWrite']

    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        if not access_token:
            return "Failed to obtain access token."

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        graph_url = f"{MS_GRAPH_BASE_URL}/me/events/{event_id}"

        # --- Handle Cancellation (No change here) ---
        if kwargs.get('cancel_event'):
            response = requests.delete(graph_url, headers=headers)
            response.raise_for_status()
            return f"Successfully canceled and deleted event with ID: {event_id}."

        # --- Handle Updates ---
        update_payload = {}
        
        # Dynamically build the payload (no changes for subject, body, location)
        if kwargs.get('new_subject'):
            update_payload['subject'] = kwargs['new_subject']
        if kwargs.get('new_body'):
            update_payload['body'] = {"contentType": "Text", "content": kwargs['new_body']}
        if kwargs.get('new_location'):
            update_payload['location'] = {"displayName": kwargs['new_location']}
            
        # --- CHANGE: Apply the correct timezone when updating times ---
        time_zone = "W. Europe Standard Time"
        if kwargs.get('new_start_time'):
            update_payload['start'] = {"dateTime": kwargs['new_start_time'], "timeZone": time_zone}
        if kwargs.get('new_end_time'):
            update_payload['end'] = {"dateTime": kwargs['new_end_time'], "timeZone": time_zone}
        
        # --- Handle adding attendees (No change here) ---
        if kwargs.get('add_attendees'):
            # First, get the current list of attendees
            get_response = requests.get(graph_url + "?$select=attendees", headers=headers)
            get_response.raise_for_status()
            current_event = get_response.json()
            existing_attendees = current_event.get('attendees', [])

            # Add the new attendees to the existing list
            new_attendees_to_add = [{"emailAddress": {"address": email.strip()}, "type": "required"} for email in kwargs['add_attendees']]
            all_attendees = existing_attendees + new_attendees_to_add
            update_payload['attendees'] = all_attendees

        if not update_payload:
            return "No update information provided. Please specify what to change (e.g., new_start_time, add_attendees) or set cancel_event=True."

        # Use HTTP PATCH to update only the specified fields of the event
        response = requests.patch(graph_url, headers=headers, json=update_payload)
        response.raise_for_status()

        return f"Successfully updated event with ID: {event_id}."

    except requests.exceptions.HTTPError as e:
        detailed_message = e.response.json()
        return f"An error occurred while modifying the event: {e}\nDetails: {detailed_message}"
    except Exception as e:
        return f"A general error occurred: {e}"


def main():
    print("--- Testing create_calendar_event ---")
    
    # Define a new event to create
    # Let's schedule it for 2 days from now to avoid conflicts
    event_start_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)
    event_start_time = event_start_time.replace(hour=14, minute=0, second=0, microsecond=0) # Set to 2 PM UTC
    event_end_time = event_start_time + datetime.timedelta(hours=1) # 1 hour duration

    status = create_calendar_event.func(
        subject="AI Agent Test Event",
        start_time=event_start_time.isoformat(),
        end_time=event_end_time.isoformat(),
        attendees=["medyouness123@gmail.com"], # Add an attendee to test invitations
        body="This is a test event created by the AI personal agent's new tool.",
        location="Microsoft Teams"
    )
    
    print("\n--- Result ---")
    print(status)
    print("----------------")
    print("\nPlease check your Outlook calendar (and the attendee's inbox) to verify the event was created.")




if __name__ == "__main__":
    main()