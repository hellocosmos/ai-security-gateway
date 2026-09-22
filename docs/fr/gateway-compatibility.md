# Compatibilité des clients de passerelle — 0.45

> [Connexions aux fournisseurs de modèles](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [Connecter, identifier, contrôler, vérifier](aisg.md). La passerelle utilise une clé de déploiement ou un JWT vérifié. agent_key identifie un agent enregistré sans IAM externe. JWT identity_mode: agent utilise les attributs vérifiés du tenant et de l’agent ; delegated exige aussi utilisateur, tâche et délégation. Les agents existants nécessitent une délégation par défaut.

[English](../en/gateway-compatibility.md) · [한국어](../ko/gateway-compatibility.md) · [简体中文](../zh-CN/gateway-compatibility.md) · [日本語](../ja/gateway-compatibility.md) · [Español](../es/gateway-compatibility.md) · [Français](../fr/gateway-compatibility.md)

Le client doit pouvoir remplacer l’URL HTTP/MCP distante par TrapDefense et envoyer une clé de connexion ou un JWT Bearer OAuth. L’authentification client→TrapDefense reste séparée de TrapDefense→cible.

| Chemin | Preuve 0.42 |
|---|---|
| JSON HTTP générique | Intégration synthétique vérifiée avec HTTPX |
| SDK Python MCP officiel 1.30.0 | Initialisation, notification et liste d’outils MCP `2025-11-25` vérifiées en intégration synthétique |
| OAuth au format Entra | `scp`, `tid`, `oid`, `azp`, discovery, DCR, PKCE et resource binding vérifiés synthétiquement ; aucun tenant Entra réel |
| OAuth au format Okta | `scp` sous forme de tableau et `cid` vérifiés dans le flux synthétique complet ; aucun serveur Okta réel |
| Keycloak synthétique / local réel | En plus du flux synthétique, un Keycloak 26.7.3 officiel fixé par digest a émis un token local réel validé via discovery et JWKS |
| MCP distant VS Code 1.135 | Le produit installé a affiché `Running`, découvert un outil et produit les trois receipts MCP avec une requête d’initialisation `2025-11-25` |
| MCP avec état, SSE longue durée, WebSocket, stdio | Non pris en charge ; session headers et upstream SSE échouent en mode fermé |
| HA multinœud | Non prise en charge ; une instance avec SQLite, replay et audit state locaux |

`gateway_auth` utilise `client_key` ou `jwt`. En mode JWT, TrapDefense est un OAuth Resource Server avec metadata RFC 9728 et `WWW-Authenticate`. `scope`/`scp` accepte une chaîne séparée par des espaces ou un tableau ; `authorized_parties` optionnel limite `azp`, `appid` ou `cid`. En 0.42, les app roles Entra dans `roles` ne sont pas interprétés comme des scopes.

`target_auth` accepte `none`, `passthrough_bearer`, `static_bearer` et `static_api_key`. Le JWT de passerelle n’est pas transmis à la cible. L’IdP externe ou un credential provider séparé gère login, émission, refresh et OBO.

Avant d’approuver une intégration, vérifiez URL, deux authentifications, initialisation/découverte MCP, action autorisée et refusée, effet côté cible, PII/secret, 401 cible, panne d’inspection et absence de fallback direct. Consultez commandes, configuration et sources dans le [guide anglais](../en/gateway-compatibility.md).


Les preuves actuelles couvrent OpenAI réel avec MCP synthétique, les fixtures SDK officielles, MCP/Keycloak locaux réels et l’initialisation/découverte VS Code. Le SSE modèle est entièrement mis en mémoire ; MCP avec état, IAM client, HA inter-hôtes et capacité de production ne sont pas certifiés. Voir [qualification et limites de 0.42](agent-workflow.md).
