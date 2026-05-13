def parse_status_msg(msg: str) -> dict:
    """
    Soporta dos formatos:

    Formato legacy:
        STATUS:0:REC:nombre:SEC:1:VT:10.0:POS:0.00

    Formato STM32 nuevo:
        STATUS:STATE:HOME_OK:SYNC:0:ENC:0:VT_x100:0:POS:0:POS_MM_x100:0
    """
    try:
        if not msg:
            return {}

        msg = msg.strip()

        # Por si alguna línea llega copiada desde logs como: <<< STATUS:...
        if msg.startswith("<<<"):
            msg = msg.replace("<<<", "", 1).strip()

        if not msg.startswith("STATUS:"):
            return {}

        resto = msg[7:]
        parts = resto.split(":")
        if not parts:
            return {}

        # Nuevo formato STM32:
        # STATUS:STATE:HOME_OK:SYNC:0:ENC:0...
        if parts[0] == "STATE":
            result = {"_formato": "stm32_mm"}

            i = 0
            while i < len(parts) - 1:
                key = parts[i]
                val = parts[i + 1] if i + 1 < len(parts) else ""

                if key:
                    result[key] = val

                i += 2

            result["_estado"] = result.get("STATE", "UNKNOWN")
            return result

        # Formato legacy:
        # STATUS:0:REC:...
        result = {
            "_formato": "legacy",
            "_estado": parts[0],
        }

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