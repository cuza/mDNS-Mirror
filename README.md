# mDNS Mirror over HTTP

This project is a Zeroconf (mDNS) service discovery and registration tool using and Flask. It discovers local mDNS services and mirrors them across multiple nodes over HTTP. Useful if you have a site to site VPN and don't want to allow multicast traffic on your VPN

## Features

- Discovers local mDNS services.
- Expose local mDNS services over HTTP
- Registers and updates services across multiple nodes.
- Uses Flask for the web server.
- Uses threading to handle service discovery and fetching remote services concurrently.

## Requirements

- Python >=3.10
- `pip` for package management

## Installation

1. Clone the repository:
    ```sh
    git clone git@github.com:cuza/mDNS-Mirror.git
    cd mDNS-Mirror
    ```
    
2. Create and activate the virtual enviroment:
    ```sh
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

1. Create a `config.json` file with the list of node IP addresses:
    ```json
    {
        "nodes": ["192.168.1.2", "192.168.2.2"]
    }
    ```

2. Run the script:
    ```sh
    python mdns-mirror.py
    ```

3. Optionally, you can pass the node IP addresses as command-line arguments:
    ```sh
    python mdns-mirror.py 192.168.1.2 192.168.2.2
    ```

## License

This project is licensed under the MIT License.
