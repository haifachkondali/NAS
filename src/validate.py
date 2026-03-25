import json
import os
import sys

try:
    from jsonschema import validate, ValidationError
except ImportError:
    # If the import fails (ImportError), warn the user.
    print("Error: The 'jsonschema' library is not installed.")
    print("Please install it with: pip install jsonschema")
    sys.exit(1)  # Stop the program with an error code.


def validate_intent(intent_path="intent/network.json", schema_path="intent/schema.json"):
    """
    Main function to validate the network intent file (JSON) against a defined schema.

    This function acts as a gatekeeper: it checks that the provided data follows
    the rules (types, required fields) before allowing the program to continue.

    Inputs:
        - intent_path (str): Absolute or relative path to the JSON file containing the network data.
                             Default: "intent/network.json"
        - schema_path (str): Path to the JSON schema file.
                             Default: "intent/schema.json"

    Outputs:
        - bool: Returns True if validation succeeds.
        - Raises a 'ValidationError' or 'FileNotFoundError' if validation fails.
    """

    # Check that files exist
    if not os.path.exists(intent_path):
        raise FileNotFoundError(f"Intent file not found: {intent_path}")

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    # Load JSON files
    with open(intent_path, "r") as f:
        intent_data = json.load(f)

    with open(schema_path, "r") as f:
        schema_data = json.load(f)

    # Perform validation
    try:
        validate(instance=intent_data, schema=schema_data)
        print("[OK] Validation successful")
        return True

    except ValidationError as e:
        print("-" * 30)
        print(f"ERROR: {e.message}")  # What happened
        print(f"LOCATION: {' -> '.join(str(p) for p in e.absolute_path)}")  # Where it happened
        print(f"EXPECTED: {e.validator}")  # Which rule was broken
        print("-" * 30)
        raise e


if __name__ == "__main__":
    # If the user provided a specific file as an argument, use it; otherwise use the default test file
    target_file = sys.argv[1] if len(sys.argv) > 1 else "intent/network.json"

    try:
        validate_intent(target_file)
    except Exception:
        # In case of any error, exit with a non-zero status code (1)
        sys.exit(1)
