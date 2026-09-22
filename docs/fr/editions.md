# Un seul produit open source

> **AISG:** [Connecter, identifier, contrôler, vérifier](aisg.md). La passerelle utilise une clé de déploiement ou un JWT vérifié. agent_key identifie un agent enregistré sans IAM externe. JWT identity_mode: agent utilise les attributs vérifiés du tenant et de l’agent ; delegated exige aussi utilisateur, tâche et délégation. Les agents existants nécessitent une délégation par défaut.

[English](../en/editions.md) · [한국어](../ko/editions.md) · [简体中文](../zh-CN/editions.md) · [日本語](../ja/editions.md) · [Español](../es/editions.md) · [Français](../fr/editions.md)

TrapDefense 0.44 repose sur une seule base de code sous licence MIT. Runtime Gateway et Agent Access Broker sont publiés ensemble dans ce dépôt ; aucune distribution Python privée, provider entry point, license key ou edition switch n’est nécessaire.

## État de livraison

| Frontière | État | Preuve et limite |
|---|---|---|
| Runtime Gateway et console | **Open Source Preview** | Source publique, CI, chemin Envoy synthétique, politiques HTTP/MCP, contrôles PII/secret et UI locale. Le routage et la capacité de production nécessitent une validation dédiée. |
| Agent Access Broker intégré | **Experimental** | Registry, delegation, autorisation stricte, isolation tenant, transactions fichier et approbation unique liée à la requête. Les validations IdP/politique client et multi-node restent à faire. |
| Docker auto-hébergé | **Preview** | Adapter, Envoy, inspector, console, authentification gateway et credentials cible séparés construits depuis la source. Une origine fixe par installation. |
| Managed cloud, fleet, HA multinœud, audit externe immuable | **Planned** | Non livré et non présenté comme disponible. |

Le mode gateway-only applique l’inspection locale et vérifie la source de confiance. Le mode broker-enabled ajoute le mapping d’identité JWT vérifié, l’agent registry, la delegation, l’autorisation resource/action et l’approval. Les deux utilisent le même package open source.

Les futurs services payants pourront exploiter ce runtime comme managed service et ajouter fleet lifecycle, HA, audit externe, connecteurs, onboarding de politiques, SLA et support. Il s’agit d’une frontière de service et d’exploitation, pas d’un verrou de fonctions source.

Le file store convient aux processus POSIX d’un même hôte grâce au remplacement atomique et aux locks. Ce n’est pas une base distribuée et il ne convient pas à la HA NFS/SMB. Les tests synthétiques ne certifient pas un IdP réel, Conditional Access, l’authentification MCP client, le routage TLS ou la capacité.

[Docker 0.44](self-hosting.md) · [Architecture](architecture.md) · [Sécurité](security.md) · [Compatibilité](gateway-compatibility.md)
