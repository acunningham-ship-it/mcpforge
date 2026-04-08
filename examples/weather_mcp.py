#!/usr/bin/env python3
"""MCP server for weather data via wttr.in — free, no auth required."""

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather")
BASE_URL = "https://wttr.in"


@mcp.tool()
def get_weather(city: str, units: str = "metric") -> dict:
    """Get current weather conditions for a city.

    Args:
        city: City name (e.g. 'London', 'New York', 'Tokyo').
        units: 'metric' (Celsius) or 'imperial' (Fahrenheit).

    Returns:
        Current temperature, feels-like, humidity, wind speed, and description.
    """
    fmt = "j1"  # JSON format
    resp = httpx.get(
        f"{BASE_URL}/{city}",
        params={"format": fmt},
        headers={"Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    current = data["current_condition"][0]
    use_fahrenheit = units == "imperial"

    temp = current.get("temp_F" if use_fahrenheit else "temp_C", "N/A")
    feels_like = current.get("FeelsLike" + ("F" if use_fahrenheit else "C"), "N/A")
    unit_label = "°F" if use_fahrenheit else "°C"

    nearest = data.get("nearest_area", [{}])[0]
    location_name = nearest.get("areaName", [{}])[0].get("value", city)
    country = nearest.get("country", [{}])[0].get("value", "")

    return {
        "location": f"{location_name}, {country}".strip(", "),
        "temperature": f"{temp}{unit_label}",
        "feels_like": f"{feels_like}{unit_label}",
        "humidity": f"{current.get('humidity', 'N/A')}%",
        "wind_speed": f"{current.get('windspeedKmph', 'N/A')} km/h",
        "wind_direction": current.get("winddir16Point", "N/A"),
        "description": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
        "visibility": f"{current.get('visibility', 'N/A')} km",
        "uv_index": current.get("uvIndex", "N/A"),
    }


@mcp.tool()
def get_forecast(city: str, days: int = 3, units: str = "metric") -> dict:
    """Get a multi-day weather forecast for a city.

    Args:
        city: City name (e.g. 'Paris', 'Sydney').
        days: Number of forecast days (1–3, wttr.in provides up to 3).
        units: 'metric' (Celsius) or 'imperial' (Fahrenheit).

    Returns:
        Daily forecast with high/low temperatures, sunrise/sunset, and hourly summaries.
    """
    days = max(1, min(days, 3))  # Clamp to 1-3
    resp = httpx.get(
        f"{BASE_URL}/{city}",
        params={"format": "j1"},
        headers={"Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    use_fahrenheit = units == "imperial"
    unit_label = "°F" if use_fahrenheit else "°C"
    max_key = "maxtempF" if use_fahrenheit else "maxtempC"
    min_key = "mintempF" if use_fahrenheit else "mintempC"

    weather_days = data.get("weather", [])[:days]
    forecast = []
    for day in weather_days:
        hourly_summaries = []
        for h in day.get("hourly", []):
            time_str = h.get("time", "0").zfill(4)
            hour = f"{time_str[:2]}:{time_str[2:]}" if len(time_str) == 4 else time_str
            desc = h.get("weatherDesc", [{}])[0].get("value", "")
            t = h.get("tempF" if use_fahrenheit else "tempC", "?")
            hourly_summaries.append({"time": hour, "temp": f"{t}{unit_label}", "desc": desc})

        forecast.append({
            "date": day.get("date", ""),
            "max_temp": f"{day.get(max_key, 'N/A')}{unit_label}",
            "min_temp": f"{day.get(min_key, 'N/A')}{unit_label}",
            "sunrise": day.get("astronomy", [{}])[0].get("sunrise", "N/A"),
            "sunset": day.get("astronomy", [{}])[0].get("sunset", "N/A"),
            "hourly": hourly_summaries,
        })

    nearest = data.get("nearest_area", [{}])[0]
    location_name = nearest.get("areaName", [{}])[0].get("value", city)
    country = nearest.get("country", [{}])[0].get("value", "")

    return {
        "location": f"{location_name}, {country}".strip(", "),
        "days_requested": days,
        "forecast": forecast,
    }


if __name__ == "__main__":
    mcp.run()
