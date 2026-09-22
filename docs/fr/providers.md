# Connexions aux fournisseurs de modèles (0.45)

[English](../en/providers.md) · [한국어](../ko/providers.md) · [简体中文](../zh-CN/providers.md) · [日本語](../ja/providers.md) · [Español](../es/providers.md) · [Français](../fr/providers.md)

Conservez le SDK et le format natif. Modifiez base_url et api_key ; utilisez une clé de passerelle ou une identité individuelle d’agent facultative. La vraie clé du fournisseur reste sur la passerelle.

Un fournisseur par déploiement, avec liste explicite de modèles et chemins exacts. Utilisez des projets Compose, ports et volumes séparés pour plusieurs fournisseurs.

Le SSE est entièrement mis en tampon et inspecté avant transmission dans son format initial. Ce n’est pas du streaming en temps réel. Limites par défaut : 120 secondes et 1 MiB. Les réponses incomplètes ou non prises en charge sont bloquées.

Le texte et les appels de fonctions exécutées par le client sont pris en charge. Fichiers, médias, outils côté fournisseur, WebSocket, raisonnement chiffré et signatures thought Gemini sont exclus. Protégez séparément le chemin HTTP/MCP de l’exécution réelle.

Pour contrôler chaque agent, activez agent_key et Broker, enregistrez les outils et autorisez explicitement l’accès autonome dans la console, puis émettez une clé à utiliser dans le même paramètre api_key.

Les profils figurent dans deploy/selfhost/providers/. Remplacez YOUR_MODEL_ID et conservez la clé fournisseur dans /state/provider-key. La validation emploie les SDK Python officiels avec des services synthétiques, sans certifier toutes les fonctions réelles.

| Provider | Gateway base_url | API |
| --- | --- | --- |
| OpenAI | https://gateway.example.com/v1 | Chat Completions / Responses |
| Anthropic | https://gateway.example.com | Messages |
| Gemini native | https://gateway.example.com | v1beta generateContent / streamGenerateContent |
| Gemini OpenAI | https://gateway.example.com/v1beta/openai | Chat Completions |
| OpenRouter | https://gateway.example.com/api/v1 | Chat Completions |


[SDK examples / Docker commands](../en/providers.md) · [AISG](aisg.md)

## 0.44 · Buffered SSE

[Latence Buffered SSE et adéquation au déploiement](latency.md)

Le gateway collecte et inspecte la réponse complète prise en charge avant de livrer le contenu. Le délai du premier contenu comprend la collecte et l’inspection. Ce mode convient aux tâches pouvant attendre un résultat complet ; le chat interactif exige un budget de latence explicite.
