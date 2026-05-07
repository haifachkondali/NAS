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
    Validate network intent against JSON schema and business rules.
    
    Performs two-stage validation:
    1. JSON schema validation (structure)
    2. Business logic validation (semantic consistency)
    
    Args:
        intent_path (str): Path to network intent JSON file
        schema_path (str): Path to JSON schema file
        
    Returns:
        bool: True if validation passes
        
    Raises:
        FileNotFoundError: If intent or schema file not found
        ValidationError: If validation fails
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

    all_routers = p_routers + pe_routers + ce_routers
    all_router_names = [r["hostname"] for r in all_routers]
    pe_router_names = {pe["hostname"] for pe in pe_routers}
    ce_router_names = {ce["hostname"] for ce in ce_routers}

    # Check unique hostnames
    if len(set(all_router_names)) != len(all_router_names):
        raise ValueError("Duplicate router hostname detected")

    # Check unique router IDs in the provider core only (P + PE).
    # Check P routers
    for router in p_routers:
        for interface in router.get("interfaces", []):
            neighbor = interface.get("neighbor")
            if neighbor and neighbor not in set(all_router_names):
                raise ValueError(
                    f"P router '{router['hostname']}' has unknown neighbor '{neighbor}'"
                )

    # Check PE routers
    for router in pe_routers:
        ibgp_to = router.get("ibgp_to")
        if ibgp_to and ibgp_to not in pe_router_names:
            raise ValueError(
                f"PE router '{router['hostname']}' has ibgp_to='{ibgp_to}' "
                f"which does not match any PE hostname"
            )

        for interface in router.get("interfaces", []):
            vrf = interface.get("vrf")
            if vrf and vrf not in vrf_names:
                raise ValueError(
                    f"PE router '{router['hostname']}' has interface '{interface['name']}' "
                    f"using unknown VRF '{vrf}'"
                )

            # Core PE links must reference known backbone routers.
            neighbor = interface.get("neighbor")
            if not vrf and neighbor and neighbor not in set(all_router_names):
                raise ValueError(
                    f"PE router '{router['hostname']}' has unknown core neighbor '{neighbor}'"
                )

            # Access PE-CE links must reference known CE routers.
            connected_to = interface.get("connected_to")
            if vrf:
                if not connected_to:
                    raise ValueError(
                        f"PE router '{router['hostname']}' interface '{interface['name']}' in VRF '{vrf}' must define connected_to"
                    )
                if connected_to not in ce_router_names:
                    raise ValueError(
                        f"PE router '{router['hostname']}' references unknown CE '{connected_to}'"
                    )

                ce = next(c for c in ce_routers if c["hostname"] == connected_to)
                if ce.get("vrf") != vrf:
                    raise ValueError(
                        f"PE router '{router['hostname']}' interface '{interface['name']}' VRF '{vrf}' mismatches CE '{connected_to}' VRF '{ce.get('vrf')}'"
                    )

                if ce.get("connected_to") != router["hostname"]:
                    raise ValueError(
                        f"CE router '{connected_to}' must connect back to PE '{router['hostname']}'"
                    )

    # Check CE routers
    for router in ce_routers:
        vrf = router.get("vrf")
        if vrf not in vrf_names:
            raise ValueError(
                f"CE router '{router['hostname']}' references unknown VRF '{vrf}'"
            )

        if router.get("connected_to") not in pe_router_names:
            raise ValueError(
                f"CE router '{router['hostname']}' references unknown PE '{router.get('connected_to')}'"
            )


if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else "intent/network.json"

    try:
        validate_intent(target_file)
    except Exception as e:
        print(f"[FAIL] {e}")
        sys.exit(1)