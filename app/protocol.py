def parse_status_msg(msg: str) -> dict:
    try:
        if not msg.startswith("STATUS:"):
            return {}

        resto = msg[7:]
        parts = resto.split(":")
        if not parts:
            return {}

        result = {"_estado": parts[0]}
        i = 1
        while i < len(parts) - 1:
            key = parts[i]
            val = parts[i + 1] if i + 1 < len(parts) else ""
            if key:
                result[key] = val
            i += 2

        return result
    except Exception as e:
        print(f"parse_status_msg error: {e}")
        return {}