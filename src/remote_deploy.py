from netmiko import ConnectHandler
import os
from concurrent.futures import ThreadPoolExecutor


def deploy_to_router(router_info, gns3_host=None, reset=True):
    """
    Connects to a router via Telnet and pushes the generated config file.
    
    Args:
        router_info (dict): Router connection details
        gns3_host (str): GNS3 host IP (can be set via GNS3_HOST env var)
        reset (bool): Whether to reset device config before deploying
    """
    hostname = router_info['hostname']
    port = router_info['port']
    config_file_path = router_info['config_file_path']
    
    # Get GNS3 host from env var or parameter, with fallback default
    if gns3_host is None:
        gns3_host = os.getenv('GNS3_HOST', '127.0.0.1')

    device = {
        'device_type': 'cisco_ios_telnet',
        'host': gns3_host,
        'port': port,
        'fast_cli': False,
    }

    if not os.path.exists(config_file_path):
        print(f"[Error] Config file not found: {config_file_path}")
        return

    try:
        with ConnectHandler(**device) as net_connect:
            if reset:
                print(f"--- [RESET] Nettoyage de la configuration sur {hostname} ---")

                reset_cmds = [
                    "no ipv6 router ospf 1",
                    "ip bgp-community new-format"
                ]

                as_name = router_info.get('as_name')
                if as_name:
                    reset_cmds.append(f"no ipv6 router rip {as_name}")

                asn = router_info.get('as_number')
                if isinstance(asn, int):
                    reset_cmds.append(f"no router bgp {asn}")

                net_connect.send_config_set(reset_cmds)
                net_connect.send_command("clear bgp ipv6 unicast *")

            net_connect.send_config_set(["no logging console"])
            print(f"--- Deploying to {hostname} (Port {port}) ---")

            output = net_connect.send_config_from_file(config_file_path)

            save_output = net_connect.send_command('write memory', expect_string=r"\[confirm\]|#")
            if 'confirm' in save_output:
                save_output += net_connect.send_command('\n', expect_string=r"#")

            print(f"[{hostname}] Save result : {save_output.strip()}.")
            net_connect.save_config()

        print(f"[OK] Configuration successfully pushed to {hostname}.\n")

    except Exception as e:
        print(f"[FAILED] Could not connect to {hostname}: {e}\n")


def deploy_parallel(router_list, gns3_host=None, max_workers=8):
    """
    Deploy configurations to multiple routers in parallel.
    
    Args:
        router_list (list): List of router deployment configs
        gns3_host (str): GNS3 host IP (can be set via GNS3_HOST env var)
        max_workers (int): Number of parallel workers
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(lambda r: deploy_to_router(r, gns3_host), router_list)