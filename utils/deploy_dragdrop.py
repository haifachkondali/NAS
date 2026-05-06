#!/usr/bin/env python3
"""Script de déploiement GNS3 - Mode glisser-déposer."""

import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from deploy import deploy_configs, find_project_root, find_router_mapping
except ImportError:
    print("[Erreur] Impossible d'importer le module deploy")
    sys.exit(1)


def find_best_source_dir(target_dir: str) -> str:
    """Choisit automatiquement le dossier source selon le nombre de routeurs."""
    project_root = find_project_root(target_dir)
    
    router_count = 0
    if project_root:
        try:
            mapping = find_router_mapping(project_root)
            router_count = len(mapping)
        except Exception:
            pass
    
    complex_candidates = [
        os.path.join(script_dir, "output_complex"),
        os.path.join(script_dir, "outputcomplexe"),
        os.path.join(project_root, "output_complex") if project_root else None,
        os.path.join(project_root, "outputcomplexe") if project_root else None,
    ]
    
    simple_candidates = [
        os.path.join(os.path.dirname(script_dir), "output"),  # Remonte d'un cran (vers NAS/output)
        os.path.join(script_dir, "output"),                  # Cherche dans utils/output (au cas où)
        "output",                                            # Chemin relatif simple
    ]
    
    if router_count >= 14:
        for path in complex_candidates:
            if path and os.path.isdir(path):
                return os.path.abspath(path)
    
    for path in simple_candidates:
        if path and os.path.isdir(os.path.abspath(path)):
            return os.path.abspath(path)
    
    return os.path.join(script_dir, "output")


def main():
    """Fonction principale."""
    print("\n" + "=" * 50)
    print("Outil de deploiement GNS3 - Mode glisser-deposer")
    print("=" * 50 + "\n")
    
    if len(sys.argv) < 2:
        print("[Erreur] Veuillez fournir le chemin du dossier du projet GNS3")
        print("\nUtilisation:")
        print("  Windows: Glisser le dossier du projet GNS3 sur ce fichier")
        print("  Linux/Mac: python deploy_dragdrop.py <chemin_vers_projet_GNS3>")
        sys.exit(1)
    
    target_dir = sys.argv[1]
    
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        print(f"[Erreur] Le dossier cible n'existe pas ou n'est pas un dossier: {target_dir}")
        sys.exit(1)
    
    source_dir = find_best_source_dir(target_dir)
    
    print(f"Dossier du projet cible: {target_dir}")
    print(f"Dossier source des configs: {source_dir}\n")
    
    if not os.path.exists(source_dir):
        print(f"[Avertissement] Le dossier source n'existe pas: {source_dir}")
        print("Veuillez d'abord executer main.py pour generer les fichiers de configuration")
        sys.exit(1)
    
    try:
        count = deploy_configs(source_dir, target_dir, create_backup=True)
        
        if count > 0:
            print("\n" + "=" * 50)
            print(f"Deploiement reussi ! {count} fichier(s) deploye(s)")
            print("=" * 50)
        else:
            print("\n" + "=" * 50)
            print("Aucun fichier de configuration trouve pour le deploiement")
            print("=" * 50)
            sys.exit(1)
            
    except Exception as e:
        print(f"\n[Erreur] Exception lors du deploiement: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
