"""Common utilities for miniTV senders."""

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


def send(url, payload):
    """Send JSON payload to miniTV display via /usr/bin/curl."""
    data = json.dumps(payload)
    try:
        subprocess.run(
            ["/usr/bin/curl", "-s", "-X", "POST", url,
             "-H", "Content-Type: application/json", "-d", "@-"],
            input=data.encode(), timeout=5, capture_output=True
        )
    except Exception as e:
        print(f"Send error: {e}")


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


def run_loop(url, collect_fn, build_fn, interval, fingerprint_fn=None):
    """Main sender loop: collect data, build display, send if changed.

    Args:
        url: miniTV display URL
        collect_fn: callable() -> data (any type)
        build_fn: callable(data) -> payload dict
        interval: seconds between updates
        fingerprint_fn: callable(data) -> hashable (optional, defaults to JSON comparison)
    """
    prev_fp = None
    prev_json = None
    while True:
        data = collect_fn()
        if fingerprint_fn:
            fp = fingerprint_fn(data)
            if fp != prev_fp:
                payload = build_fn(data)
                send(url, payload)
                prev_fp = fp
        else:
            payload = build_fn(data)
            payload_json = json.dumps(payload, sort_keys=True)
            if payload_json != prev_json:
                send(url, payload)
                prev_json = payload_json
        time.sleep(interval)
