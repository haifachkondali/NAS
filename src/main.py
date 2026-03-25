from addressing import generate_ipv6
from generator import load_intent, generate_router_data
from remote_deploy import deploy_parallel 
from validate import validate_intent
from jinja2 import Environment, FileSystemLoader
import json, argparse, os, sys

def print_help():
    print("Usage: python main.py [--file <intent_file>] [--output <output_folder>]")
    print("\nOptions:")
    print("  --file, -f     Path to the intent file (default: intent/network.json)")
    print("  --output, -o   Path to output folder (default: output/)")
    print(" --deploy, -d    Deploy configs to routers after generation")
    print("  --help, -h     Show this help message")


def main(intent_file, output_folder, deploy=False):

    intent = load_intent(intent_file)

    template_file_loader = FileSystemLoader('templates')
    env = Environment(loader=template_file_loader)

    all_router_data = []
    deploy_list = []

    for as_name in intent["autonomous_systems"]:
        igp=intent["autonomous_systems"][as_name]["igp"]
        if igp.lower() not in ["ospf", "rip"]:
            print(f"Unsupported IGP '{igp}' for AS '{as_name}'. Skipping...")
            continue
        igp_template = env.get_template(f"router_{igp.lower()}.j2")
        bgp_template = env.get_template("router_bgp.j2")
        router_data_list = generate_router_data(intent, as_name)
        for router_data in router_data_list:
            print(f"Generating config for router {router_data['hostname']}..., port: {router_data.get('console_port', 'N/A')}")
            igp_part = igp_template.render(**router_data)
            bgp_part = bgp_template.render(**router_data)
            template = igp_part + "\n" + bgp_part
            output_path = os.path.join(output_folder, f"{router_data['hostname']}_config.cfg")
            with open(output_path, "w") as f:
                f.write(template)
            all_router_data.append(router_data)
            if deploy and "console_port" in router_data:
                deploy_list.append({
                    "hostname": router_data["hostname"],
                    "port": router_data["console_port"],
                    "as_number": router_data.get("asn", None),
<<<<<<< HEAD
                    "config_file_path": output_path,
                    "as_name": as_name
=======
                    "as_name" : router_data["AS_name"],
                    "config_file_path": output_path
>>>>>>> a919896b64780a3a7d5484cd99c1406bc67436f1
                })

    if deploy and deploy_list:
        deploy_parallel(deploy_list, max_workers=8) # Multi-threaded deployment


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Network Router Data Generator", add_help=False)
    parser.add_argument("--file", "-f", type=str, default="network.json", help="Path to the intent file")
    parser.add_argument("--output", "-o", type=str, default="output/", help="Path to output folder (default: output/)")
    parser.add_argument("--deploy", "-d", action="store_true", help="Deploy configs to routers after generation")
    parser.add_argument("-h", "--help", action="store_true", help="Show help message and exit")


    args=parser.parse_args()


    if args.help:
        print_help()
        exit(0)

    if args.file:
        intent_file = "intent/" + args.file

    if args.output:
        output_folder = args.output

    if args.deploy:
        print("Deployment after generation is enabled.")


    if not os.path.exists(intent_file):
        print(f"Erreur : Le fichier d'intention '{args.file}' est introuvable.")
        exit(1)



    # create output dir if doesn't already exist
    os.makedirs(output_folder, exist_ok=True)

    # Make sure intent_file is in the right format
    try:
        validate_intent(intent_file)
    except Exception as e:
        print(f"[ERROR] Intent file validation failed. Make sure the {intent_file} is valid.")
        sys.exit(1)



    main(intent_file, output_folder, deploy=args.deploy)
