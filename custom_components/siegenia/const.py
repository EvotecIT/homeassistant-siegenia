DOMAIN = "siegenia"

DEFAULT_PORT = 443
DEFAULT_WS_PROTOCOL = "wss"
DEFAULT_POLL_INTERVAL = 5  # seconds
DEFAULT_HEARTBEAT_INTERVAL = 10  # seconds

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_WS_PROTOCOL = "ws_protocol"
CONF_POLL_INTERVAL = "poll_interval"
CONF_HEARTBEAT_INTERVAL = "heartbeat_interval"
CONF_ENABLE_POSITION_SLIDER = "enable_position_slider"
CONF_ENABLE_OPEN_COUNT = "enable_open_count"
CONF_ENABLE_STATE_SENSOR = "enable_state_sensor"
CONF_DEBUG = "debug"
CONF_INFORMATIONAL = "informational"

PLATFORMS = ["cover", "sensor", "binary_sensor", "button"]

# Raw device states observed from Siegenia API
STATE_OPEN = "OPEN"
STATE_CLOSED = "CLOSED"
STATE_CLOSED_WO_LOCK = "CLOSED_WO_LOCK"
STATE_GAP_VENT = "GAP_VENT"
STATE_STOP_OVER = "STOP_OVER"
STATE_STOPPED = "STOPPED"
STATE_MOVING = "MOVING"

# Mapping between raw state and a pseudo-percentage position used by UI
STATE_TO_POSITION = {
    STATE_CLOSED: 0,
    STATE_GAP_VENT: 10,
    STATE_CLOSED_WO_LOCK: 20,
    STATE_STOP_OVER: 40,
    STATE_STOPPED: 70,
    STATE_OPEN: 100,
}

# Reverse mapping thresholds used to interpret set_cover_position
def position_to_command(position: int) -> str | None:
    if position == 100:
        return STATE_OPEN
    if 40 < position <= 99:
        return STATE_STOP_OVER
    if 20 <= position <= 40:
        return STATE_CLOSED_WO_LOCK
    if 0 < position < 20:
        return STATE_GAP_VENT
    if position == 0:
        return "CLOSE"
    return None
# Device type map (same as Homebridge mapping)
DEVICE_TYPE_MAP = {
    1: "AEROPAC",
    2: "AEROMAT VT",
    3: "DRIVE axxent Family",
    4: "SENSOAIR",
    5: "AEROVITAL",
    6: "MHS Family",
    7: "reserved",
    8: "AEROTUBE",
    9: "GENIUS B",
    10: "Universal Module",
}
