# TrapDefense — Open-source AI Security Gateway

[0.45: Chronologies par requête et admission](docs/fr/latency.md) · [Décision sur le streaming interactif](docs/fr/interactive-streaming.md)

[0.44: Latence Buffered SSE et adéquation au déploiement](docs/fr/latency.md)

## Least Privilege, Least Agency

**Le moindre privilège limite l’accès. L’autonomie minimale encadre l’action autonome.**

Notre principe de conception : accorder uniquement les accès nécessaires et délimiter les actions qu’un agent peut accomplir seul. TrapDefense complète IAM et les permissions du service de destination en appliquant des politiques d’action et de données aux appels pris en charge et routés par la passerelle. L’identité facultative de l’agent ajoute des périmètres individuels, des délégations et des approbations.

[0.44: Espace d’exploitation (0.44)](docs/fr/operator-workspace.md)


[0.42: Vérification modèle → MCP → modèle](docs/fr/agent-workflow.md)

**0.44:** [Connexions aux fournisseurs de modèles](docs/fr/providers.md) — OpenAI · Anthropic · Gemini · OpenRouter.

**Connectez les API HTTP et les serveurs MCP distants compatibles via une frontière de sécurité explicite. Ajoutez une identité pour contrôler chaque agent.**

[Connecter, identifier, contrôler, vérifier →](docs/fr/aisg.md)

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Français](README.fr.md)

> **Open Source Preview 0.45 :** l’ensemble du runtime et de la console d’exploitation est sous licence MIT. L’Agent Access Broker intégré est implémenté et validé avec des données synthétiques, mais reste **Experimental** jusqu’à la validation d’IdP réels, de politiques client, de la HA et de la capacité.

TrapDefense est un AI Firewall auto-hébergé pour les flux HTTP et MCP pris en charge. Il inspecte les requêtes et réponses, applique des politiques d’action, de PII et de secrets, conserve des preuves assainies et peut autoriser une action selon l’agent, la délégation, la tâche, la ressource et une approbation humaine à usage unique.

```text
AI agent → gateway authentifié → liaison fiable de la requête → Envoy + inspector
         → Access Broker intégré optionnel → Tool / MCP / HTTP API
```

## La console en action

Écrans réels de la version 0.41 avec des données synthétiques. Le tableau de bord inclut un délai fournisseur volontaire de sept secondes ; ce ne sont pas des mesures de performance. La gestion des agents provient d’une autre démonstration locale.

![Tableau de bord](docs/assets/console-dashboard-041.png)

<table>
<tr>
<td width="50%"><img src="docs/assets/console-agents-041.png" alt="Autorisations des agents · Expérimental"><br><strong>Autorisations des agents · Expérimental</strong></td>
<td width="50%"><img src="docs/assets/console-provider-041.png" alt="Configuration du fournisseur"><br><strong>Configuration du fournisseur</strong></td>
</tr>
</table>

## Un seul produit open source

Il n’existe plus d’éditions de code Community et Enterprise. Ce dépôt public contient le Runtime Gateway, l’inspection HTTP/MCP, la protection PII/secret, la validation OAuth JWT externe, l’Agent Registry, la délégation, l’Access Broker, la human approval, l’audit, la console et l’auto-hébergement Docker. Aucun package runtime privé n’est requis.

De futurs services payants pourront fournir un cloud managé, l’exploitation de fleets, la HA multinœud, un audit externe immuable, des intégrations client et du support. Les fonctions actuelles d’enforcement restent ouvertes. [Modèle open source](docs/fr/editions.md)

## Auto-hébergement Docker

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
```

Ouvrez `http://localhost:18080` et connectez-vous en tant qu’`admin` avec le mot de passe choisi à l’initialisation. Le client doit permettre de configurer l’URL HTTP/MCP et `X-TD-Client-Key` ou un Bearer JWT. Le credential de la cible reste séparé et chaque installation utilise une origine fixe avec des mappings explicites. [Contrat d’auto-hébergement](docs/fr/self-hosting.md)

## Access Broker intégré (Experimental)

Le mode gateway seul vérifie la source de transfert et la politique locale sans revendiquer l’identité de l’agent. Le mode Broker exige un JWT émis par un IdP externe et un mapping explicite des claims. TrapDefense ne propage que les claims vérifiés et configurés vers `tenant_id`, `user_id`, `agent_id`, `delegation_id` et `task_id`. Une identité obligatoire absente bloque avant transfert.

Le Broker vérifie tenant, registry, scopes tool/resource, delegation, user, task, action, request digest et approval. Une action à haut risque produit `approval_required`; l’approbation ne peut être consommée qu’une seule fois pour la requête exacte. TrapDefense ne remplace pas les autorisations du service cible et n’émet pas de token OAuth aval.

## Démo locale et validation

```bash
./scripts/install-console.sh
./scripts/run-console.sh
```

Ouvrez [http://127.0.0.1:5176](http://127.0.0.1:5176), utilisez `admin` / `1234`, puis changez le mot de passe. La démo enregistre des agents et délégations synthétiques dans le vrai Broker sur fichiers et montre « approbation requise → approuver → une exécution → replay bloqué ».

```bash
pip install -e ".[dev]"
pytest -q
npm run check --prefix console
npm run build --prefix console
```

Ces résultats prouvent le comportement du code, du protocole et des scénarios synthétiques. Ils ne certifient pas un tenant Entra/Okta/Keycloak réel, Conditional Access, l’authentification MCP client, le routage obligatoire, la HA ou la capacité de production.

[Console](docs/fr/console.md) · [Architecture](docs/fr/architecture.md) · [Sécurité](docs/fr/security.md) · [Migration](docs/fr/migration.md) · [Référence anglaise](README.md)

## Licence

MIT. Le Runtime Gateway et l’Access Broker de ce dépôt sont entièrement open source.
