from flask import Flask, request, jsonify
import os
import time
import json
import urllib

JELLYFIN_API_URL = os.getenv("JELLYFIN_API_URL")
JELLYFIN_API_TOKEN = os.getenv("JELLYFIN_API_TOKEN")
MAXIMUM_PLAYTIME_ALLOWED = float(os.getenv("MAXIMUM_PLAYTIME_ALLOWED", 120))  # in minutes
CONFIRMATION_TIMEOUT = 60  # Time in seconds to wait for user confirmation
MOVIES_ONLY = os.getenv("MOVIES_ONLY", "False").lower() == "true"
EPISODES_ONLY = os.getenv("EPISODES_ONLY", "False").lower() == "true"

app = Flask(__name__)

# In-memory tracking
playback_tracker = {}

def should_apply_rules(item_type):
    """Determine if rules should apply based on media type and settings"""
    if MOVIES_ONLY:
        return item_type == "Movie"
    if EPISODES_ONLY:
        return item_type == "Episode"
    return True  # Both if neither is set

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        content_type = request.headers.get('Content-Type')
        event = request.json if content_type == 'application/json' else json.loads(request.data.decode('utf-8'))

        notification_type = event.get("NotificationType")
        user_id = event.get("UserId")
        device_id = event.get("DeviceId")
        item_type = event.get("ItemType")
        
        session = {
            "NotificationUsername": event.get("NotificationUsername", None),
            "Id": event.get("Id", None),
            "DeviceName": event.get("DeviceName", None),
            "RemoteEndPoint": event.get("RemoteEndPoint", None),
            "ItemType": item_type
        }

        key = f"{user_id}-{device_id}"

        if notification_type == "PlaybackStart":
            if not should_apply_rules(item_type):
                if key in playback_tracker:
                    del playback_tracker[key]
                return jsonify({"message": "Rules not applied for this media type"}), 200

            if key in playback_tracker and playback_tracker[key].get("block_autoplay"):
                # Stop autoplay if block is active
                if stop_playback(session):
                    del playback_tracker[key]
                    return jsonify({"message": "Autoplay blocked"}), 200
                else:
                    return jsonify({"message": "Failed to block autoplay"}), 500

            if key not in playback_tracker:
                playback_tracker[key] = {
                    "start_time": time.time(),
                    "last_activity": time.time(),
                    "confirmation_sent": False,
                    "item_type": item_type,
                    "block_autoplay": False
                }
            else:
                if playback_tracker[key]["confirmation_sent"]:
                    # User resumed playback after confirmation prompt
                    display_message(session['Id'], "Confirmed Still Watching", "Confirmation", 5000)
                    playback_tracker[key] = {
                        "start_time": time.time(),
                        "last_activity": time.time(),
                        "confirmation_sent": False,
                        "item_type": item_type,
                        "block_autoplay": False
                    }
                else:
                    playback_tracker[key]["last_activity"] = time.time()

            print(f"ℹ️ PlaybackStart: {session.get('NotificationUsername', 'Unknown')} | Media: {item_type}")

        elif notification_type == "PlaybackStop":
            if key in playback_tracker:
                del playback_tracker[key]
                print(f"ℹ️ PlaybackStop: {session.get('NotificationUsername', 'Unknown')}")

        # Check active sessions
        if key in playback_tracker and not playback_tracker[key]["block_autoplay"]:
            elapsed_time = (time.time() - playback_tracker[key]["start_time"]) / 60  # minutes
            if elapsed_time >= MAXIMUM_PLAYTIME_ALLOWED:
                if not playback_tracker[key]["confirmation_sent"]:
                    display_message(session['Id'], "Are you still watching?", "Confirmation", CONFIRMATION_TIMEOUT * 1000)
                    playback_tracker[key]["confirmation_sent"] = True
                    playback_tracker[key]["confirmation_time"] = time.time()
                else:
                    if time.time() - playback_tracker[key]["confirmation_time"] > CONFIRMATION_TIMEOUT:
                        # Allow current media to finish, block next autoplay
                        playback_tracker[key]["block_autoplay"] = True
                        print(f"⚠️ Autoplay blocked for {session.get('NotificationUsername', 'Unknown')}")

    except Exception as e:
        print("Error processing webhook:", e)
        return jsonify({"message": "Error processing request"}), 500

    return jsonify({"message": "Event processed"}), 200

def stop_playback(session):
    try:
        session_id = session['Id']
        # Immediate stop command
        stop_url = f"{JELLYFIN_API_URL}/Sessions/{session_id}/Playing/Stop?ApiKey={JELLYFIN_API_TOKEN}"
        urllib.request.urlopen(urllib.request.Request(stop_url, method="POST"))
        print(f"⏹️ Stopped playback for {session.get('NotificationUsername', 'Unknown')}")
        return True
    except Exception as e:
        print(f"Error stopping playback: {e}")
        return False

def display_message(session_id, message, header="Notice", timeout_ms=5000):
    try:
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
        req = urllib.request.Request(display_message_url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5553)
