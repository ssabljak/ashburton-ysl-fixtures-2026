import requests
import json
import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from collections import Counter

def sync():
    # Load settings
    with open('config.json', 'r') as f:
        conf = json.load(f)

    # Set our local timezone anchor
    local_tz = ZoneInfo("Australia/Melbourne")

    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }
    
    # Your private Cloudflare Worker URL
    MY_PROXY_URL = "https://dribl-proxy.steve-786.workers.dev/" 

    for team in conf['teams']:
        params = {**conf['common_params'], "league": team['league']}
        print(f"Syncing {team['name']} (Arrival: {team['arrival_offset']}m)...")
        
        try:
            # --- PROXY WRAPPER ---
            # Route through private Worker to bypass GitHub IP block
            dribl_url = f"https://mc-api.dribl.com/api/fixtures?{urlencode(params)}"
            res = requests.get(MY_PROXY_URL, params={"url": dribl_url}, headers=headers)
        
            if res.status_code != 200:
                print(f"Failed! Status Code: {res.status_code}. Response: {res.text[:100]}")
                continue
            
            # Parse the direct JSON from your worker
            data = res.json()
            
        except Exception as e:
            print(f"Error fetching {team['name']}: {e}")
            continue

        ics = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"X-WR-CALNAME:{team['name']} Fixtures",
            "METHOD:PUBLISH",
            "X-PUBLISHED-TTL:PT12H"
        ]

        for item in data['data']:
            attr = item['attributes']
            
            # --- TIMEZONE WRANGLING ---
            # 1. Parse Dribl UTC string
            dt_utc = datetime.datetime.strptime(attr['date'], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)
            # 2. Convert to Melbourne local time
            dt_kickoff = dt_utc.astimezone(local_tz)
            
            # --- BYE HANDLING ---
            if attr.get('bye_flag'):
                date_str = dt_kickoff.strftime("%Y%m%d")
                ics.extend([
                    "BEGIN:VEVENT",
                    f"UID:bye-{item['hash_id']}@dribl",
                    f"SUMMARY:BYE - {team['name']}",
                    f"DTSTART;VALUE=DATE:{date_str}",
                    f"DTEND;VALUE=DATE:{(dt_kickoff + datetime.timedelta(days=1)).strftime('%Y%m%d')}",
                    "TRANSP:TRANSPARENT",
                    f"DESCRIPTION:Round {attr['full_round']}: No match.",
                    "END:VEVENT"
                ])
                continue

            # --- DURATION & TIMES ---
            total_duration = team['duration'] + conf['halftime_mins'] + conf['post_match_buffer_mins']
            dt_end = dt_kickoff + datetime.timedelta(minutes=total_duration)
            dt_arrival = dt_kickoff - datetime.timedelta(minutes=team['arrival_offset'])

            # --- SMART PREP ALERT LOGIC ---
            if dt_kickoff.hour < conf['smart_alerts']['morning_cutoff_hour']:
                # Set to 8pm the night before
                dt_prep = dt_kickoff.replace(hour=conf['smart_alerts']['night_before_hour'], minute=0) - datetime.timedelta(days=1)
            else:
                # Set to 4 hours before kickoff
                dt_prep = dt_kickoff - datetime.timedelta(minutes=conf['smart_alerts']['prep_offset_mins'])
            
            prep_delta_mins = int((dt_kickoff - dt_prep).total_seconds() / 60)

            # --- MATCH EVENT ---
            location = f"{attr['ground_name']} - {attr['field_name']}" if attr['ground_name'] else "TBA"

            # Use TZID to ensure global accuracy while maintaining local convenience
            ics.extend([
                "BEGIN:VEVENT",
                f"UID:{item['hash_id']}@dribl",
                f"SUMMARY:{attr['name']}",
                f"DTSTART;TZID=Australia/Melbourne:{dt_kickoff.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID=Australia/Melbourne:{dt_end.strftime('%Y%m%dT%H%M%S')}",
                f"LOCATION:{location}",
                f"DESCRIPTION:Arrival: {dt_arrival.strftime('%I:%M %p')} ({team['arrival_offset']}m prior)\\nRound: {attr['full_round']}",
                # Alert 1: Prep
                "BEGIN:VALARM",
                f"TRIGGER:-PT{prep_delta_mins}M",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Match Prep: {team['name']}",
                "END:VALARM",
                # Alert 2: Arrival
                "BEGIN:VALARM",
                f"TRIGGER:-PT{team['arrival_offset']}M",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Arrival at Pitch: {team['name']}",
                "END:VALARM",
                "END:VEVENT"
            ])

        ics.append("END:VCALENDAR")
        filename = f"{team['name'].lower().replace(' ', '_')}.ics"
        with open(filename, 'w') as f:
            f.write("\n".join(ics))

        # --- GENERATE LANDING PAGE ---
        try:
            with open('template.html', 'r') as f:
                html_content = f.read()
    
            team_rows = ""
            for team in conf['teams']:
                fname = f"{team['name'].lower().replace(' ', '_')}.ics"
                team_rows += f'''
                <div class="team-card">
                    <div class="team-info">{team['name']}</div>
                    <button class="btn" onclick="subscribe('{fname}')">Add to Calendar</button>
                </div>'''
    
            # Replace placeholders
            timestamp = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
            html_content = html_content.replace("{{TEAMS}}", team_rows)
            html_content = html_content.replace("{{TIMESTAMP}}", timestamp)
    
            with open("index.html", "w") as f:
                f.write(html_content)
            print("Successfully generated index.html")
            
        except FileNotFoundError:
            print("Error: template.html not found. Skipping HTML generation.")

        all_logos = []
    
        # First, collect every logo URL from every fixture in every team
        for team in conf['teams']:
            # ... (your existing requests logic) ...
            data = res.json()
            
            for item in data.get('data', []):
                attr = item.get('attributes', {})
                if attr.get('home_logo'):
                    all_logos.append(attr['home_logo'])
                if attr.get('away_logo'):
                    all_logos.append(attr['away_logo'])
    
        # Now, find the most frequent one
        if all_logos:
            most_common_logo, count = Counter(all_logos).most_common(1)[0]
            print(f"Most frequent logo found ({count} occurrences): {most_common_logo}")
            
            try:
                img_res = requests.get(MY_PROXY_URL, params={"url": most_common_logo}, stream=True)
                if img_res.status_code == 200:
                    with open("logo.png", 'wb') as f:
                        f.write(img_res.content)
                    print("Successfully saved winner logo as logo.png")
            except Exception as e:
                print(f"Failed to download winner logo: {e}")

if __name__ == "__main__":
    sync()
