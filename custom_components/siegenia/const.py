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
CONF_WARNING_NOTIFICATIONS = "warning_notifications"
CONF_WARNING_EVENTS = "warning_events"
CONF_ENABLE_BUTTONS = "enable_buttons"

# Advanced timing options
CONF_MOTION_INTERVAL = "motion_interval"  # seconds while moving
CONF_IDLE_INTERVAL = "idle_interval"      # seconds when idle (no push)

DEFAULT_MOTION_INTERVAL = 2
DEFAULT_IDLE_INTERVAL = 60

# Slider threshold options
CONF_SLIDER_GAP_MAX = "slider_gap_max"            # 0 < x < 100; 1..x -> GAP_VENT
CONF_SLIDER_CWOL_MAX = "slider_cwol_max"          # (gap_max+1)..x -> CLOSE_WO_LOCK
CONF_SLIDER_STOP_OVER_DISPLAY = "slider_stop_over_display"  # position used to display STOP_OVER

# Defaults
DEFAULT_GAP_MAX = 19
DEFAULT_CWOL_MAX = 40
DEFAULT_STOP_OVER_DISPLAY = 40

PLATFORMS = ["cover", "sensor", "binary_sensor", "button", "number", "update", "select"]

# Raw device states observed from Siegenia API
STATE_OPEN = "OPEN"
STATE_CLOSED = "CLOSED"
STATE_CLOSED_WO_LOCK = "CLOSED_WO_LOCK"
STATE_GAP_VENT = "GAP_VENT"
STATE_STOP_OVER = "STOP_OVER"
STATE_STOPPED = "STOPPED"
STATE_MOVING = "MOVING"

# Mapping between raw state and a pseudo-percentage position used by UI
STATE_TO_POSITION_DEFAULT = {
    STATE_CLOSED: 0,
    STATE_GAP_VENT: 10,
    STATE_CLOSED_WO_LOCK: 20,
    STATE_STOP_OVER: DEFAULT_STOP_OVER_DISPLAY,
    STATE_STOPPED: 70,
    STATE_OPEN: 100,
}

# Reverse mapping thresholds used to interpret set_cover_position
def position_to_command(position: int, *, gap_max: int = DEFAULT_GAP_MAX, cwol_max: int = DEFAULT_CWOL_MAX) -> str | None:
    # Normalize
    position = max(0, min(100, int(position)))
    if position == 100:
        return STATE_OPEN
    if cwol_max < position < 100:
        return STATE_STOP_OVER
    if gap_max < position <= cwol_max:
        return STATE_CLOSED_WO_LOCK
    if 0 < position <= gap_max:
        return STATE_GAP_VENT
    if position == 0:
        return "CLOSE"
    return None

def state_to_position(state: str, *, stop_over_display: int = DEFAULT_STOP_OVER_DISPLAY) -> int:
    if state == STATE_STOP_OVER:
        return int(stop_over_display)
    return STATE_TO_POSITION_DEFAULT.get(state, 0)

# Select options for mode selector
SELECT_OPTIONS = [
    "OPEN",
    "CLOSE",
    "GAP_VENT",
    "CLOSE_WO_LOCK",
    "STOP_OVER",
    "STOP",
]

# Map raw state -> select option label
STATE_TO_SELECT = {
    STATE_OPEN: "OPEN",
    STATE_CLOSED: "CLOSE",
    STATE_GAP_VENT: "GAP_VENT",
    STATE_CLOSED_WO_LOCK: "CLOSE_WO_LOCK",
    STATE_STOP_OVER: "STOP_OVER",
    STATE_STOPPED: "STOP",
}

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

# Known model variant names for MHS Family (type=6)
# Tuple key: (variant, subvariant)
MHS_MODEL_MAP = {
    (1, 0): "MHS400 Schema A",
}

def resolve_model(device_info: dict) -> str:
    """Resolve a friendly model string from device info."""
    t = device_info.get("type")
    base = DEVICE_TYPE_MAP.get(t, t)
    if t == 6:  # MHS Family
        v = device_info.get("variant")
        sv = device_info.get("subvariant")
        if v is not None and sv is not None:
            name = MHS_MODEL_MAP.get((int(v), int(sv)))
            if name:
                return name
    return str(base)
