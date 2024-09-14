#!/usr/bin/env python3

import argparse
from os import remove
from flask import Flask, Response
from zeroconf import BadTypeInNameException, NonUniqueNameException, Zeroconf, ServiceBrowser, ServiceListener, ZeroconfServiceTypes
import threading
import time
from colorama import Fore, init
import pickle
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
from functools import wraps

# Colorama stuff
init(autoreset=True)

app = Flask(__name__)

# Store discovered services
services = {}

# Store remote services from other nodes
fetched_services = {}

# Initialize Zeroconf
zeroconf = Zeroconf()

def skip_non_local_service(func):
    @wraps(func)
    def wrapper(self, zc, type_, name):
        if is_not_local_service(name):
            print(Fore.BLACK + f"Skipping non local service {name}")
            return
        return func(self, zc, type_, name)
    return wrapper

# Zeroconf listener class
class mDNSListener(ServiceListener):
    @skip_non_local_service
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            services[name] = info
            print(Fore.GREEN + f"Service {name} added")

    @skip_non_local_service
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            services[name] = info
            print(Fore.BLUE + f"Service {name} updated")

    @skip_non_local_service
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        if name in services:
            del services[name]
            print(Fore.RED + f"Service {name} removed")

def is_not_local_service(name):
    return any(name in services for services in fetched_services.values())

def serialize_services(services):
    return pickle.dumps(services)

def deserialize_services(data):
    return pickle.loads(data)

def service_is_not_registered(type, name):
    return zeroconf.get_service_info(type, name) is None

def register_remote_service(info, node_ip):
    if zeroconf.get_service_info(info.type, info.name) is None:
        try:
            zeroconf.register_service(info)
            print(Fore.GREEN + f"[{node_ip}] Service {info.name} added")
        except NonUniqueNameException:
            print(Fore.RED + f"[{node_ip}] Service {info.name} already exists")
        except BadTypeInNameException:
            print(Fore.RED + f"[{node_ip}] Service {info.name} has an invalid type name")

def get_services_from_host(host_ip):
    try:
        with requests.Session() as session:
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
            session.mount('http://', HTTPAdapter(max_retries=retries))
            response = session.get(f'http://{host_ip}:5121/', timeout=5)
            if response.status_code == 200:
                return deserialize_services(response.content)
            else:
                print(Fore.RED + f"Failed to fetch services from {host_ip}: {response.status_code}")
    except requests.RequestException as e:
        print(Fore.RED + f"Error fetching services from {host_ip}: {e.strerror}")
    return None

# pickle Endpoint (this is probably not a good idea)
@app.route('/', methods=['GET'])
def get_services():
    serialized_services = serialize_services(services)
    return Response(serialized_services, mimetype='application/octet-stream')

# start the Zeroconf service browser
def start_browser():
    listener = mDNSListener()
    service_types = set()
    browsers = []

    while True:
        new_service_types = set(ZeroconfServiceTypes.find())
        added_types = new_service_types - service_types

        for service_type in added_types:
            browsers.append(ServiceBrowser(zeroconf, service_type, listener))
            print(Fore.MAGENTA + f"Started browsing for service type: {service_type}")

        service_types.update(new_service_types)
        time.sleep(5)  # Refresh every 5 seconds

# update or create remote services
def update_remote_services(new_fetched_services):
    for node_ip, node_services in new_fetched_services.items():
        if node_ip in fetched_services:
            for name, info in node_services.items():
                if name in fetched_services[node_ip]:
                    if zeroconf.get_service_info(info.type, info.name) != info:
                        fetched_services[node_ip][name] = info
                        zeroconf.update_service(info)
                        print(Fore.BLUE + f"[{node_ip}] Service {name} updated")
                else:
                    fetched_services[node_ip][name] = info
                    register_remote_service(info, node_ip)
        else:
            fetched_services[node_ip] = node_services
            for _ in node_services:
                for name, info in node_services.items():
                    register_remote_service(info, node_ip)

def remove_remote_services(new_fetched_services):
    for node_ip in list(fetched_services.keys()):
        if node_ip not in new_fetched_services:
            for name in list(fetched_services[node_ip].keys()):
                zeroconf.unregister_service(fetched_services[node_ip][name])
                del fetched_services[node_ip][name]
                print(Fore.RED + f"[{node_ip}] Service {name} removed")
            del fetched_services[node_ip]
            print(Fore.RED + f"All services removed from {node_ip} list")
        else:
            for name in list(fetched_services[node_ip].keys()):
                if name not in new_fetched_services[node_ip]:
                    zeroconf.unregister_service(fetched_services[node_ip][name])
                    del fetched_services[node_ip][name]
                    print(Fore.RED + f"[{node_ip}] Service {name} removed")


def get_remote_services():
    while True:
        new_fetched_services = {}
        for node_ip in nodes:
            node_services = get_services_from_host(node_ip)
            if node_services:
                new_fetched_services[node_ip] = node_services
            else:
                print(Fore.RED + f"Node {node_ip} is unreachable or returned no services")

        update_remote_services(new_fetched_services)
        remove_remote_services(new_fetched_services)

        time.sleep(20)  # maybe this time is too long or too short

parser = argparse.ArgumentParser(description='Service discovery and registration script.')
parser.add_argument('nodes', metavar='N', type=str, nargs='*', help='List of node IP addresses')
args = parser.parse_args()

# load configs
if args.nodes:
    nodes = args.nodes
else:
    try:
        with open('config.json') as config_file:
            config = json.load(config_file)
            nodes = config.get('nodes', [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(Fore.YELLOW + f"Error loading config.json: {e.strerror}")
        nodes = []

# get services from nodes on a separate thread just in case
fetch_thread = threading.Thread(target=get_remote_services)
fetch_thread.daemon = True
fetch_thread.start()

# another thread to start the zeroconf browser
browser_thread = threading.Thread(target=start_browser)
browser_thread.daemon = True
browser_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5121)
