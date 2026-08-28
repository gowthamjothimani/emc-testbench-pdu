from hdc302x import HDC302xRead


def get_temp_hum():
    try:
        temp, hum = HDC302xRead()
        if temp is None or hum is None:
            return {"error": "sensor read failed"}
        return {"temperature": round(temp, 1), "humidity": round(hum, 1)}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print(get_temp_hum())
