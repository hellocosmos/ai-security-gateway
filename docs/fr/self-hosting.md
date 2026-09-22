# Auto-hébergement Docker — 0.44 Open Source Preview

> **0.44:** [Espace d’exploitation (0.44)](operator-workspace.md)


> [Connexions aux fournisseurs de modèles](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [Connecter, identifier, contrôler, vérifier](aisg.md). La passerelle utilise une clé de déploiement ou un JWT vérifié. agent_key identifie un agent enregistré sans IAM externe. JWT identity_mode: agent utilise les attributs vérifiés du tenant et de l’agent ; delegated exige aussi utilisateur, tâche et délégation. Les agents existants nécessitent une délégation par défaut.

[English](../en/self-hosting.md) · [한국어](../ko/self-hosting.md) · [简体中文](../zh-CN/self-hosting.md) · [日本語](../ja/self-hosting.md) · [Español](../es/self-hosting.md) · [Français](../fr/self-hosting.md)

## Choisir un point de départ pour 0.44

- **API de modèles :** utilisez un [profil fournisseur](providers.md) pour OpenAI, Anthropic, Gemini ou OpenRouter. Modifiez la base URL du SDK et gardez la clé fournisseur sur la passerelle.
- **Outils HTTP / MCP :** suivez le démarrage Docker puis remplacez la cible synthétique par un service explicitement configuré.
- **Évaluation complète :** lancez l’[exemple modèle → MCP → modèle avec deux agents](agent-workflow.md). Aucune clé payante par défaut ; le guide distingue preuve OpenAI réelle, tests synthétiques et limites mesurées.

L’authentification accepte `client_key`, `agent_key` et un `jwt` externe. Le registre local d’agents et leurs permissions sont optionnels et ne remplacent pas l’authentification cible. Chaque déploiement vise une origine fixe ; modèles et outils exécutés séparément nécessitent leurs propres routes. Le SSE modèle est entièrement mis en mémoire puis inspecté avant livraison, sans diffusion de tokens en temps réel.

0.44 fournit adaptateur, Envoy, inspecteur, console et authentifications séparées pour passerelle et cible. L’image se construit localement depuis les sources. TrapDefense Cloud reste prévu.

Le client doit pouvoir modifier l’URL MCP/API et utiliser `X-TD-Client-Key` ou un JWT Bearer OAuth. Chaque déploiement possède une cible fixe et des routes/outils explicites. Consultez la [matrice de compatibilité](gateway-compatibility.md).

| Type | Contrat |
|---|---|
| HTTP API | JSON, method/path exacts, maximum 1 MiB, réponse bornée |
| MCP | POST JSON sans état, méthodes de contrôle et outils explicites |
| Authentification passerelle | Clé ou JWT RS256 d’un IdP externe avec issuer/audience/scope et métadonnées RFC 9728 |
| Authentification cible | none, Bearer hérité transmis, Bearer/API Key fixe depuis fichier |
| Non pris en charge | Émission OAuth, connexion intermédiaire, DCR, OBO, cookies/sessions, SSE longue durée, WebSocket, stdio, SaaS interne fermé |

Le mot de passe sert à la console. La clé ou le JWT authentifie l’accès à TrapDefense. Le JWT est validé pour l’audience de la passerelle et n’est pas transmis à la cible, qui utilise un identifiant séparé. Une clé ou un JWT n’enregistre pas automatiquement un agent. L’Access Broker optionnel gère séparément registre et permissions ; l’IdP externe émet les jetons OAuth.

## Docker

Git et Docker Compose v2 sont requis. init demande un mot de passe administrateur de 12 caractères minimum, sans valeur par défaut. L’exemple cible un service synthétique et ne prouve aucune intégration réelle.

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
docker compose run --rm app client-key
```

Connectez-vous comme admin sur http://localhost:18080. Lisez la clé avec client-key et stockez-la dans les en-têtes secrets du client. La passerelle est sur http://localhost:18084 ; le jeton cible synthétique est Bearer synthetic-target-token.

Pour votre service, modifiez upstream, authority, chemins, outils et resource. `gateway_auth` accepte `client_key`, `agent_key` ou `jwt`; `target_auth` accepte `none`, `passthrough_bearer`, `static_bearer` et `static_api_key`. JWT et passthrough sont incompatibles. Les identifiants fixes utilisent un fichier 0600 lisible par UID 10001 et refusent les entrées en conflit.

L’UI gère politiques et mots de passe. Pour changer les correspondances : sauvegardez, exécutez policy-reset, render puis recréez les services. Seules les politiques enregistrées sont réinitialisées ; comptes, clés et événements restent présents. Les nouvelles requêtes utilisent la nouvelle politique.

Les ports sont liés à la boucle locale. L’accès distant nécessite un proxy TLS et un console_origin exact. Inspecteur et Envoy ne publient aucun port hôte. Prévenez le contournement avec les contrôles réseau.

Les volumes conservent l’état après redémarrage. Arrêtez puis sauvegardez les deux volumes et la configuration. down -v détruit les données. Le retour arrière restaure l’ancienne image et sa sauvegarde correspondante. Un port accessible ne prouve pas l’authentification : testez autorisation, blocage et effets sur la cible. SSE longue durée, HA et IAM client réel nécessitent une validation distincte.

[Compatibilité et VS Code](gateway-compatibility.md) · [Detailed examples, backup and migration (English)](../en/self-hosting.md)

## Activer l’Access Broker intégré

La suite décrit le **mode JWT delegated**. Consultez le [guide AISG](aisg.md) pour agent_key local et le mode agent autonome.

Utilisez `gateway_auth.mode: jwt` et déclarez dans `identity_claims` les noms de claims tenant, user, agent, delegation et task. Configurez ensuite `access_broker.enabled: true` et un `access_broker.tenant_id`. Enregistrez d’abord l’agent et la delegation du même tenant dans la console. Un claim obligatoire absent ou un tenant différent est bloqué avant transfert. Suivez le YAML exact de la [référence anglaise](../en/self-hosting.md). Le file store local est prévu pour un seul hôte, pas pour la HA multinœud.

## 0.44 · Buffered SSE

[Latence Buffered SSE et adéquation au déploiement](latency.md)

Le gateway collecte et inspecte la réponse complète prise en charge avant de livrer le contenu. Le délai du premier contenu comprend la collecte et l’inspection. Ce mode convient aux tâches pouvant attendre un résultat complet ; le chat interactif exige un budget de latence explicite.
