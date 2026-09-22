# TrapDefense — AI Security Gateway (0.44)

> [Connexions aux fournisseurs de modèles](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

[en](../en/aisg.md) · [ko](../ko/aisg.md) · [zh-CN](../zh-CN/aisg.md) · [ja](../ja/aisg.md) · [es](../es/aisg.md) · [fr](../fr/aisg.md)

Connectez les API HTTP et les serveurs MCP distants compatibles via une frontière de sécurité explicite. Ajoutez une identité pour contrôler chaque agent.

## Connecter, identifier, contrôler, vérifier

Démarrez l’environnement synthétique Docker, enregistrez un agent dans Access Broker, autorisez les outils choisis en mode autonome et émettez un identifiant. Modifiez l’URL du client et envoyez l’identifiant dans Authorization. Testez un appel autorisé et un appel refusé, puis consultez les décisions.

## Choisir le modèle d’identité

La passerelle utilise une clé de déploiement ou un JWT vérifié. agent_key identifie un agent enregistré sans IAM externe. JWT identity_mode: agent utilise les attributs vérifiés du tenant et de l’agent ; delegated exige aussi utilisateur, tâche et délégation. Les agents existants nécessitent une délégation par défaut.

## Cycle des identifiants

Les identifiants expirent après 1 heure, 24 heures ou au maximum 30 jours. Seuls les condensats sont stockés ; le nouvel identifiant est affiché une seule fois. Le renouvellement révoque immédiatement l’ancien. La révocation ou la désactivation de l’agent bloque les authentifications suivantes. Les identifiants de destination restent séparés.

## Compatibilité et limites

Une destination fixe par installation ; HTTP JSON et MCP JSON POST sans état avec des routes explicites. SSE, sessions avec état, stdio, WebSocket et appels internes SaaS ne sont pas pris en charge. Modifier le base_url du modèle ne redirige pas les outils exécutés séparément. Configurez chaque endpoint protégé et empêchez les contournements au niveau réseau.

## Approbations

L’accès autonome vérifie les outils, ressources et actions. Les actions à haut risque nécessitent une approbation limitée dans le temps et liée à la requête. Après validation, renvoyez la même requête avec la clé locale et X-TD-Approval-ID ; l’approbation est consommée une seule fois. Mirror ne crée ni ne consomme d’approbations.

## Preuves

La vérification synthétique locale ne certifie ni les IdP de production, ni les routes client, ni la HA, ni la capacité. Access Broker reste expérimental. Aucune inscription au cloud géré n’est disponible.

## Démarrage rapide

```bash
cd deploy/selfhost
docker compose -f compose.yaml -f compose.agent.yaml build app
docker compose -f compose.yaml -f compose.agent.yaml run --rm app init
docker compose -f compose.yaml -f compose.agent.yaml --profile smoke up -d
```

Console: `http://localhost:18080` · Gateway: `http://localhost:18084`

```text
API base_url: http://localhost:18084
MCP URL: http://localhost:18084/mcp
Authorization: Bearer <agent-credential>
```


```bash
# Set TD_AGENT_CREDENTIAL locally to the credential displayed once in the console.
# Register notes.read and enable autonomous access first.
curl --fail-with-body http://localhost:18084/api/notes \
  -H "Authorization: Bearer ${TD_AGENT_CREDENTIAL}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'

# Expected: HTTP 403. The fixture policy blocks notes.delete.
curl --fail-with-body http://localhost:18084/mcp \
  -H "Authorization: Bearer ${TD_AGENT_CREDENTIAL}" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"notes.delete","arguments":{}}}'
```

[Self-hosting](self-hosting.md) · [Identity](identity.md) · [Compatibility](gateway-compatibility.md)
