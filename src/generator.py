import json
import re

from addressing import generate_ip, generate_loopback


def load_intent(intent_file):
    with open(intent_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _router_num(router):
    value = router.get("router_num")
    if value is not None:
        return int(value)

    value = router.get("router_num_int")
    if value is not None:
        return int(value)

    match = re.search(r"(\d+)$", router.get("hostname", ""))
    if not match:
        raise ValueError(f"Unable to infer numeric router id from hostname '{router.get('hostname', 'UNKNOWN')}'")
    return int(match.group(1))


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


def _core_interface_data(my_num, intf):
    neighbor_num = intf.get("neighbor_num")
    if neighbor_num is None:
        raise ValueError(f"Interface '{intf.get('name', 'UNKNOWN')}' is missing neighbor_num")

    ip = generate_ip(my_num, neighbor_num, is_pe_ce=False)
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


def _generate_p_data(router_cfg):
    my_num = _router_num(router_cfg)
    interfaces = []
    for intf in router_cfg.get("interfaces", []):
        if "vrf" in intf:
            continue
        interfaces.append(_core_interface_data(my_num, intf))

    return {
        "hostname": router_cfg["hostname"],
        "router_type": "P",
        "loopback_ip": generate_loopback(my_num),
        "router_id": generate_loopback(my_num),
        "interfaces": interfaces,
    }


def _generate_pe_data(router_cfg, intent_data, ce_by_hostname, vrf_defaults, pe_by_hostname):
    my_num = _router_num(router_cfg)
    backbone_interfaces = []
    vrf_map = {}

    for intf in router_cfg.get("interfaces", []):
        if "vrf" not in intf:
            backbone_interfaces.append(_core_interface_data(my_num, intf))
            continue

        vrf_name = intf["vrf"]
        ce_hostname = intf.get("connected_to")
        ce_router = ce_by_hostname.get(ce_hostname, {})

        ce_num = intf.get("neighbor_num") or intf.get("neighbor_CE_num")
        if ce_num is None and ce_router:
            ce_num = _router_num(ce_router)
        if ce_num is None:
            raise ValueError(
                f"PE router '{router_cfg['hostname']}' interface '{intf.get('name', 'UNKNOWN')}' has no CE id"
            )

        if vrf_name not in vrf_map:
            defaults = vrf_defaults.get(vrf_name, {"rd": "100:1", "rt": "100:1"})
            vrf_map[vrf_name] = {
                "name": vrf_name,
                "rd": defaults["rd"],
                "rt": defaults["rt"],
                "interfaces": [],
                "bgp_neighbors": [],
            }

        pe_ip = generate_ip(my_num, ce_num, is_pe_ce=True)
        ce_ip = generate_ip(ce_num, None, is_pe_ce=True, is_ce_context=True)

        vrf_map[vrf_name]["interfaces"].append(
            {
                "name": intf["name"],
                "ip": pe_ip,
                "mask": "255.255.255.252",
                "desc": intf.get("desc", f"Link to {ce_hostname or vrf_name}"),
            }
        )

        vrf_map[vrf_name]["bgp_neighbors"].append(
            {
                "ip": ce_ip,
                "remote_as": int(ce_router.get("as", 65000)),
                "hostname": ce_hostname or "UNKNOWN",
            }
        )

    ibgp_neighbor = {}
    ibgp_to = router_cfg.get("ibgp_to")
    if ibgp_to:
        target = pe_by_hostname.get(ibgp_to)
        if target:
            target_num = _router_num(target)
            ibgp_neighbor = {
                "ip": generate_loopback(target_num),
                "remote_as": int(intent_data["backbone_as"]),
                "hostname": target["hostname"],
            }

    return {
        "hostname": router_cfg["hostname"],
        "router_type": "PE",
        "loopback_ip": generate_loopback(my_num),
        "router_id": generate_loopback(my_num),
        "interfaces": backbone_interfaces,
        "vrfs_config": list(vrf_map.values()),
        "neighbor": ibgp_neighbor,
        "backbone_as": int(intent_data["backbone_as"]),
    }


def _generate_ce_data(router_cfg, intent_data, pe_by_hostname):
    my_num = _router_num(router_cfg)
    pe_hostname = router_cfg.get("connected_to")

    if pe_hostname and pe_hostname not in pe_by_hostname:
        raise ValueError(f"CE router '{router_cfg['hostname']}' references unknown PE '{pe_hostname}'")

    return {
        "hostname": router_cfg["hostname"],
        "router_type": "CE",
        "as_number": int(router_cfg["as"]),
        "vrf_membership": router_cfg["vrf"],
        "interface_name": router_cfg.get("interface", "FastEthernet0/0"),
        "ip": generate_ip(my_num, None, is_pe_ce=True, is_ce_context=True),
        "mask": "255.255.255.252",
        "pe_ip": generate_ip(my_num, my_num, is_pe_ce=True, is_ce_context=False),
        "backbone_as": int(intent_data["backbone_as"]),
    }


def generate_router_data(intent_data):
    routers = intent_data.get("routers", {})
    p_routers = routers.get("P_ROUTERS", [])
    pe_routers = routers.get("PE_ROUTERS", [])
    ce_routers = routers.get("CE_ROUTERS", [])

    ce_by_hostname = {r["hostname"]: r for r in ce_routers}
    pe_by_hostname = {r["hostname"]: r for r in pe_routers}
    vrf_defaults = _vrf_defaults(intent_data)

    data = []
    for router in p_routers:
        data.append(_generate_p_data(router))

    for router in pe_routers:
        data.append(_generate_pe_data(router, intent_data, ce_by_hostname, vrf_defaults, pe_by_hostname))

    for router in ce_routers:
        data.append(_generate_ce_data(router, intent_data, pe_by_hostname))

    return data