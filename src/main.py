from generator import load_intent, generate_router_data
from validate import validate_intent
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import argparse
import os
import sys


def print_help():
    print("Usage: python main.py [--file <intent_file>] [--output <output_folder>] [--deploy]")
    print("\nOptions:")
    print("  --file, -f      Path to the intent file inside intent/ (default: network.json)")
    print("  --output, -o    Path to output folder (default: output/)")
    print("  --deploy, -d    Deploy configs to routers after generation")
    print("  --help, -h      Show this help message")


def render_router_config(env, router_data, igp, ldp_enabled=False):
    """
    Build the final config for one router according to its type.

    Expected router_data fields:
        - hostname
        - router_type: "P", "PE", or "CE"
        - optional port
        - all template variables needed by Jinja
    """

    router_type = router_data.get("router_type", "").upper()
    template_map = {
        "P": "router_p.j2",
        "PE": "router_pe.j2",
        "CE": "router_ce.j2",
    }

    template_name = template_map.get(router_type)
    if not template_name:
        raise ValueError(f"Unsupported router type: '{router_type}'")

    try:
        template = env.get_template(template_name)
    except TemplateNotFound:
        raise FileNotFoundError(f"Template not found: {template_name}")

    return template.render(**router_data, igp=igp, ldp_enabled=ldp_enabled)


def main(intent_file, output_folder, deploy=False):
    intent = load_intent(intent_file)

    igp = intent.get("igp", "").strip()
    ldp_enabled = intent.get("ldp_enabled", False)

    if igp.lower() != "ospf":
        print(f"Unsupported IGP '{igp}'. Only OSPF is currently supported.")
        sys.exit(1)

    env = Environment(loader=FileSystemLoader("templates"))

    router_data_list = generate_router_data(intent)

    if not isinstance(router_data_list, list):
        print("[ERROR] generate_router_data(intent) must return a list of router data dictionaries.")
        sys.exit(1)

    deploy_list = []

    for router_data in router_data_list:
        hostname = router_data.get("hostname", "UNKNOWN")
        port = router_data.get("port", "N/A")

        print(f"Generating config for router {hostname}..., port: {port}")

        try:
            full_config = render_router_config(
                env=env,
                router_data=router_data,
                igp=igp,
                ldp_enabled=ldp_enabled
            )
        except Exception as e:
            print(f"[ERROR] Failed to generate config for {hostname}: {e}")
            continue

        output_path = os.path.join(output_folder, f"{hostname}_config.cfg")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_config)

        if deploy and "port" in router_data:
            deploy_list.append({
                "hostname": hostname,
                "port": router_data["port"],
                "as_number": router_data.get("as_number"),
                "config_file_path": output_path
            })

    if deploy and deploy_list:
        from remote_deploy import deploy_parallel

        print(f"Starting parallel deployment for {len(deploy_list)} routers...")
        deploy_parallel(deploy_list, max_workers=8)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Router Config Generator", add_help=False)
    parser.add_argument("--file", "-f", type=str, default="network.json",
                        help="Path to the intent file inside intent/")
    parser.add_argument("--output", "-o", type=str, default="output/",
                        help="Path to output folder (default: output/)")
    parser.add_argument("--deploy", "-d", action="store_true",
                        help="Deploy configs to routers after generation")
    parser.add_argument("--help", "-h", action="store_true",
                        help="Show help message and exit")

    args = parser.parse_args()

    if args.help:
        print_help()
        sys.exit(0)

    intent_file = os.path.join("intent", args.file)
    output_folder = args.output

    if args.deploy:
        print("Deployment after generation is enabled.")

    if not os.path.exists(intent_file):
        print(f"Erreur : le fichier d'intention '{intent_file}' est introuvable.")
        sys.exit(1)

    os.makedirs(output_folder, exist_ok=True)

    try:
        validate_intent(intent_file)
    except Exception as e:
        print(f"[ERROR] Intent file validation failed: {e}")
        sys.exit(1)

    main(intent_file, output_folder, deploy=args.deploy)