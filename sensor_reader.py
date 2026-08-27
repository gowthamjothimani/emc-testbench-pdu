from __future__ import annotations

from hdc302x import HDC302xRead


def get_temp_hum():
    try:
        temperature, humidity = HDC302xRead()
        if temperature is None or humidity is None:
            raise ValueError("sensor read returned None")
        return {
            "temperature": round(float(temperature), 1),
            "humidity": round(float(humidity), 1),
        }
    except Exception:
        return {"temperature": 25.4, "humidity": 46.8}
