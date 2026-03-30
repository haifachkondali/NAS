from addressing import generate_ipv4, generate_loopback

def get_vrf_details(intent_data, vrf_name):
    """ Recherche les détails d'une VRF (RD, RT) dans l'intent. """
    for vrf in intent_data.get("vrfs", []):
        if vrf["name"] == vrf_name:
            return vrf
    return None

def generate_overlay_data(router_config, intent_data):
    """ Prépare les VRF et le voisinage BGP Client (PE-CE). """
    vrfs_config = {}
    my_id = router_config.get("router_num") or router_config.get("router_num_int")

    for interface in router_config.get("interfaces", []):
        vrf_name = interface.get("vrf")
        if vrf_name:
            details = get_vrf_details(intent_data, vrf_name)
            # On cherche l'ID du CE (soit neighbor_num, soit neighbor_CE_num)
            neighbor_num = interface.get("neighbor_num") or interface.get("neighbor_CE_num")
            
            # Ici on est dans un PE, donc is_ce_context=False (par défaut)
            ip_address = generate_ipv4(my_id, neighbor_num, is_pe_ce=True)
            
            if vrf_name not in vrfs_config:
                vrfs_config[vrf_name] = {
                    "name": vrf_name,
                    "rd": details["rd"] if details else "N/A",
                    "rt": details["rt"] if details else "N/A",
                    "interfaces": [],
                    "bgp_neighbors": []
                }
            
            vrfs_config[vrf_name]["interfaces"].append({
                "name": interface["name"],
                "ip": ip_address,
                "mask": "255.255.255.252",
                "desc": interface.get("desc", f"Link to {vrf_name}")
            })

            # Mapping BGP : On calcule l'IP du voisin (le CE) qui est toujours .2
            vrfs_config[vrf_name]["bgp_neighbors"].append({
                "ip": f"192.168.{neighbor_num}.2", 
                "remote_as": next((ce["as"] for ce in intent_data["routers"]["CE_ROUTERS"] if ce["hostname"] in interface.get("connected_to", "")), "65000"),
                "hostname": interface.get("connected_to")
            })

    return list(vrfs_config.values())

def generate_ce_data(router_config, intent_data):
    """ Prépare les données pour un routeur Client (CE). """
    # L'ID du CE est souvent déduit du nom ou d'un champ router_num
    # Pour CE1 -> 1, CE2 -> 2, etc.
    my_id = router_config.get("router_num") or int(''.join(filter(str.isdigit, router_config["hostname"])))
    
    return {
        "hostname": router_config["hostname"],
        "as_number": router_config["as"],
        "vrf_membership": router_config["vrf"],
        "interface_name": router_config.get("interface", "FastEthernet0/0"),
        # Ici on utilise la logique : CE est .2, PE est .1
        "ip": generate_ipv4(my_id, None, is_pe_ce=True, is_ce_context=True),
        "mask": "255.255.255.252",
        "pe_ip": generate_ipv4(my_id, None, is_pe_ce=True, is_ce_context=False),
        "backbone_as": intent_data["backbone_as"]
    }

def generate_ospf_mpls_data(router_config, intent_data):
    """ Prépare OSPF/MPLS pour les routeurs P et PE. """
    interfaces = []
    my_id = router_config.get("router_num") or router_config.get("router_num_int")
    
    for intf in router_config.get("interfaces", []):
        if "vrf" not in intf:
            neighbor_id = intf.get("neighbor_num")
            ip = generate_ipv4(my_id, neighbor_id, is_pe_ce=False)
            
            parts = ip.split('.')
            network_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.0"

            interfaces.append({
                "name": intf["name"],
                "neighbor": intf.get("neighbor", "UNKNOWN"),
                "ip": ip,
                "mask": "255.255.255.252",
                "network_ip": network_ip,
                "mpls": intf.get("mpls", False)
            })
    
    return {
        "hostname": router_config["hostname"],
        "loopback_ip": generate_loopback(my_id),
        "router_id": generate_loopback(my_id),
        "interfaces": interfaces
    }

def generate_ibgp_data(pe_config, intent_data):
    """ Prépare la session iBGP VPNv4 entre PE. """
    neighbor_info = {}
    ibgp_target_hostname = pe_config.get("ibgp_to")
    
    if ibgp_target_hostname:
        target_router = next((r for r in intent_data["routers"].get("PE_ROUTERS", [])
                              if r["hostname"] == ibgp_target_hostname), None)
        
        if target_router:
            target_id = target_router.get("router_num") or target_router.get("router_num_int")
            neighbor_info = {
                "ip": generate_loopback(target_id),
                "remote_as": intent_data["backbone_as"],
                "hostname": target_router["hostname"]
            }

    my_id = pe_config.get("router_num") or pe_config.get("router_num_int")
    return {
        "hostname": pe_config["hostname"],
        "backbone_as": intent_data["backbone_as"],
        "loopback_ip": generate_loopback(my_id),
        "neighbor": neighbor_info
    }

def generate_router_data(router_hostname, intent_data):
    """ Orchestrateur principal. """
    categories = ["PE_ROUTERS", "P_ROUTERS", "CE_ROUTERS"]
    raw_config, role = None, ""

    for cat in categories:
        raw_config = next((r for r in intent_data["routers"].get(cat, []) if r["hostname"] == router_hostname), None)
        if raw_config:
            role = cat
            break

    if not raw_config: return None

    my_id = raw_config.get("router_num") or raw_config.get("router_num_int")
    router_data = {
        "hostname": router_hostname,
        "backbone_as": intent_data.get("backbone_as"),
        "igp_protocol": intent_data.get("igp")
    }

    if role == "PE_ROUTERS":
        router_data["role"] = "PE"
        router_data.update(generate_ospf_mpls_data(raw_config, intent_data))
        router_data["vrfs_config"] = generate_overlay_data(raw_config, intent_data)
        router_data["ibgp_data"] = generate_ibgp_data(raw_config, intent_data)
    
    elif role == "P_ROUTERS":
        router_data["role"] = "P"
        router_data.update(generate_ospf_mpls_data(raw_config, intent_data))

    elif role == "CE_ROUTERS":
        router_data["role"] = "CE"
        router_data.update(generate_ce_data(raw_config, intent_data))

    return router_data