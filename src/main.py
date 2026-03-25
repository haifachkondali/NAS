from generator import load_intent, generate_router_data
from remote_deploy import deploy_parallel
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
        - optional console_port
        - all template variables needed by Jinja
    """

    parts = []
    router_type = router_data.get("router_type", "").upper()

    # IGP for core routers only
    if router_type in {"P", "PE"}:
        try:
            igp_template = env.get_template(f"router_{igp.lower()}.j2")
            parts.append(igp_template.render(**router_data))
        except TemplateNotFound:
            raise FileNotFoundError(f"Template not found: router_{igp.lower()}.j2")

    # Optional MPLS/LDP template for P / PE
    if ldp_enabled and router_type in {"P", "PE"}:
        try:
            mpls_template = env.get_template("router_mpls.j2")
            parts.append(mpls_template.render(**router_data))
        except TemplateNotFound:
            pass

    # BGP for PE / CE
    if router_type in {"PE", "CE"}:
        try:
            bgp_template = env.get_template("router_bgp.j2")
            parts.append(bgp_template.render(**router_data))
        except TemplateNotFound:
            raise FileNotFoundError("Template not found: router_bgp.j2")

    return "\n\n".join(part for part in parts if part.strip())


def main(intent_file, output_folder, deploy=False):
    intent = load_intent(intent_file)

    igp = intent.get("igp", "").strip()
    ldp_enabled = intent.get("ldp_enabled", False)

    if igp.lower() not in {"ospf", "rip"}:
        print(f"Unsupported IGP '{igp}'. Only OSPF and RIP are currently supported.")
        sys.exit(1)

    env = Environment(loader=FileSystemLoader("templates"))

    try:
        router_data_list = generate_router_data(intent)
    except TypeError:
        print("[ERROR] generate_router_data() must now accept the new full intent format.")
        sys.exit(1)

    if not isinstance(router_data_list, list):
        print("[ERROR] generate_router_data(intent) must return a list of router data dictionaries.")
        sys.exit(1)

    deploy_list = []

    for router_data in router_data_list:
        hostname = router_data.get("hostname", "UNKNOWN")
        console_port = router_data.get("console_port", "N/A")

        print(f"Generating config for router {hostname}..., port: {console_port}")

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

        if deploy and "console_port" in router_data:
            deploy_list.append({
                "hostname": hostname,
                "port": router_data["console_port"],
                "as_number": router_data.get("asn"),
                "config_file_path": output_path
            })

    if deploy and deploy_list:
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