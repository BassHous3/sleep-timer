from flask import Flask, request, jsonify
import os
import time
import json
import requests
import urllib

JELLYFIN_API_URL = os.getenv("JELLYFIN_API_URL")
JELLYFIN_API_TOKEN = os.getenv("JELLYFIN_API_TOKEN")
MAXIMUM_PLAYTIME_ALLOWED = float(os.getenv("MAXIMUM_PLAYTIME_ALLOWED", 120))  # in minutes
CONFIRMATION_TIMEOUT = 60  # Time in seconds to wait for user confirmation

app = Flask(__name__)

# In-memory tracking
playback_tracker = {}

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Check the Content-Type header
        content_type = request.headers.get('Content-Type')
        
        if content_type == 'application/json':
            # Parse JSON payload
            event = request.json
        else:
            # Fall back to raw data and try to parse it
            event = json.loads(request.data.decode('utf-8'))

        # Debugging: Log the parsed payload
        #print("Parsed Payload:", event)

        # Extract key information
        notification_type = event.get("NotificationType")
        user_id = event.get("UserId")
        device_id = event.get("DeviceId")
        item_type = event.get("ItemType")
        
        # Store session object with nullable fields
        session = {
            "NotificationUsername": event.get("NotificationUsername", None),
            "Id": event.get("Id", None),  # The ID of the session to stop
            "DeviceName": event.get("DeviceName", None),
            "RemoteEndPoint": event.get("RemoteEndPoint", None)
        }

        key = f"{user_id}-{device_id}"

        if notification_type == "PlaybackStart":
            if key not in playback_tracker:
                playback_tracker[key] = {
                    "start_time": time.time(),
                    "last_activity": time.time(),
                    "confirmation_sent": False
                }
            else:
                # If confirmation was sent and user resumes playback, confirm they are still watching
                if playback_tracker[key]["confirmation_sent"]:
                    display_message(session['Id'], "Confirmed Still Watching", "Confirmation", 5000)
                    playback_tracker[key]["confirmation_sent"] = False
                    playback_tracker[key]["start_time"] = time.time()  # Reset the timer

                playback_tracker[key]["last_activity"] = time.time()

            print(f"ℹ️ PlaybackStart event received from user: {session.get('NotificationUsername', 'Unknown')}\n🌐 Device Address: {session.get('RemoteEndPoint', 'Unknown')}")

        elif notification_type == "PlaybackStop":
            if key in playback_tracker:
                del playback_tracker[key]
                print(f"ℹ️ PlaybackStop event received from user: {session.get('NotificationUsername', 'Unknown')}\n🌐 Device Address: {session.get('RemoteEndPoint', 'Unknown')}")

        # Check if the maximum playtime has been exceeded
        if key in playback_tracker:
            elapsed_time = (time.time() - playback_tracker[key]["start_time"]) / 60  # Convert to minutes
            if elapsed_time >= MAXIMUM_PLAYTIME_ALLOWED:
                if not playback_tracker[key]["confirmation_sent"]:
                    # Send "Are you still watching?" message
                    display_message(session['Id'], "Are you still watching?", "Confirmation", CONFIRMATION_TIMEOUT * 1000)
                    playback_tracker[key]["confirmation_sent"] = True
                    playback_tracker[key]["confirmation_time"] = time.time()
                else:
                    # Check if the confirmation timeout has passed
                    if time.time() - playback_tracker[key]["confirmation_time"] > CONFIRMATION_TIMEOUT:
                        if stop_playback(session):
                            del playback_tracker[key]
                            return jsonify({"message": "Playback stopped due to inactivity"}), 200
                        else:
                            return jsonify({"message": "Failed to stop playback"}), 500

    except Exception as e:
        print("Error processing webhook:", e)
        return jsonify({"message": "Error processing request"}), 500

    return jsonify({"message": "Event processed"}), 200


def stop_playback(session):
    """
    Stop playback for a given session ID using the Jellyfin API.
    """
    session_id = session['Id']
    display_message(session_id, 'Stopping Playback', 'Sleep Timer', 7000)

    time.sleep(5)

    try:
        # Construct the URL to stop playback
        stop_url = f"{JELLYFIN_API_URL}/Sessions/{session_id}/Playing/Stop?ApiKey={JELLYFIN_API_TOKEN}"
        
        # Send the request to stop playback
        req = urllib.request.urlopen(urllib.request.Request(stop_url, method="POST"))
        print(f"👤 {session.get('NotificationUsername', 'Unknown')} has exceeded the maximum playtime.\n❗️ ⏹️ Stopping Playback ❗️\n🌐 Device Address: {session.get('RemoteEndPoint', 'Unknown')}")
        print()

        # Wait for 2 seconds before sending the next command
        time.sleep(2)

        # Construct the URL to send the 'GoHome' command
        go_home_url = f"{JELLYFIN_API_URL}/Sessions/{session_id}/Command/GoHome?ApiKey={JELLYFIN_API_TOKEN}"
        
        # Send the request to navigate back to the home screen
        req = urllib.request.urlopen(urllib.request.Request(go_home_url, method="POST"))

        return True
    except Exception as e:
        print(f"Error stopping playback for session {session_id}: {e}")
        return False

def display_message(session_id, message, header="Notice", timeout_ms=5000):
    """
    Send a display message to the Jellyfin client.
    
    Args:
        session_id (str): The session ID of the client.
        message (str): The message to display.
        header (str): The header for the message.
        timeout_ms (int): Time in milliseconds to display the message.
    """
    try:
        # Construct the URL for the DisplayMessage command
        display_message_url = f"{JELLYFIN_API_URL}/Sessions/{session_id}/Command"
        headers = {
            "Authorization": f"MediaBrowser Token={JELLYFIN_API_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "Name": "DisplayMessage",
            "Arguments": {
                "Header": header,
                "Text": message,
                "TimeoutMs": timeout_ms
            }
        }

        # Send the display message
        req = urllib.request.Request(display_message_url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
        urllib.request.urlopen(req)

    except Exception as e:
        print(f"Error sending display message to session {session_id}: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5553)
