#!/usr/bin/env python3
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify({"service": "health-check-api", "version": "1.0", "endpoints": ["/api/health"]})


@app.route("/api/health")
def health():
    # CWE-78: check parameter passed unsanitized to ping
    host = request.args.get("check", "127.0.0.1")
    result = subprocess.run(
        f"ping -c1 -W1 {host}",
        shell=True, capture_output=True, text=True, timeout=5,
    )
    return jsonify({
        "check": host,
        "output": result.stdout + result.stderr,
        "reachable": result.returncode == 0,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
