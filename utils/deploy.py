#!/usr/bin/env python3
"""Outil de déploiement de configuration GNS3."""

import os
import shutil
import argparse
import re
from datetime import datetime


def find_project_root(path):
    """Trouver la racine d'un projet GNS3."""
    current = os.path.abspath(path)
    for _ in range(10):
        if os.path.exists(os.path.join(current, "project-files", "dynamips")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def find_router_mapping(project_dir):
    """Construire le mapping {hostname: (uuid_folder, node_id)}."""
    dynamips_dir = os.path.join(project_dir, "project-files", "dynamips")
    mapping = {}
    
    for uuid_folder in os.listdir(dynamips_dir):
        configs_dir = os.path.join(dynamips_dir, uuid_folder, "configs")
        if not os.path.isdir(configs_dir):
            continue
            
        for config_file in os.listdir(configs_dir):
            match = re.match(r"i(\d+)_startup-config\.cfg", config_file)
            if match:
                config_path = os.path.join(configs_dir, config_file)
                with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
                    hostname_match = re.search(r"hostname\s+(\w+)", f.read())
                    if hostname_match:
                        mapping[hostname_match.group(1)] = (uuid_folder, f"i{match.group(1)}")
    
    return mapping


def fix_config(content, hostname):
    """Appliquer les corrections nécessaires à la configuration."""
    
    # Supprimer update-source invalide pour eBGP (conserve le saut de ligne)
    content = re.sub(
        r'\s+neighbor\s+\S+\s+update-source\s+(GigabitEthernet|FastEthernet)\d+/\d+\s*\n',
        '\n',
        content
    )
    
    # S'assurer que chaque interface se termine par 'no shutdown'
    lines = content.split('\n')
    fixed = []
    in_interface = False
    interface_lines = []
    
    for line in lines:
        if re.match(r'^\s*interface\s+\S+', line):
            if in_interface and interface_lines:
                if not any('no shutdown' in l.lower() for l in interface_lines):
                    insert_pos = len(interface_lines) - 1
                    while insert_pos > 0 and not interface_lines[insert_pos].strip():
                        insert_pos -= 1
                    interface_lines.insert(insert_pos + 1, ' no shutdown')
                fixed.extend(interface_lines)
            in_interface = True
            interface_lines = [line]
        elif in_interface and line.strip() == '!':
            interface_lines.append(line)
            if not any('no shutdown' in l.lower() for l in interface_lines[:-1]):
                interface_lines.insert(-1, ' no shutdown')
            fixed.extend(interface_lines)
            in_interface = False
            interface_lines = []
        elif in_interface:
            interface_lines.append(line)
        else:
            fixed.append(line)
    
    if in_interface and interface_lines:
        if not any('no shutdown' in l.lower() for l in interface_lines):
            interface_lines.append(' no shutdown')
        fixed.extend(interface_lines)
    
    content = '\n'.join(fixed)
    
    # Ajouter redistribute et network dans BGP si manquants
    if 'address-family ipv6' in content:
        lines = content.split('\n')
        fixed = []
        in_af = False
        
        for line in lines:
            fixed.append(line)
            if 'address-family ipv6' in line:
                in_af = True
            elif 'exit-address-family' in line and in_af:
                in_af = False
                fixed.pop()
                
                rip_match = re.search(r'ipv6 router rip\s+(\S+)', content)
                if rip_match and f'redistribute rip {rip_match.group(1)}' not in content:
                    fixed.append(f' redistribute rip {rip_match.group(1)}')
                elif 'ipv6 router ospf' in content and 'redistribute ospf 1' not in content:
                    fixed.append(' redistribute ospf 1')
                
                loopback_match = re.search(r'ipv6 address (FC00:0:0:\d+::1)/128', content)
                if loopback_match:
                    network_cmd = f' network {loopback_match.group(1)}/128'
                    if network_cmd not in content:
                        fixed.append(network_cmd)
                
                fixed.append(line)
        
        content = '\n'.join(fixed)
    
    return content


def deploy_configs(source_dir, target_dir, create_backup=True):
    """Déployer les fichiers de configuration vers le projet GNS3."""
    
    if not os.path.exists(source_dir):
        print(f"Erreur: Répertoire source '{source_dir}' introuvable")
        return 0
    
    project_root = find_project_root(target_dir)
    if not project_root:
        print(f"Erreur: Projet GNS3 introuvable à '{target_dir}'")
        return 0
    
    router_mapping = find_router_mapping(project_root)
    if not router_mapping:
        print("Erreur: Aucun routeur trouvé dans le projet")
        return 0
    
    print(f"Trouvé {len(router_mapping)} routeur(s): {', '.join(router_mapping.keys())}")
    
    if create_backup:
        backup_dir = os.path.join(
            project_root, "project-files", "dynamips",
            f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(backup_dir, exist_ok=True)
    
    count = 0
    dynamips_dir = os.path.join(project_root, "project-files", "dynamips")
    
    for filename in os.listdir(source_dir):
        match = re.match(r"([Rr]\d+)(?:_config)?\.cfg", filename)
        if not match or match.group(1) not in router_mapping:
            continue
        
        hostname = match.group(1)
        uuid_folder, node_id = router_mapping[hostname]
        
        src_file = os.path.join(source_dir, filename)
        target_file = os.path.join(dynamips_dir, uuid_folder, "configs", f"{node_id}_startup-config.cfg")
        
        with open(src_file, "r", encoding="utf-8", errors="ignore") as f:
            content = fix_config(f.read(), hostname)
        
        if create_backup and os.path.exists(target_file):
            shutil.copy2(target_file, os.path.join(backup_dir, f"{hostname}_{node_id}_startup-config.cfg"))
        
        with open(target_file, "w", encoding="utf-8", errors="ignore") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        
        print(f"  [OK] {filename} -> {hostname}")
        count += 1
    
    print(f"\n{count} fichier(s) déployé(s) avec succès")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Déployer les fichiers de config vers le projet GNS3")
    parser.add_argument("target_dir", help="Répertoire du projet GNS3")
    parser.add_argument("--source-dir", "-s", help="Répertoire source (par défaut: auto-détection)")
    parser.add_argument("--no-backup", action="store_true", help="Ne pas créer de sauvegarde")
    
    args = parser.parse_args()
    
    if not args.source_dir:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = find_project_root(args.target_dir)
        
        router_count = 0
        if project_root:
            try:
                mapping = find_router_mapping(project_root)
                router_count = len(mapping)
            except Exception:
                pass
        
        complex_candidates = [
            os.path.join(os.path.dirname(script_dir), "output_complex"),
            os.path.join(os.path.dirname(script_dir), "outputcomplexe"),
            os.path.join(project_root, "output_complex") if project_root else None,
            os.path.join(project_root, "outputcomplexe") if project_root else None,
        ]
        
        simple_candidates = [
            os.path.join(os.path.dirname(script_dir), "output"),
            os.path.join(project_root, "output") if project_root else None,
            "output",
        ]
        
        chosen = None
        if router_count >= 14:
            for path in complex_candidates:
                if path and os.path.isdir(path):
                    chosen = os.path.abspath(path)
                    break
        
        if not chosen:
            for path in simple_candidates:
                if path and os.path.isdir(path):
                    chosen = os.path.abspath(path)
                    break
        
        if not chosen:
            chosen = os.path.join(os.path.dirname(script_dir), "output")
        
        args.source_dir = chosen
        print(f"Répertoire de sortie auto-détecté: {args.source_dir}\n")
    
    deploy_configs(args.source_dir, args.target_dir, not args.no_backup)
