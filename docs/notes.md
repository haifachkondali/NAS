# Project Notes

This file collects design decisions, conventions, and implementation details used throughout the GNS3 network automation project.

---

## Interface addressing conventions

- Physical interfaces use **IPv4 addressing** throughout the backbone and customer access links.
- **Note**: Initial design considered IPv6-only, but current implementation uses IPv4 exclusively.

### Why `no ip address` in templates?

In each interface block of the Jinja2 templates, the line `no ip address` is added to make it explicit that the interface must not receive any IPv4 address. This ensures : 

- **Prevention of accidental dual-stack:** Interfaces remain strictly IPv6-only.
- **Configuration Clarity:** The intent of keeping things IPV6-only is immediately visible when reading device configs.
- **Consistency:** Generated configs remain uniform regardless of platform defaults.

In short, `no ip address` documents and enforces the design decision "this interface is IPv6-only".

---

## Directory layout 

- `intent/`: JSON describing the desired network state (topology, addressing, routing protocols, policies, etc.).
- `templates/`: Jinja2 templates used to render device configurations from the intent data.
- `src/`: Python code that parses the intent, renders templates, and orchestrates generation/deployment.
- `utils/`: Deployment tools for mapping router hostnames to GNS3 UUIDs.
- `output/`: Generated configuration files per device; safe to delete/regenerate.

# BGP Policy & Routing logic
### Route redistribution in BGP
- **BGP Tagging:** `redistribute connected route-map RM-TAG-LOCAL` injects physical interface networks into BGP while tagging them with the local AS community (e.g., `ASN:10`).

- **IGP to BGP:** Routes learned via RIP or OSPF are pulled into the BGP table to ensure cross-AS reachability.

- **Anti-Loop Mechanism:** Route-maps (e.g., `RM-BGP-TO-OSPF`) are used when redistributing BGP back into IGPs to prevent re-injecting local-tagged routes, avoiding routing loops.

### Neighbor configuration 
- **Activate:** Neighbors are explicitly activated for the IPv6 unicast address family.

- **Send-community:** `send-community` is enabled to ensure BGP "tags" (communities) are passed between routers for policy enforcement. 
*BGP "communities" are like luggage tags. They carry extra information about a route (like "don't send this to the internet"). This command ensures this router passes those tags along to its neighbors.*

- **Next-Hop-Self:** Used in iBGP to ensure internal peers can reach external prefixes by setting the local router as the next hop.
*In iBGP, a router often passes on a route exactly as it received it, including the original "Next Hop" address. If the neighbor doesn't know how to reach that original address, the route is useless. This command tells this router to say, "If you want to reach this network, send the data to me."*

---
## Progress ✅

- [x] **Addressing automation**: `addressing.py` auto-generates loopback IPs, router-IDs, and link IPs from hostnames
- [x] **Unified IP generation**: Single `generate_ipv6()` function for both loopbacks (`/128`) and links (`/64`)
- [x] **Template generation**: `generator.py` creates RIP/OSPF/BGP configs per router
- [x] **iBGP auto-discovery**: All routers in AS peer via loopbacks automatically
- [x] **eBGP border detection**: `remote_as` ≠ local AS → border router
- [X] **Schema Validation**: Integrated jsonschema in `src/validate.py` to verify the `network.json` structure before generation.
- [X] **eBGP neighbor IP resolution**: Completed by cross-referencing remote AS address plans and IDs.
- [x] **BGP Policy Conventions**: Automated Valley-Free routing (Customer/Peer/Provider) using communities and local preference.
- [X] **OSPF cost automation**: Use `ospf_cost` from intent in templates
- [X] **Deployment Tools**: Completed both live Telnet deployment and offline UUID-based file mapping.

---

## Final Implementation Details

- **Validation**: All intent files are now validated against `intent/schema.json` to prevent deployment errors.
- **Complex Topologies**: The deployment script intelligently detects project size (14+ routers) to choose between standard `output` and `output_complex` directories.
- **Backup system**: The deployment utility creates automatic backups of existing GNS3 configs before overwriting them.