import json
import os
from jinja2 import Environment, FileSystemLoader

try:
    from addressing import generate_ipv4, generate_router_id
except ImportError:
    # Fallback si les fonctions ne sont pas encore prêtes
    def generate_router_id(hostname, router_num): return f"{router_num}.{router_num}.{router_num}.{router_num}"

def get_vrf_details(intent_data, vrf_name):
    """
    Recherche les détails d'une VRF (RD, RT) dans la configuration globale de l'intent.
    """
    for vrf in intent_data.get("vrfs", []):
        if vrf["name"] == vrf_name:
            return vrf
    return None

def generate_overlay_data(router_config, intent_data):
    """
    Prépare les données de VRF et de voisinage client (eBGP) pour un PE.
    """
    vrfs_config = {}

    # 1. Parcourir les interfaces pour trouver celles rattachées à une VRF
    for interface in router_config.get("interfaces", []):
        vrf_name = interface.get("vrf")
        if vrf_name:
            details = get_vrf_details(intent_data, vrf_name)
            
            if vrf_name not in vrfs_config:
                vrfs_config[vrf_name] = {
                    "name": vrf_name,
                    "rd": details["rd"] if details else "N/A",
                    "rt": details["rt"] if details else "N/A",
                    "interfaces": [],
                    "bgp_neighbors": []
                }
            
            # Ajouter l'interface à la configuration de cette VRF
            vrfs_config[vrf_name]["interfaces"].append({
                "name": interface["name"],
                "ip": interface["ip"],
                "mask": interface["mask"],
                "desc": interface.get("desc", "")
            })

            # 2. Mapping PE-CE : Chercher le voisin CE correspondant dans l'intent
            for ce in intent_data["routers"].get("CE_ROUTERS", []):
                # On lie le CE au PE si l'IP du PE est définie comme 'pe' (passerelle) dans le CE
                if ce.get("pe") == interface["ip"]:
                    vrfs_config[vrf_name]["bgp_neighbors"].append({
                        "ip": ce["ip"].split('/')[0], # Récupère l'IP sans le CIDR
                        "remote_as": ce["as"],
                        "hostname": ce["hostname"]
                    })

    return list(vrfs_config.values())

def generate_ce_data(router_config, intent_data):
    """
    LOGIQUE PERSONNE B : Prépare les données spécifiques pour un routeur Client (CE).
    """
    return {
        "hostname": router_config["hostname"],
        "as_number": router_config["as"],
        "vrf_membership": router_config["vrf"],
        "interface_name": router_config["interface"],
        "ip": router_config["ip"].split('/')[0],
        "mask": "255.255.255.252", # Masque /30 par défaut pour les liens PE-CE
        "pe_ip": router_config["pe"],
        "backbone_as": intent_data["backbone_as"]
    }

def generate_nas_router_data(router_hostname, intent_data):
    """
    Fonction principale d'orchestration pour le projet NAS.
    """
    router_data = {
        "hostname": router_hostname,
        "backbone_as": intent_data.get("backbone_as"),
        "igp_protocol": intent_data.get("igp")
    }
    
    # Cas 1 : Le routeur est un PE
    pe_list = intent_data["routers"].get("PE_ROUTERS", [])
    pe_config = next((r for r in pe_list if r["hostname"] == router_hostname), None)
    
    if pe_config:
        router_data["role"] = "PE"
        router_data["loopback0"] = pe_config["loopback0"]
        router_data["bgp_rid"] = pe_config.get("bgp_rid")
        router_data["ibgp_target"] = pe_config.get("ibgp_to")
        # Insertion des données VRF (Personne B)
        router_data["vrfs_config"] = generate_overlay_data(pe_config, intent_data)
        # On garde les interfaces pour la config physique (Personne A)
        router_data["interfaces"] = pe_config["interfaces"]
        return router_data

    # Cas 2 : Le routeur est un CE
    ce_list = intent_data["routers"].get("CE_ROUTERS", [])
    ce_config = next((r for r in ce_list if r["hostname"] == router_hostname), None)
    
    if ce_config:
        router_data["role"] = "CE"
        router_data.update(generate_ce_data(ce_config, intent_data))
        return router_data

    # Cas 3 : Le routeur est un P (Backbone uniquement)
    p_list = intent_data["routers"].get("P_ROUTERS", [])
    p_config = next((r for r in p_list if r["hostname"] == router_hostname), None)
    
    if p_config:
        router_data["role"] = "P"
        router_data["loopback0"] = p_config["loopback0"]
        router_data["interfaces"] = p_config["interfaces"]
        return router_data

    return None

if __name__ == "__main__":
    # Petit test local pour vérifier la structure
    print("Logique Generator NAS chargée.")