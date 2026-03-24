"""Common utilities for miniTV senders."""

import argparse
import json
import re
import socket
import subprocess
import time


def resolve_url(url):
    """Resolve any .local mDNS hostname in URL to IP address."""
    m = re.search(r'([\w-]+\.local)', url)
    if m:
        mdns_host = m.group(1)
        try:
            ip = socket.getaddrinfo(mdns_host, 80, socket.AF_INET)[0][4][0]
            url = url.replace(mdns_host, ip)
            print(f"Resolved {mdns_host} -> {ip}")
        except socket.gaierror:
            print(f"Warning: could not resolve {mdns_host}, using as-is")
    return url


def resolve_host(host):
    """Resolve a .local hostname to IP address."""
    if ".local" in host:
        try:
            ip = socket.getaddrinfo(host, 80, socket.AF_INET)[0][4][0]
            print(f"Resolved {host} -> {ip}")
            return ip
        except socket.gaierror:
            print(f"Warning: could not resolve {host}")
    return host


def _send_http(url, payload):
    """Send JSON payload to miniTV display via HTTP."""
    data = json.dumps(payload)
    try:
        subprocess.run(
            ["/usr/bin/curl", "-s", "-X", "POST", url,
             "-H", "Content-Type: application/json", "-d", "@-"],
            input=data.encode(), timeout=5, capture_output=True
        )
    except Exception as e:
        print(f"Send error: {e}")


def _send_mqtt(broker, port, topic, payload, username=None, password=None):
    """Send JSON payload to miniTV display via MQTT."""
    data = json.dumps(payload)
    cmd = ["mosquitto_pub", "-h", broker, "-p", str(port), "-t", topic, "-r", "-s"]
    if username:
        cmd += ["-u", username]
    if password:
        cmd += ["-P", password]
    if len(data) > 4096:
        print(f"Warning: MQTT payload {len(data)} bytes (device buffer is 4096)")
    try:
        result = subprocess.run(cmd, input=data, timeout=5, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"MQTT send error: {result.stderr.strip()}")
    except FileNotFoundError:
        print("Error: mosquitto_pub not found. Install with: brew install mosquitto")
    except Exception as e:
        print(f"MQTT send error: {e}")


class Display:
    """miniTV display target — supports both HTTP and MQTT."""

    def __init__(self, url=None, mqtt_broker=None, mqtt_port=1883,
                 mqtt_device="minitv", mqtt_user=None, mqtt_pass=None):
        self.url = resolve_url(url) if url else None
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = int(mqtt_port)
        self.mqtt_topic = f"/{mqtt_device}/display"
        self.mqtt_user = mqtt_user
        self.mqtt_pass = mqtt_pass
        self.use_mqtt = mqtt_broker is not None

    def send(self, payload):
        if self.use_mqtt:
            _send_mqtt(self.mqtt_broker, self.mqtt_port, self.mqtt_topic,
                       payload, self.mqtt_user, self.mqtt_pass)
        elif self.url:
            _send_http(self.url, payload)

    def describe(self):
        if self.use_mqtt:
            return f"mqtt://{self.mqtt_broker}:{self.mqtt_port}{self.mqtt_topic}"
        return self.url or "no target"


# Convenience: keep old send() working for simple cases
def send(url, payload):
    _send_http(url, payload)


def fetch(url, timeout=10):
    """Fetch JSON from a URL via /usr/bin/curl. Returns parsed dict or None."""
    try:
        result = subprocess.run(
            ["/usr/bin/curl", "-s", url],
            capture_output=True, text=True, timeout=timeout
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Fetch error: {e}")
        return None


def add_display_args(parser):
    """Add common display target arguments to an argparse parser."""
    parser.add_argument("url", nargs="?", default=None,
                        help="HTTP URL (default: http://minitv.local/display)")
    parser.add_argument("--mqtt-broker", help="MQTT broker hostname")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT port (default: 1883)")
    parser.add_argument("--mqtt-device", default="minitv", help="MQTT device name (default: minitv)")
    parser.add_argument("--mqtt-user", help="MQTT username")
    parser.add_argument("--mqtt-pass", help="MQTT password")


def display_from_args(args):
    """Create a Display from parsed argparse args."""
    if args.mqtt_broker:
        return Display(mqtt_broker=args.mqtt_broker, mqtt_port=args.mqtt_port,
                       mqtt_device=args.mqtt_device, mqtt_user=args.mqtt_user,
                       mqtt_pass=args.mqtt_pass)
    url = args.url or "http://minitv.local/display"
    return Display(url=url)


def run_loop(display, collect_fn, build_fn, interval, fingerprint_fn=None):
    """Main sender loop: collect data, build display, send if changed.

    Args:
        display: Display instance or HTTP URL string (for backwards compat)
        collect_fn: callable() -> data (any type)
        build_fn: callable(data) -> payload dict
        interval: seconds between updates
        fingerprint_fn: callable(data) -> hashable (optional, defaults to JSON comparison)
    """
    # Support passing a URL string for backwards compat
    if isinstance(display, str):
        display = Display(url=display)

    prev_fp = None
    prev_json = None
    while True:
        data = collect_fn()
        if fingerprint_fn:
            fp = fingerprint_fn(data)
            if fp != prev_fp:
                payload = build_fn(data)
                display.send(payload)
                prev_fp = fp
        else:
            payload = build_fn(data)
            payload_json = json.dumps(payload, sort_keys=True)
            if payload_json != prev_json:
                display.send(payload)
                prev_json = payload_json
        time.sleep(interval)
