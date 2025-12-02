
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
from zoneinfo import ZoneInfo

IANA_TO_WINDOWS = {
    "Europe/Berlin": "W. Europe Standard Time",
}

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


class CreateCalendarEventInput(BaseModel):
    subject: str = Field(..., description="Event title.")
    # Allow plain local wall-time; we'll apply time_zone
    start_time: str = Field(..., description="Local start in ISO without tz (e.g. '2025-09-09T13:00:00') or with tz.")
    end_time: str   = Field(..., description="Local end in ISO without tz or with tz.")
    time_zone: str  = Field(default="Europe/Berlin", description="IANA time zone of the provided times.")
    attendees: Optional[List[str]] = None
    body: Optional[str] = None
    location: Optional[str] = None


@tool(args_schema=CreateCalendarEventInput)
def create_calendar_event(subject: str,
                          start_time: str,
                          end_time: str,
                          time_zone: str = "Europe/Berlin",
                          attendees: Optional[List[str]] = None,
                          body: Optional[str] = None,
                          location: Optional[str] = None) -> str:
    """
    Creates an Outlook event. Treats `start_time`/`end_time` as local times in `time_zone`
    (if no offset is present) and sends them with the correct Outlook timeZone so that
    13:00 stays 13:00 in the user's calendar, including DST.
    """
    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scopes = ['User.Read', 'Mail.ReadWrite', 'Calendars.ReadWrite']

    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        if not access_token:
            return "Failed to obtain access token. Cannot create calendar event."

        iana_tz = time_zone
        windows_tz = IANA_TO_WINDOWS.get(iana_tz, "W. Europe Standard Time")
        tzinfo = ZoneInfo(iana_tz)

        def normalize(dt_str: str) -> str:
            dt = datetime.datetime.fromisoformat(dt_str)
            # If naive, assume it's in the provided local tz (NOT UTC)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tzinfo)
            else:
                # Convert any provided tz to the chosen local tz for stable display
                dt = dt.astimezone(tzinfo)
            # Graph expects the local wall time string without offset + separate timeZone
            return dt.strftime("%Y-%m-%dT%H:%M:%S")

        start_local = normalize(start_time)
        end_local   = normalize(end_time)

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Prefer': f'outlook.timezone="{windows_tz}"'
        }

        event_payload = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body or ""},
            "start": {"dateTime": start_local, "timeZone": windows_tz},
            "end":   {"dateTime": end_local,   "timeZone": windows_tz},
            "location": {"displayName": location or ""},
            "attendees": [
                {"emailAddress": {"address": email.strip()}, "type": "required"}
                for email in (attendees or [])
            ]
        }

        graph_url = f"{MS_GRAPH_BASE_URL}/me/events"
        response = requests.post(graph_url, headers=headers, json=event_payload)
        response.raise_for_status()
        return f"Successfully created event '{subject}'."

    except requests.exceptions.HTTPError as e:
        try:
            detailed_message = e.response.json().get('error', {}).get('message', '')
        except Exception:
            detailed_message = e.response.text
        return f"An error occurred while creating the event: {e}\nDetails: {detailed_message}"
    except Exception as e:
        return f"A general error occurred: {e}"


class UpdateCalendarEventInput(BaseModel):
    event_id: str
    new_subject: Optional[str] = None
    new_start_time: Optional[str] = None  # local wall-time or tz-aware
    new_end_time: Optional[str] = None
    time_zone: str = Field(default="Europe/Berlin", description="IANA tz for provided times.")
    add_attendees: Optional[List[str]] = None
    new_body: Optional[str] = None
    new_location: Optional[str] = None
    cancel_event: bool = False


@tool(args_schema=UpdateCalendarEventInput)
def update_calendar_event(event_id: str, **kwargs) -> str:
    """
    Updates or cancels an existing calendar event in Outlook.
    Accepts new times, subject, body, attendees, or cancellation.
    All times should be given in ISO 8601 format (naive = local in the given time_zone).
    """

    load_dotenv()
    application_id = os.getenv("APPLICATION_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    scopes = ['Calendars.ReadWrite']

    try:
        access_token = get_access_token(application_id, client_secret, scopes)
        if not access_token:
            return "Failed to obtain access token."

        iana_tz = kwargs.get('time_zone', 'Europe/Berlin')
        windows_tz = IANA_TO_WINDOWS.get(iana_tz, "W. Europe Standard Time")
        tzinfo = ZoneInfo(iana_tz)

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Prefer': f'outlook.timezone="{windows_tz}"'
        }
        graph_url = f"{MS_GRAPH_BASE_URL}/me/events/{event_id}"

        if kwargs.get('cancel_event'):
            r = requests.delete(graph_url, headers=headers)
            r.raise_for_status()
            return f"Successfully canceled and deleted event with ID: {event_id}."

        def normalize(dt_str: str) -> str:
            dt = datetime.datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tzinfo)
            else:
                dt = dt.astimezone(tzinfo)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")

        update_payload = {}
        if kwargs.get('new_subject'):
            update_payload['subject'] = kwargs['new_subject']
        if kwargs.get('new_body'):
            update_payload['body'] = {"contentType": "Text", "content": kwargs['new_body']}
        if kwargs.get('new_location'):
            update_payload['location'] = {"displayName": kwargs['new_location']}
        if kwargs.get('new_start_time'):
            update_payload['start'] = {"dateTime": normalize(kwargs['new_start_time']), "timeZone": windows_tz}
        if kwargs.get('new_end_time'):
            update_payload['end'] = {"dateTime": normalize(kwargs['new_end_time']), "timeZone": windows_tz}

        if kwargs.get('add_attendees'):
            get_resp = requests.get(graph_url + "?$select=attendees", headers=headers)
            get_resp.raise_for_status()
            existing = get_resp.json().get('attendees', [])
            new_att = [{"emailAddress": {"address": a.strip()}, "type": "required"} for a in kwargs['add_attendees']]
            update_payload['attendees'] = existing + new_att

        if not update_payload:
            return "No update information provided."

        r = requests.patch(graph_url, headers=headers, json=update_payload)
        r.raise_for_status()
        return f"Successfully updated event with ID: {event_id}."

    except requests.exceptions.HTTPError as e:
        try:
            detailed = e.response.json()
        except Exception:
            detailed = {"raw": e.response.text}
        return f"An error occurred while modifying the event: {e}\nDetails: {detailed}"
    except Exception as e:
        return f"A general error occurred: {e}"


CALENDAR_OUTLOOK_TOOLS = [
    get_calendar_events,
    create_calendar_event,
    update_calendar_event
]
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