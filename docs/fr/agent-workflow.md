# Vérification modèle → MCP → modèle (0.44)

[English](../en/agent-workflow.md) · [한국어](../ko/agent-workflow.md) · [简体中文](../zh-CN/agent-workflow.md) · [日本語](../ja/agent-workflow.md) · [Español](../es/agent-workflow.md) · [Français](../fr/agent-workflow.md)

Connectez le SDK officiel OpenAI et le client MCP via deux passerelles indépendantes. Modifiez le base_url du modèle et l’URL MCP. Un même identifiant d’agent utilise des clés distinctes sur chaque passerelle.

Par défaut, le modèle est un scénario synthétique sans inférence réelle ni appel payant. Docker, Envoy et l’inspecteur vérifient la lecture autorisée pour A, refusée pour B, la suppression bloquée, le masquage des PII, la révocation des clés utilisées et des identifiants dont l’expiration est fixée dans le passé. Les décisions sont comparées aux traces du destinataire.

La validation OpenAI réelle exige un modèle explicite et un fichier de clé de test privé avec des permissions 0600. --model et --provider-key-file activent des appels payants avec des données métier synthétiques. Aucun résultat synthétique ne remplace un échec réel. Le 2026-09-18, les trois scénarios ont été validés avec OpenAI réel et `gpt-4.1-mini`, avec deux appels au modèle par scénario. La cible MCP et les données métier restent synthétiques. Cette validation concerne ce modèle et ce compte, pas tous les fournisseurs ni les environnements de production. Les cookies de réponse LLM sont supprimés ; les horodatages entiers bornés de Chat Completions, OpenAI Responses et des enveloppes SSE prises en charge est traité comme métadonnée temporelle. Les champs métier imbriqués restent inspectés.

Seuls les projets de test créés par cet exemple sont supprimés. La HA, les performances, le streaming temps réel et l’annulation ne sont pas qualifiés. Consultez le guide anglais pour les commandes et limites complètes.

```bash
pip install -e '.[dev,console,compat,llm-compat]'
python -m examples.agent_workflow --report .runtime-state/workflow-042.json
```

[Full setup / live mode / evidence](../en/agent-workflow.md)


## 0.42

La qualification élargie couvre un serveur MCP local réel, les pannes de l’inspecteur, la reprise et l’anti-rejeu sur un même hôte, et les contrats synthétiques de quatre fournisseurs. Elle ne certifie pas les MCP clients, les autres comptes réels ou la HA entre serveurs. Sur cinq secondes à 0,1 RPS par utilisateur hypothétique, 10 et 30 RPS ont produit les résultats attendus ; des réponses 503 sont apparues dès 50 RPS. Aucune suppression interdite ni fuite de PII dans ces échantillons. Ce ne sont ni des garanties de capacité ni des recommandations matérielles ; les détails sont dans le guide anglais.

[Detailed qualification and measurements](../en/agent-workflow.md#042-extended-qualification)

SSE : l’adresse divisée en deux fragments a été masquée avant livraison complète. Le fournisseur synthétique a terminé après le timeout client ; l’annulation immédiate de la génération n’est pas garantie.
