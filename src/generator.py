from addressing import generate_ip, generate_loopback

def get_vrf_details(intent_data, vrf_name):
    """ Recherche les détails d'une VRF (RD, RT) dans l'intent. """
    for vrf in intent_data.get("vrfs", []):
        if vrf["name"] == vrf_name:
            return vrf
    return None

def generate_overlay_data(router_config, intent_data):
    """ Prépare les VRF et le voisinage BGP Client (PE-CE). """
    vrfs_config = {}
    # On récupère l'ID du PE actuel
    my_id = router_config.get("router_num") or router_config.get("router_num_int")

    for interface in router_config.get("interfaces", []):
        vrf_name = interface.get("vrf")
        if vrf_name:
            details = get_vrf_details(intent_data, vrf_name)
            neighbor_num = interface.get("neighbor_num") or interface.get("neighbor_CE_num")
            
            # Génération de l'IP du PE sur l'interface client (is_pe_ce=True)
            ip_address = generate_ip(my_id, neighbor_num, is_pe_ce=True)
            
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

            # Mapping BGP : Trouver le CE qui correspond à ce lien
            for ce in intent_data["routers"].get("CE_ROUTERS", []):
                # On lie si le CE est censé être connecté à ce PE
                if ce.get("connected_to") == router_config["hostname"] and ce.get("vrf") == vrf_name:
                    # L'IP du CE est la .2 du sous-réseau (via notre logique addressing)
                    ce_id = ce.get("router_num") or neighbor_num
                    vrfs_config[vrf_name]["bgp_neighbors"].append({
                        "ip": f"192.168.{ce_id}.2", 
                        "remote_as": ce["as"],
                        "hostname": ce["hostname"]
                    })

    return list(vrfs_config.values())

def generate_ce_data(router_config, intent_data):
    """ Prépare les données pour un routeur Client (CE). """
    my_id = router_config.get("router_num")
    # Pour un CE, le neighbor_num est l'ID du PE (ex: 1 pour PE1)
    pe_neighbor_num = router_config.get("neighbor_num") 
    
    return {
        "hostname": router_config["hostname"],
        "as_number": router_config["as"],
        "vrf_membership": router_config["vrf"],
        "interface_name": router_config.get("interface", "FastEthernet0/0"),
        "ip": f"192.168.{my_id}.2", # Le CE est toujours .2
        "mask": "255.255.255.252",
        "pe_ip": f"192.168.{my_id}.1", # Le PE est toujours .1
        "backbone_as": intent_data["backbone_as"]
    }

def generate_ospf_mpls_data(router_config, intent_data):
    """ Prépare OSPF/MPLS pour les routeurs P et PE. """
    interfaces = []
    my_id = router_config.get("router_num") or router_config.get("router_num_int")
    
    for intf in router_config.get("interfaces", []):
        # On ne configure OSPF/MPLS que sur les liens Backbone (sans VRF)
        if "vrf" not in intf:
            neighbor_id = intf.get("neighbor_num")
            ip = generate_ip(my_id, neighbor_id, is_pe_ce=False)
            
            # Calcul du network ID (ex: 10.0.12.1 -> 10.0.12.0)
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
    ibgp_target_hostname = pe_config.get("ibgp_to") # ex: "PE2"
    
    if ibgp_target_hostname:
        # Trouver l'ID du voisin PE pour calculer sa Loopback
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
    # 1. Identifier le rôle et récupérer la config brute
    categories = ["PE_ROUTERS", "P_ROUTERS", "CE_ROUTERS"]
    raw_config = None
    role = ""

    for cat in categories:
        raw_config = next((r for r in intent_data["routers"].get(cat, []) 
                           if r["hostname"] == router_hostname), None)
        if raw_config:
            role = cat
            break

    if not raw_config:
        return None

    # 2. Remplir les données communes
    my_id = raw_config.get("router_num") or raw_config.get("router_num_int")
    router_data = {
        "hostname": router_hostname,
        "backbone_as": intent_data.get("backbone_as"),
        "igp_protocol": intent_data.get("igp"),
        "loopback_ip": generate_loopback(my_id) if role != "CE_ROUTERS" else None
    }

    # 3. Remplir selon le rôle
    if role == "PE_ROUTERS":
        router_data["role"] = "PE"
        router_data["interfaces"] = generate_ospf_mpls_data(raw_config, intent_data)["interfaces"]
        router_data["vrfs_config"] = generate_overlay_data(raw_config, intent_data)
        router_data["ibgp_data"] = generate_ibgp_data(raw_config, intent_data)
    
    elif role == "P_ROUTERS":
        router_data["role"] = "P"
        router_data["interfaces"] = generate_ospf_mpls_data(raw_config, intent_data)["interfaces"]

    elif role == "CE_ROUTERS":
        router_data["role"] = "CE"
        router_data.update(generate_ce_data(raw_config, intent_data))

    return router_data