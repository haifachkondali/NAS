def generate_ipv4(my_num, neighbor_num, is_pe_ce=False, is_ce_context=False):
    """
    my_num: l'ID du routeur qui exécute le script.
    neighbor_num: l'ID du voisin.
    is_pe_ce: True si c'est un lien Client-Fournisseur.
    is_ce_context: True si le routeur qui génère sa config est dans CE_ROUTERS.
    """
    if is_pe_ce:
        # Dans un lien PE-CE, le sous-réseau est TOUJOURS l'ID du CE.
        # Si je suis le CE, mon ID est mon numéro de réseau.
        # Si je suis le PE, l'ID du voisin (neighbor_num) est mon numéro de réseau.
        subnet = my_num if is_ce_context else neighbor_num
        
        # L'hôte : .2 si je suis un CE, .1 si je suis un PE
        host = "2" if is_ce_context else "1"
        return f"192.168.{subnet}.{host}"
    
    else:
        # Backbone classique (P-P, P-PE)
        ids = sorted([int(my_num), int(neighbor_num)])
        subnet = f"{ids[0]}{ids[1]}"
        host = "1" if int(my_num) < int(neighbor_num) else "2"
        return f"10.0.{subnet}.{host}"