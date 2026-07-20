DOMAIN = "govee_lan"
CONF_DEVICES = "devices"
CONF_DEVICE_IP = "ip"
CONF_DEVICE_MODEL = "model"
CONF_DEVICE_NAME = "name"
CONF_DEVICE_ID = "device_id"
CONF_MIN_COLOR_TEMP_KELVIN = "min_color_temp_kelvin"
CONF_MAX_COLOR_TEMP_KELVIN = "max_color_temp_kelvin"
CONF_SKU = "sku"

GOVEE_CMD_PORT = 4003
GOVEE_SCAN_PORT = 4001
GOVEE_SCAN_RESP_PORT = 4002
GOVEE_MULTICAST_ADDR = "239.255.255.250"

DEFAULT_POLL_INTERVAL = 10

# Clamped to match the range Govee's own app exposes (2700-6500K), not the
# device's advertised 2000-9000K spec. Confirmed by direct devStatus polling
# (see README) that this hardware's RGBICW color-mix math produces genuinely
# wrong output -- a hue flip toward magenta/purple, not just a duller color --
# outside this window. The wider range is real on paper but not safe to send.
MIN_COLOR_TEMP_KELVIN = 2700
MAX_COLOR_TEMP_KELVIN = 6500

# devStatus polling is single unicast UDP across subnets (no retransmit in UDP).
# Send each poll a few times with a short per-try timeout so one lost datagram
# doesn't count as a failure. Total worst case = ATTEMPTS * PER_TRY_TIMEOUT.
POLL_ATTEMPTS = 3
POLL_TRY_TIMEOUT = 1.0
