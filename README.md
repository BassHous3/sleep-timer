# sleep-timer
A poor man's sleep timer for Jellyfin

This is just a small side-project, with a lot of room for improvement.  Feel free to submit Pull Requests.

## Summary
Becasue most Jellyfin clients do not have a "Still Watching?" feature, I created a work-around.  This app leverages events from the official Jellyfin Webhook Plugin to count the number of minutes after media started to play.  If content still playing after 120 minutes, this will ask user if still watching, if no interecation is commenced by the user, media will automatically stop playback at the end of it.

## Requirements
1. Start the docker container
2. Install the [Jellyfin Webhook Plugin](https://github.com/jellyfin/jellyfin-plugin-webhook)
3. Add a generic destination, with a Webhook URL of `http://{docker-address}:5553/webhook`
4. Choose the "Playback Start" Notification Type, choose the users who will use this sleep timer, and click the "Send All Properties (ignores template)" checkbox


## Docker Compose Example

Here is an example of how to use `sleep-timer` with Docker Compose:

```yaml
version: '3.8'

services:
  sleep-timer:
    image: joshjryan/jf-sleep-timer:latest
    container_name: jf-sleep-timer
    ports:
      - "5553:5553"
    environment:
      JELLYFIN_API_URL: "value1" # Required. Address of your jellyfin server (e.g. http://192.168.1.100:8096)
      JELLYFIN_API_TOKEN: "value2" # Required. API Key generated from your jellyfin server

      MAXIMUM_PLAYTIME_ALLOWED: 120 # Required. Timeout after 2 hours. Number of minutes after user is notified with "Are you watching?" and will stop from next media to play.

      MOVIES_ONLY: False # Required. Rule applies to Movies or Episodes? Both False = applies to both.
      EPISODES_ONLY: True

    restart: unless-stopped
```
