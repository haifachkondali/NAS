def generate_ip(my_id, neighbor_id, is_pe_ce=False):
    """
    Automates the addressing logic.
    """
    if is_pe_ce:
        # CE links: Subnet is the CE's ID. PE is always .1, CE is always .2
        # We assume the 'neighbor_id' here is the CE ID.
        return f"192.168.{neighbor_id}.1"
    else:
        # Backbone links: Subnet is sorted IDs (1 & 2 -> 12). Lower ID is .1
        ids = sorted([int(my_id), int(neighbor_id)])
        subnet = f"{ids[0]}{ids[1]}"
        host = "1" if int(my_id) < int(neighbor_id) else "2"
        return f"10.0.{subnet}.{host}"
    
def generate_loopback(my_id):
    return f"10.0.0.{my_id}"