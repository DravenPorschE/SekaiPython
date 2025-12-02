import os
import requests
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# OpenWeather API endpoints
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

def _map_weather(main: str, clouds: Optional[int], weather_id: Optional[int]) -> str:
    """Map OpenWeather conditions to simple categories for Sekai robot"""
    main_lower = (main or "").lower()
    
    # Check weather ID for more accurate classification
    if weather_id is not None:
        if 200 <= weather_id < 600:  # Thunderstorm, drizzle, rain
            return "rainstorm"
        if 600 <= weather_id < 700:  # Snow
            return "snow"
    
    # Check main weather description
    if "clear" in main_lower:
        return "sunny"
    
    if "cloud" in main_lower:
        if clouds is None:
            return "cloudy"
        if clouds <= 25:
            return "sunny"
        if 25 < clouds <= 70:
            return "partly cloudy"
        return "cloudy"
    
    if "rain" in main_lower or "drizzle" in main_lower or "thunderstorm" in main_lower:
        return "rainstorm"
    
    if "mist" in main_lower or "fog" in main_lower or "haze" in main_lower:
        return "fog"
    
    return main_lower or "unknown"

def _ts_to_local_day(ts: int) -> str:
    """Convert Unix timestamp to day name (e.g., Monday, Tuesday)"""
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%A")

def get_weather_for_city_json(city: str,
                              api_key: Optional[str] = None,
                              units: str = "metric",
                              days_ahead: int = 4,
                              country_hint: Optional[str] = "PH") -> Dict[str, Any]:
    """
    Get weather data for a city from OpenWeather API (using standard endpoints).
    
    Args:
        city: City name (e.g., "Lipa", "Manila", "Batangas")
        api_key: OpenWeather API key (or set OPENWEATHER_API_KEY env var)
        units: "metric" (Celsius) or "imperial" (Fahrenheit)
        days_ahead: Number of forecast days (max 5)
        country_hint: Default country code (default "PH" for Philippines)
    
    Returns:
        Dictionary with current weather and forecast
    """
    # Get API key from environment if not provided
    if api_key is None:
        api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise ValueError("Missing OpenWeather API key. Set OPENWEATHER_API_KEY environment variable or pass api_key parameter.")

    # Build query with country hint
    q = city
    if country_hint and "," not in city:
        q = f"{city},{country_hint}"
    
    print(f"🔍 Fetching weather for: {q}")

    # Get current weather
    current_params = {
        "q": q,
        "units": units,
        "appid": api_key,
    }
    
    try:
        r = requests.get(WEATHER_URL, params=current_params, timeout=10)
        r.raise_for_status()
        current_data = r.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise ValueError(f"City not found: {city}. Try: 'Manila', 'Lipa', 'Batangas', or add country code like '{city},PH'")
        raise
    
    print(f"✅ Found: {current_data.get('name')}, {current_data.get('sys', {}).get('country')}")

    # Parse current weather
    cur_weather = current_data.get("weather", [{}])[0]
    result_current = {
        "date": datetime.fromtimestamp(current_data.get("dt", 0)).strftime("%Y-%m-%d"),
        "day": _ts_to_local_day(current_data.get("dt", 0)),
        "description": cur_weather.get("description"),
        "simple": _map_weather(
            cur_weather.get("main", ""),
            current_data.get("clouds", {}).get("all"),
            cur_weather.get("id")
        ),
        "temp": current_data.get("main", {}).get("temp"),
        "feels_like": current_data.get("main", {}).get("feels_like"),
        "humidity": current_data.get("main", {}).get("humidity"),
        "wind_speed": current_data.get("wind", {}).get("speed"),
    }

    # Get forecast data (5 day / 3 hour forecast)
    forecast_params = {
        "q": q,
        "units": units,
        "appid": api_key,
    }
    
    r = requests.get(FORECAST_URL, params=forecast_params, timeout=10)
    r.raise_for_status()
    forecast_data = r.json()

    # Process forecast - group by day and take midday readings
    forecast_by_day: Dict[str, Dict[str, Any]] = {}
    
    for item in forecast_data.get("list", []):
        dt = datetime.fromtimestamp(item.get("dt", 0))
        date_key = dt.strftime("%Y-%m-%d")
        hour = dt.hour
        
        # Skip today, only future days
        if date_key == datetime.now().strftime("%Y-%m-%d"):
            continue
        
        # Take the midday reading (around 12-15:00) as representative
        if date_key not in forecast_by_day or (12 <= hour <= 15):
            w = item.get("weather", [{}])[0]
            forecast_by_day[date_key] = {
                "date": date_key,
                "day": _ts_to_local_day(item.get("dt", 0)),
                "description": w.get("description"),
                "simple": _map_weather(
                    w.get("main", ""),
                    item.get("clouds", {}).get("all"),
                    w.get("id")
                ),
                "temp_day": item.get("main", {}).get("temp"),
                "temp_min": item.get("main", {}).get("temp_min"),
                "temp_max": item.get("main", {}).get("temp_max"),
                "pop": item.get("pop", 0),  # Probability of precipitation
            }
    
    # Convert to list and limit to requested days
    forecast_list = list(forecast_by_day.values())[:days_ahead]
    
    print(f"📅 Forecast days: {len(forecast_list)}")

    return {
        "city": current_data.get("name"),
        "country": current_data.get("sys", {}).get("country"),
        "units": units,
        "current": result_current,
        "forecast": forecast_list,
    }

# Command line interface for testing
if __name__ == "__main__":
    import argparse, sys
    
    parser = argparse.ArgumentParser(description="Get weather JSON for a city (OpenWeather API)")
    parser.add_argument("--city", "-c", required=True, help="City name (e.g., 'Lipa', 'Manila')")
    parser.add_argument("--api-key", "-k", help="OpenWeather API key (or set OPENWEATHER_API_KEY env var)")
    parser.add_argument("--days", "-d", type=int, default=4, help="Number of forecast days (max 5, default 4)")
    parser.add_argument("--units", "-u", default="metric", choices=["metric", "imperial"], help="Units: metric (Celsius) or imperial (Fahrenheit)")
    parser.add_argument("--simple", "-s", action="store_true", help="Show simplified output (for Sekai robot)")
    
    args = parser.parse_args()
    
    try:
        res = get_weather_for_city_json(
            args.city, 
            api_key=args.api_key, 
            days_ahead=args.days,
            units=args.units
        )
        
        if args.simple:
            # Simple output for Sekai robot - exact format needed
            print(f"\n📍 Location: {res['city']}, {res['country']}")
            print(f"📅 Date: {res['current']['date']}, Day: {res['current']['day']}, Weather: {res['current']['simple']}, Temp: {res['current']['temp']}°C")
            for f in res['forecast']:
                print(f"📅 Date: {f['date']}, Day: {f['day']}, Weather: {f['simple']}, Temp: {f['temp_day']}°C")
            print()
        else:
            # Full JSON output
            print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)