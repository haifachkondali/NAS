import json
from addressing import generate_ipv4


def load_intent(intent_file):
    with open(intent_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _vrf_defaults(intent_data):
    backbone_as = int(intent_data.get("backbone_as", 100))
    defaults = {}
    for idx, vrf in enumerate(intent_data.get("vrfs", []), start=1):
        name = vrf["name"]
        defaults[name] = {
            "rd": vrf.get("rd", f"{backbone_as}:{idx}"),
            "rt": vrf.get("rt", f"{backbone_as}:{idx}"),
        }
    return defaults


def _core_interface_data(my_num, intf, routers_by_hostname, intent_data):
    neighbor_num = None
    neighbor_name = intf.get("neighbor")

    if neighbor_name and neighbor_name in routers_by_hostname:
        neighbor_num = intf.get("neighbor_num")

    if neighbor_num is None:
        raise ValueError(f"Interface '{intf.get('name', 'UNKNOWN')}' is missing neighbor_num")

    # Utilisation du préfixe backbone de l'intent
    prefix = intent_data.get("address_prefixes").get("backbone")
    ip = generate_ipv4(my_num, neighbor_num, prefix)
    
    octets = ip.split(".")
    network_ip = f"{octets[0]}.{octets[1]}.{octets[2]}.0"

    return {
        "name": intf["name"],
        "neighbor": intf.get("neighbor", "UNKNOWN"),
        "ip": ip,
        "mask": "255.255.255.252",
        "network_ip": network_ip,
        "mpls": bool(intf.get("mpls", False)),
    }


def _generate_p_data(router_cfg, routers_by_hostname, intent_data):
    my_num = router_cfg.get("router_num")
    interfaces = []
    
    # Récupération du préfixe loopback
    lb_prefix = intent_data.get("address_prefixes").get("loopback")
    loopback_ip = generate_ipv4(my_num, None, lb_prefix)

    for intf in router_cfg.get("interfaces", []):
        if "vrf" in intf:
            continue
        interfaces.append(_core_interface_data(my_num, intf, routers_by_hostname, intent_data))

    return {
        "hostname": router_cfg["hostname"],
        "router_type": "P",
        "port": router_cfg["port"],
        "loopback_ip": loopback_ip,
        "router_id": loopback_ip,
        "interfaces": interfaces,
    }


def _generate_pe_data(router_cfg, intent_data, ce_by_hostname, vrf_defaults, pe_by_hostname, routers_by_hostname):
    my_num = router_cfg.get("router_num")
    backbone_interfaces = []
    vrf_map = {}

    # Préfixes de l'intent
    lb_prefix = intent_data.get("address_prefixes").get("loopback")
    pe_ce_prefix = intent_data.get("address_prefixes").get("pe_ce")
    
    loopback_ip = generate_ipv4(my_num, None, lb_prefix)

    for intf in router_cfg.get("interfaces", []):
        if "vrf" not in intf:
            backbone_interfaces.append(_core_interface_data(my_num, intf, routers_by_hostname, intent_data))
            continue

        vrf_name = intf["vrf"]
        ce_hostname = intf.get("connected_to")
        ce_router = ce_by_hostname.get(ce_hostname, {})

        ce_num = intf.get("neighbor_num")
        
        if ce_num is None:
            raise ValueError(f"PE router '{router_cfg['hostname']}' interface '{intf.get('name', 'UNKNOWN')}' has no CE id")

        if vrf_name not in vrf_map:
            defaults = vrf_defaults.get(vrf_name, {"rd": "100:1", "rt": "100:1"})
            vrf_map[vrf_name] = {
                "name": vrf_name,
                "rd": defaults["rd"],
                "rt": defaults["rt"],
                "interfaces": [],
                "bgp_neighbors": [],
            }

        # Nouveaux appels avec prefix
        pe_ip = generate_ipv4(my_num, ce_num, pe_ce_prefix, is_pe_ce=True, is_ce_context=False)
        ce_ip = generate_ipv4(ce_num, my_num, pe_ce_prefix, is_pe_ce=True, is_ce_context=True)

        vrf_map[vrf_name]["interfaces"].append({
            "name": intf["name"],
            "ip": pe_ip,
            "mask": "255.255.255.252",
            "desc": intf.get("desc", f"Link to {ce_hostname or vrf_name}"),
        })

        vrf_map[vrf_name]["bgp_neighbors"].append({
            "ip": ce_ip,
            "remote_as": int(ce_router.get("as", 65000)),
            "hostname": ce_hostname or "UNKNOWN",
        })

        ibgp_neighbor = {}
        ibgp_to = router_cfg.get("ibgp_to")
        if ibgp_to:
            target = pe_by_hostname.get(ibgp_to)
            if target:
                target_num = target.get("router_num")
                ibgp_neighbor = {
                    "ip": generate_ipv4(target_num, None, lb_prefix), # Loopback du voisin PE
                    "remote_as": int(intent_data["backbone_as"]),
                    "hostname": target["hostname"],
                    "update_source": "Loopback0"
                }

    return {
        "hostname": router_cfg["hostname"],
        "router_type": "PE",
        "port": router_cfg["port"],
        "loopback_ip": loopback_ip,
        "router_id": loopback_ip,
        "interfaces": backbone_interfaces,
        "vrfs_config": list(vrf_map.values()),
        "neighbor": ibgp_neighbor,
        "backbone_as": int(intent_data["backbone_as"]),
    }


def _generate_ce_data(router_cfg, intent_data, pe_by_hostname):
    my_num = router_cfg.get("router_num")
    pe_hostname = router_cfg.get("connected_to")

    pe_router_obj = pe_by_hostname.get(pe_hostname)

    pe_ce_prefix = intent_data.get("address_prefixes").get("pe_ce")

    if pe_hostname and pe_hostname not in pe_by_hostname:
        raise ValueError(f"CE router '{router_cfg['hostname']}' references unknown PE '{pe_hostname}'")

    return {
        "hostname": router_cfg["hostname"],
        "router_type": "CE",
        "port": router_cfg["port"],
        "as_number": int(router_cfg["as"]),
        "vrf_membership": router_cfg["vrf"],
        "interface_name": router_cfg.get("interface", "FastEthernet0/0"),
        # .2 pour le CE
        "ip": generate_ipv4(my_num, None, pe_ce_prefix, is_pe_ce=True, is_ce_context=True),
        "mask": "255.255.255.252",
        # .1 pour le PE
        "pe_ip": generate_ipv4(my_num, my_num, pe_ce_prefix, is_pe_ce=True, is_ce_context=False),
        "backbone_as": int(intent_data["backbone_as"]),
    }


def generate_router_data(intent_data):
    routers = intent_data.get("routers", {})
    p_routers = routers.get("P_ROUTERS", [])
    pe_routers = routers.get("PE_ROUTERS", [])
    ce_routers = routers.get("CE_ROUTERS", [])

    ce_by_hostname = {r["hostname"]: r for r in ce_routers}
    pe_by_hostname = {r["hostname"]: r for r in pe_routers}
    routers_by_hostname = {r["hostname"]: r for r in (p_routers + pe_routers + ce_routers)}
    vrf_defaults = _vrf_defaults(intent_data)

    data = []
    for router in p_routers:
        data.append(_generate_p_data(router, routers_by_hostname, intent_data))

    for router in pe_routers:
        data.append(_generate_pe_data(router, intent_data, ce_by_hostname, vrf_defaults, pe_by_hostname, routers_by_hostname))

    for router in ce_routers:
        data.append(_generate_ce_data(router, intent_data, pe_by_hostname))

    return data