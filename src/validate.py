import json
import os
import sys

try:
    from jsonschema import validate, ValidationError
except ImportError:
    print("Error: The 'jsonschema' library is not installed.")
    print("Please install it with: pip install jsonschema")
    sys.exit(1)


def validate_intent(intent_path="intent/network.json", schema_path="intent/schema.json"):
    """
    Validate a network intent JSON file against its schema, then run
    additional logical consistency checks specific to the MPLS/VPN structure.
    """

    if not os.path.exists(intent_path):
        raise FileNotFoundError(f"Intent file not found: {intent_path}")

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(intent_path, "r", encoding="utf-8") as f:
        intent_data = json.load(f)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_data = json.load(f)

    try:
        validate(instance=intent_data, schema=schema_data)
    except ValidationError as e:
        print("-" * 30)
        print(f"ERROR: {e.message}")
        print(f"LOCATION: {' -> '.join(str(p) for p in e.absolute_path)}")
        print(f"EXPECTED: {e.validator}")
        print("-" * 30)
        raise

    _validate_business_rules(intent_data)

    print("[OK] Validation successful")
    return True


def _validate_business_rules(intent_data):
    """
    Additional semantic checks not always easy or clean to enforce in JSON Schema.
    """

    vrf_names = {vrf["name"] for vrf in intent_data.get("vrfs", [])}

    routers = intent_data.get("routers", {})
    p_routers = routers.get("P_ROUTERS", [])
    pe_routers = routers.get("PE_ROUTERS", [])
    ce_routers = routers.get("CE_ROUTERS", [])

    all_router_names = {r["hostname"] for r in (p_routers + pe_routers + ce_routers)}
    pe_router_ids = {pe["router_id"] for pe in pe_routers}

    # Check unique hostnames
    if len(all_router_names) != len(p_routers) + len(pe_routers) + len(ce_routers):
        raise ValueError("Duplicate router hostname detected")

    # Check unique router IDs
    all_router_ids = [r["router_id"] for r in (p_routers + pe_routers + ce_routers)]
    if len(all_router_ids) != len(set(all_router_ids)):
        raise ValueError("Duplicate router_id detected")

    # Check P routers
    for router in p_routers:
        for interface in router.get("interfaces", []):
            neighbor = interface.get("neighbor")
            if neighbor and neighbor not in all_router_names:
                raise ValueError(
                    f"P router '{router['hostname']}' has unknown neighbor '{neighbor}'"
                )

    # Check PE routers
    for router in pe_routers:
        ibgp_to = router.get("ibgp_to")
        if ibgp_to and ibgp_to not in pe_router_ids:
            raise ValueError(
                f"PE router '{router['hostname']}' has ibgp_to='{ibgp_to}' "
                f"which does not match any PE router_id"
            )

        client_awareness = router.get("client_awareness", {})
        sites = client_awareness.get("sites", {})

        for vrf_name in sites.keys():
            if vrf_name not in vrf_names:
                raise ValueError(
                    f"PE router '{router['hostname']}' references unknown VRF "
                    f"in client_awareness.sites: '{vrf_name}'"
                )

        for interface in router.get("interfaces", []):
            vrf = interface.get("vrf")
            if vrf and vrf not in vrf_names:
                raise ValueError(
                    f"PE router '{router['hostname']}' has interface '{interface['name']}' "
                    f"using unknown VRF '{vrf}'"
                )

    # Check CE routers
    for router in ce_routers:
        vrf = router.get("vrf")
        if vrf not in vrf_names:
            raise ValueError(
                f"CE router '{router['hostname']}' references unknown VRF '{vrf}'"
            )

    # Check total_clients consistency on each PE
    for router in pe_routers:
        client_awareness = router.get("client_awareness", {})
        total_clients = client_awareness.get("total_clients")
        sites = client_awareness.get("sites", {})
        computed_total = sum(sites.values())

        if total_clients != computed_total:
            raise ValueError(
                f"PE router '{router['hostname']}': total_clients={total_clients} "
                f"but sum(sites)={computed_total}"
            )


if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else "intent/network.json"

    try:
        validate_intent(target_file)
    except Exception as e:
        print(f"[FAIL] {e}")
        sys.exit(1)