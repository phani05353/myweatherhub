from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime
import pytz
from suntime import Sun

app = Flask(__name__)
# NWS requires a User-Agent with contact info
HEADERS = {'User-Agent': '(MyHomeLab, maruthi.phanikumar@yopmail.com)'}

def calculate_feels_like(temp_f, humidity, wind_speed_mph):
    if temp_f <= 50 and wind_speed_mph > 3:
        v = pow(wind_speed_mph, 0.16)
        return 35.74 + (0.6215 * temp_f) - (35.75 * v) + (0.4275 * temp_f * v)
    if temp_f >= 80:
        T, R = temp_f, humidity
        hi = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (R * 0.094))
        if hi > 80:
            hi = -42.379 + 2.04901523*T + 10.14333127*R - 0.22475541*T*R - \
                 0.00683783*T*T - 0.05481717*R*R + 0.00122874*T*T*R + \
                 0.00085282*T*R*R - 0.00000199*T*T*R*R
        return hi
    return temp_f

def get_env_data(lat, lon):
    try:
        url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=us_aqi,uv_index&timezone=auto"
        resp = requests.get(url, timeout=5).json()
        return resp.get('current', {})
    except:
        return {"us_aqi": "N/A", "uv_index": "N/A"}

def get_weather_data(lat, lon):
    try:
        lat_f, lon_f = round(float(lat), 4), round(float(lon), 4)
        meta_resp = requests.get(f"https://api.weather.gov/points/{lat_f},{lon_f}", headers=HEADERS, timeout=5)
        if meta_resp.status_code != 200: return None
        
        prop = meta_resp.json()['properties']
        daily_resp = requests.get(prop['forecast'], headers=HEADERS).json()
        hourly_resp = requests.get(prop['forecastHourly'], headers=HEADERS).json()
        
        obs_data = {}
        try:
            stations = requests.get(prop['observationStations'], headers=HEADERS).json()
            if stations.get('features'):
                st_id = stations['features'][0]['properties']['stationIdentifier']
                obs_resp = requests.get(f"https://api.weather.gov/stations/{st_id}/observations/latest", headers=HEADERS).json()
                obs_data = obs_resp.get('properties', {})
        except: pass

        active_alerts = []
        try:
            alerts_url = f"https://api.weather.gov/alerts/active?point={lat_f},{lon_f}"
            alerts_resp = requests.get(alerts_url, headers=HEADERS, timeout=3).json()
            active_alerts = alerts_resp.get('features', [])
        except: pass

        current = hourly_resp['properties']['periods'][0]
        temp = current['temperature']
        
        humid_data = current.get('relativeHumidity', {})
        humid = humid_data.get('value') if (humid_data and humid_data.get('value') is not None) else 50
        
        wind_raw = str(current.get('windSpeed', '0')).lower()
        if 'to' in wind_raw:
            wind_str = wind_raw.split('to')[-1].strip().split(' ')[0]
        else:
            wind_str = wind_raw.split(' ')[0]
        wind_val = float(wind_str) if wind_str.replace('.','',1).isdigit() else 0
        
        raw_p = obs_data.get('barometricPressure', {}).get('value')
        pressure_inhg = round(raw_p * 0.0002953, 2) if raw_p else "N/A"

        sun = Sun(lat_f, lon_f)
        eastern_tz = pytz.timezone('US/Eastern')
        sunrise_local = sun.get_sunrise_time().astimezone(eastern_tz)
        sunset_local = sun.get_sunset_time().astimezone(eastern_tz)

        env_data = get_env_data(lat_f, lon_f)

        daily_forecasts = []
        periods = daily_resp['properties']['periods']
        for i in range(0, min(len(periods), 14), 2):
            day = periods[i]
            night = periods[i+1] if i+1 < len(periods) else day
            daily_forecasts.append({
                "name": day['name'], "icon": day['shortForecast'],
                "high": day['temperature'], "low": night['temperature']
            })

        city_camel = prop['relativeLocation']['properties']['city'].title()
        state = prop['relativeLocation']['properties']['state']

        return {
            "location": f"{city_camel}, {state}",
            "current": current,
            "feels_like": round(calculate_feels_like(temp, humid, wind_val)),
            "wind": {"speed": wind_val, "direction": current.get('windDirection')},
            "pressure": pressure_inhg,
            "aqi": env_data.get('us_aqi'),
            "uv": env_data.get('uv_index'),
            "daily": daily_forecasts,
            "hourly": hourly_resp['properties']['periods'][:24],
            "alerts": active_alerts,
            "sun": {
                "sunrise": sunrise_local.strftime("%I:%M %p"),
                "sunset": sunset_local.strftime("%I:%M %p")
            },
            "updated": datetime.now(eastern_tz).strftime("%I:%M %p"),
            "lat": lat_f, "lon": lon_f
        }
    except Exception as e:
        print(f"Error: {e}")
        return None

@app.route('/')
def home(): return render_template('index.html')

@app.route('/weather_data', methods=['POST'])
def weather_data():
    coords = request.get_json()
    data = get_weather_data(coords['lat'], coords['lon'])
    return jsonify(data) if data else ("API Error", 500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)