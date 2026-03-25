
def generate_router_id(hostname, router_num):
    """Generate router-id using get_router_id (R1 → 1.1.1.1)."""
    router_id = router_num
    if router_id is not None:
        return f"{router_id}.{router_id}.{router_id}.{router_id}"
    return None



def generate_ipv6(base, router_a_id, router_b_id=None):
    """Generate IPv6 address based on base prefix and router IDs.
    Args:
        base (str): The base IPv6 prefix (e.g., "2001:" or "FC00:0:0:").
        router_a_id (int): The ID of the first router.
        router_b_id (int, optional): The ID of the second router. If None, generate loopback.
    Returns:
        str: The generated IPv6 address.
    """
    if router_b_id:
        ids = sorted([int(router_a_id), int(router_b_id)])
        network_part = f"{ids[0]}:{ids[1]}"
        interface_host = "1" if router_a_id < router_b_id else "2"
        return f"{base}{network_part}::{interface_host}"
    else:
        # Loopback for one router: FC00:0:0:1::1/128
        return f"{base}{router_a_id}::1"


# Example usage
if __name__ == "__main__":
    print(generate_router_id("R2"))  # 2.2.2.2
    print(generate_ipv6("2001:1:", 1, 2))  # 2001:1:1:2::1/64
