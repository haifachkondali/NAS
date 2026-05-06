def generate_ipv4(my_num, neighbor_num, base_prefix, is_pe_ce=False, is_ce_context=False):
    """
    Generate IPv4 address for router interfaces using a prefix from the intent file.
    
    Args:
        my_num: Router ID executing the script
        neighbor_num: Neighbor router ID (can be None for loopbacks)
        base_prefix: Network prefix defined in the intent file (e.g., "10.0" or "192.168")
        is_pe_ce: True if PE-CE customer link
        is_ce_context: True if router is a CE
        
    Returns:
        IPv4 address string
    """
    if is_pe_ce:
        # PE-CE link: subnet is always the CE ID
        subnet = my_num if is_ce_context else neighbor_num
        # Host: .2 if CE, .1 if PE
        host = "2" if is_ce_context else "1"
        # Uses base_prefix from intent (e.g., "192.168")
        return f"{base_prefix}.{subnet}.{host}"
    
    elif neighbor_num is None:
        # Case for Loopback interfaces
        # Uses base_prefix from intent (e.g., "10.0.0")
        return f"{base_prefix}.{my_num}"
        
    else:
        # Backbone link (P-P, P-PE)
        ids = sorted([int(my_num), int(neighbor_num)])
        subnet = f"{ids[0]}{ids[1]}"
        host = "1" if int(my_num) < int(neighbor_num) else "2"
        # Uses base_prefix from intent (e.g., "10.0")
        return f"{base_prefix}.{subnet}.{host}"


def extract_router_num(router):
    """
    Extract numeric router ID from router config object.
    
    Args:
        router (dict): Router configuration with hostname and optional router_num fields
        
    Returns:
        int: Numeric router ID
        
    Raises:
        ValueError: If router ID cannot be determined
    """
    import re
    
    # Try explicit router_num field
    value = router.get("router_num")
    if value is not None:
        return int(value)
    
    # Try alternate field name
    value = router.get("router_num_int")
    if value is not None:
        return int(value)
    
    # Extract from hostname (e.g., "P1" -> 1, "PE2" -> 2)
    match = re.search(r"(\d+)$", router.get("hostname", ""))
    if not match:
        raise ValueError(
            f"Router '{router.get('hostname', 'UNKNOWN')}' must define router_num/router_num_int or end hostname with digits"
        )
    return int(match.group(1))


def generate_loopback(router_num):
    """Generate a deterministic loopback for a router numeric ID."""
    """Generate a deterministic loopback for a router numeric ID."""
    return f"10.0.0.{int(router_num)}"
