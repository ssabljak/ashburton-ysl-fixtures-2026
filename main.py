import requests
import json
import datetime
from urllib.parse import urlencode

def sync():
    # Load settings
    with open('config.json', 'r') as f:
        conf = json.load(f)

    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }
    
    # YOUR NEW CLOUDFLARE WORKER URL HERE
    MY_PROXY_URL = "https://dribl-proxy.steve-786.workers.dev/" 

    for team in conf['teams']:
        params = {**conf['common_params'], "league": team['league']}
        print(f"Syncing {team['name']} (Arrival: {team['arrival_offset']}m)...")
        
        try:
            # --- PROXY WRAPPER ---
            # Using private Cloudflare Worker to bypass GitHub IP block and Public Proxy timeouts
            dribl_url = f"https://mc-api.dribl.com/api/fixtures?{urlencode(params)}"
            res = requests.get(MY_PROXY_URL, params={"url": dribl_url}, headers=headers)
        
            if res.status_code != 200:
                print(f"Failed! Status Code: {res.status_code}. Response: {res.text[:100]}")
                continue
            
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
            dt_kickoff = datetime.datetime.strptime(attr['date'], "%Y-%m-%dT%H:%M:%S.%fZ")
            
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

            ics.extend([
                "BEGIN:VEVENT",
                f"UID:{item['hash_id']}@dribl",
                f"SUMMARY:{attr['name']}",
                f"DTSTART:{dt_kickoff.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%SZ')}",
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

if __name__ == "__main__":
    sync()
