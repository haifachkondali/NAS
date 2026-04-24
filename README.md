# GNS3 Network Config Generator

Générateur automatique de configurations réseau pour routeurs Cisco dans GNS3 (OSPF, BGP, MPLS, LDP, VRFs).

## Technologies utilisées

- **OSPF** : IGP du backbone MPLS
- **MPLS/LDP** : Transport des labels
- **BGP** : eBGP entre PE/CE, iBGP entre PE
- **VRF** : Isolation des clients (VPN)

## 1. Installation

```bash
pip install netmiko jsonschema jinja2
```

## 2. Modifier le fichier d'intention (si nécessaire)

Éditez <code>intent/network.json</code> pour décrire votre topologie.

> **NOTE :** Selon votre configuration, modifiez le champ `host` dans `remote_deploy.py` :

```python
device = {
    'device_type': 'cisco_ios_telnet',
    'host': '127.0.0.1',  # A modifier selon votre cas
    'port': port,
    'fast_cli': False,
}
```

**Cas courants :**

- GNS3 sur la même machine (Linux) : `127.0.0.1`
- GNS3 sur Windows + WSL : utilisez l'IP de Windows
- GNS3 sur machine distante : l'IP de cette machine

**Pour WSL, trouvez l'IP de Windows :**

```bash
grep nameserver /etc/resolv.conf | awk '{print $2}'
```

## 3. Valider le fichier d'intention

```bash
python3 src/validate.py intent/network.json
```

## 4. Générer les configurations
```bash
python3 src/main.py --file network.json
```

Les fichiers sont générés dans output/ : PE1_config.cfg, P1_config.cfg, CE1_config.cfg, etc.

## 5. Déploiement - Deux méthodes

### Méthode 1 : Glisser-déposer (Windows uniquement)

#### 1. Sur Windows, créez un dossier gns3_deploy et copiez ces fichiers :

<code>deploy_dragdrop.bat</code>

<code>deploy_dragdrop.py</code>

<code>deploy.py</code>

#### 2. Glissez-déposez votre dossier projet GNS3 sur <code>deploy_dragdrop.bat</code>

Le script copie automatiquement les configurations au bon endroit.

#### 3. Redémarrez les routeurs dans GNS3

### Méthode 2 : Ligne de commande (Windows, Linux, WSL)
Sous Windows :

```bash
python3 deploy.py "C:\Users\votre_user\GNS3\projects\mon_projet" --source-dir output
```
Sous WSL (Linux sur Windows) :

```bash
python3 deploy.py "/mnt/c/Users/votre_user/GNS3/projects/NAS_Project/mon_projet" --source-dir output
```
Sous Linux natif :

```bash
python3 deploy.py "/home/votre_user/GNS3/projects/mon_projet" --source-dir output
```

Puis redémarrez les routeurs dans GNS3.
