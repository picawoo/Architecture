import os
from abc import ABC, abstractmethod

import redis
import requests
from flask import Flask, jsonify

app = Flask(__name__)
cache = redis.Redis(host=os.getenv('REDIS_HOST', 'redis'), port=6379, decode_responses=True)


# адаптеры
class IPProvider(ABC):
    @abstractmethod
    def fetch(self): raise NotImplementedError


class IpApiProvider(IPProvider):
    def fetch(self):
        resp = requests.get("http://ip-api.com/json/", timeout=5).json()
        return resp.get("query")


class JsonIpProvider(IPProvider):
    def fetch(self):
        resp = requests.get("https://jsonip.com/", timeout=5).json()
        return resp.get("ip")


# основной маршрут
@app.route('/')
def get_ip():
    api_type = os.getenv('TYPE', 'ip-api')
    provider = JsonIpProvider() if api_type == 'jsonip' else IpApiProvider()

    try:
        ip = provider.fetch()
        if ip:
            cache.incr(f"stats:calls:{api_type}")

            cache.lpush("stats:recent_ips", ip)
            cache.ltrim("stats:recent_ips", 0, 4)

            with open("/app/logs/history.log", "a") as f:
                f.write(f"API: {api_type}, IP: {ip}\n")

            return jsonify({"myIP": ip, "provider": api_type})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# статистика
@app.route('/stats')
def get_stats():
    stats = {
        "calls_ip_api": cache.get("stats:calls:ip-api") or 0,
        "calls_jsonip": cache.get("stats:calls:jsonip") or 0,
        "recent_ips": cache.lrange("stats:recent_ips", 0, -1)
    }
    return jsonify(stats)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)