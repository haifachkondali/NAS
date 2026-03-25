# jinja2 templates
import json
import os

from jinja2 import Environment, FileSystemLoader

from addressing import generate_ipv6, generate_router_id


def load_intent(intent_file="intent/network.json"):
    with open(intent_file, "r") as f:
        return json.load(f)


def correspondance_table(intent):
    router_lookup = {}
    for as_name in intent["autonomous_systems"]:
        as_data = intent["autonomous_systems"][as_name]
        for router in as_data["routers"]:
            router_lookup[router["hostname"]] = router["id"]
    return router_lookup


def generate_router_data(intent, as_name):
    """
    Generate router data for all routers in the specified autonomous system.
    Args:
        intent (dict): The network intent data.
        as_name (str): The name of the autonomous system.
    Returns:
        list: A list of router data dictionaries.
    """
    router_lookup = correspondance_table(intent)
    as_data = intent["autonomous_systems"][as_name]
    neighbor_policies = as_data.get("neighbors", {})
    routers = []

    for router in as_data["routers"]:
        router_num = router["id"]
        router_data = {
            "hostname": router["hostname"],
            "AS_name": as_name,
            "console_port": router.get("console_port"),
            "loopback_ip": generate_ipv6(as_data["address_plan"]["loopback_base"], router_num),
            "router_id": generate_router_id(router["hostname"], router_num),
            "interfaces": [],
            "igp": as_data["igp"],
            "asn": as_data["as_number"],
            "ebgp_peers": [],
        }

        # Generate interface IPs and neighbor info
        for intf in router["interfaces"]:
            neighbor_hostname = intf.get("neighbor")
            neighbor_num = router_lookup.get(neighbor_hostname)

            is_bgp = intf.get("remote_as") and intf["remote_as"] != as_data["as_number"]

            if is_bgp:
                # Find neighbor's AS data to compare
                remote_as_data = next(as_d for _, as_d in intent["autonomous_systems"].items() 
                                    if as_d["as_number"] == intf["remote_as"])
                # Use the smaller AS number's base to ensure consistency on both sides
                as_sorted = sorted([as_data, remote_as_data], key=lambda x: x["as_number"])
                common_base = as_sorted[0]["address_plan"]["physical_base"]
            else:
                common_base = as_data["address_plan"]["physical_base"]

            interface_ip = generate_ipv6(common_base, router_num, neighbor_num)

            router_data["interfaces"].append(
                {
                    "name": intf["name"],
                    "ip": interface_ip,
                    "neighbor": neighbor_hostname,
                    "ospf_cost": intf.get("ospf_cost"),
                    "remote_as": intf.get("remote_as"),
                }
            )

            # Detect eBGP
            if is_bgp:
                remote_as = intf["remote_as"]

                # Find the neighbor's specific IP on that link
                remote_ip = generate_ipv6(common_base, neighbor_num, router_num)
                
                # ---- Read neighbor policies ----
                # Read policies for this neighbor from intent (AS-local view)
                pol = neighbor_policies.get(str(remote_as), {})  # JSON keys are strings

                relationship = pol.get("relationship")  # "customer" | "peer" | "provider"
                community_in = pol.get("community_in")  # e.g., "65002:20"
                export_policy = pol.get("export_policy")

                # ---- Local Preference automation (customer > peer > provider) ----
                local_pref = None
                if relationship == "customer":
                    local_pref = 200
                elif relationship == "peer":
                    local_pref = 150
                elif relationship == "provider":
                    local_pref = 100

                # ---- Inbound policy: one route-map for both community and local-pref ----
                needs_in_policy = (community_in is not None) or (local_pref is not None)
                route_map_in = f"RM-IN-{remote_as}" if needs_in_policy else None

                # ---- Outbound policy 
                community_match = None
                community_list = None
                route_map_out = None

                # ---- Outbound valley-free export: only customer-learned paths to providers/peers ----
                customer_comm = f"{as_data['as_number']}:10"   # ex: 65002:10

                # Export only customer paths to providers and peers
                if relationship in ("provider", "peer"):
                    community_match = customer_comm
                    community_list = "CL-CUSTOMER-ONLY"
                    route_map_out = f"RM-OUT-{remote_as}-CUST-ONLY"

                router_data["ebgp_peers"].append(
                    {
                        "ip": remote_ip,
                        "remote_as": remote_as,
                        "interface": intf["name"],

                        # Relationship & selection attributes
                        "relationship": relationship,
                        "local_pref": local_pref,

                        # IN policy (community + local-pref)
                        "community_in": community_in,
                        "route_map_in": route_map_in,

                        # OUT policy (filtering)
                        "export_policy": export_policy,
                        "community_match": community_match,
                        "community_list": community_list,
                        "route_map_out": route_map_out,
                    }
                )

        # iBGP peers
        router_data["ibgp_peers"] = [
            {"ip": generate_ipv6(as_data["address_plan"]["loopback_base"], r["id"])}
            for r in as_data["routers"]
            if r["hostname"] != router["hostname"]
        ]

        routers.append(router_data)

    return routers

if __name__ == "__main__":
    env = Environment(loader=FileSystemLoader("templates"))

    template = env.get_template("router_ospf.j2")

    router_data = {
        "hostname": "R4",
        "loopback_ip": "FC00:0:0:4::1",
        "ospf_cost": 50,
        "interfaces": [
            {"name": "FastEthernet0/0", "ip": "2001:4:5::1"},
            {"name": "GigabitEthernet1/0", "ip": "2001:4:6::1"},
        ],
        "router_id": 4,
    }

    config_output = template.render(**router_data)
    print(config_output)

    output_file = f"output/{router_data['hostname']}.cfg"

    with open(output_file, "w") as f:
        f.write(config_output)
