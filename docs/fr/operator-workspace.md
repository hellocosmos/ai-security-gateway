# Espace d’exploitation (0.44)

La console Docker propose configuration, changements en attente, restauration, diagnostic et aperçu dans Connections / System et Settings. Quatre profils de modèles génèrent les routes natives. Les outils HTTP/MCP sont bloqués par défaut : vérifiez actions, ressources et masquage. Les mappings avancés se modifient en JSON.

Enregistrer ne modifie pas le trafic actif. Les nouveaux secrets sont stockés dans des fichiers 0600 du volume d’état, sans réaffichage. Un champ vide conserve le secret existant. L’origine de console, l’authentification de passerelle et la confiance du broker restent dans le fichier de déploiement.

```bash
docker compose stop app envoy
docker compose run --rm app activate-config
docker compose up -d app envoy
```

Arrêtez les deux services pendant une maintenance. L’activation refuse une application active mais ne vérifie pas l’arrêt d’un Envoy externe. Les nouvelles routes réinitialisent leurs politiques. Comptes, clés et audit sont conservés. Dix révisions peuvent être préparées pour restauration, avec leur politique si disponible. Les fichiers secrets restent pour la récupération ; les fichiers externes doivent être montés. La connexion enregistrée prévaut sur le fichier, sauf la confiance d’identité.

Le diagnostic montre écouteurs, phase, statut, compteur et date des requêtes observées. Il ne contourne pas l’isolation et ne prouve pas l’authentification de destination. Les compteurs repartent à zéro au redémarrage. Consultez les événements. L’aperçu accepte du JSON synthétique de 8 KiB maximum et vérifie uniquement la politique locale, sans appel, autorisation d’agent, modification ou approbation. Il retourne décision, raison et types d’entités.

Premier essai : installer avec un mot de passe unique → identifiants distincts → requêtes autorisées, données personnelles synthétiques et blocage → événements → redémarrage et persistance → restauration. Un MCP et un compte réels exigent une validation séparée.

[Docker](self-hosting.md) · [Workflow](agent-workflow.md)

## 0.44 · Buffered SSE

[Latence Buffered SSE et adéquation au déploiement](latency.md)

Le gateway collecte et inspecte la réponse complète prise en charge avant de livrer le contenu. Le délai du premier contenu comprend la collecte et l’inspection. Ce mode convient aux tâches pouvant attendre un résultat complet ; le chat interactif exige un budget de latence explicite.
