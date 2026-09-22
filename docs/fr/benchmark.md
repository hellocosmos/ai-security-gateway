# Référence locale de performance

[English](../en/benchmark.md) · [한국어](../ko/benchmark.md) · [简体中文](../zh-CN/benchmark.md) · [日本語](../ja/benchmark.md) · [Español](../es/benchmark.md) · [Français](../fr/benchmark.md)

Cette commande mesure une **référence locale synthétique** reproductible via le listener Envoy installé, l’inspecteur gRPC ExtProc et la destination HTTP synthétique. Elle sert à comparer des révisions sur la même machine, sans certifier la capacité de production, la HA ou le trafic client.

## Exécution

Installez une fois avec `./scripts/install-console.sh`, puis arrêtez la console car le benchmark utilise les mêmes ports loopback.

```bash
.venv/bin/trapdefense-benchmark --scenario read --iterations 30
```

Les scénarios sont `read`, `pii`, `secret` et `response`. Les itérations sont limitées à 5–500 et le préchauffage à 0–50 ; par défaut, 30 requêtes sont mesurées après 3 préchauffages. Chaque requête traverse le proxy et crée une preuve nettoyée, sans destination métier externe ni API de modèle.

## Interpréter le JSON

Utilisez `p50_ms`, `p95_ms`, `mean_ms` et `sequential_requests_per_second` uniquement comme référence de régression locale. Les décomptes de décisions et statuts HTTP confirment que le résultat attendu n’a pas changé. Le rapport inclut OS, architecture, Python et CPU logiques, mais exclut le nom d’hôte et le contenu inspecté.

Comparez seulement avec charge, Docker, alimentation, scénario, itérations et politique équivalents. Exécutez au moins trois fois et conservez le résultat médian. Capacité parallèle, réutilisation des connexions, gros corps, SSE prolongé, reprise et multi-nœuds nécessitent d’autres tests.

Consultez [console](console.md), [architecture](architecture.md), [éditions](editions.md) et [sécurité](security.md).

## Pool d’inspecteurs AI Firewall

[Pool d’inspecteurs AI Firewall](inspector-pool.md)

## 0.44 · Buffered SSE

[Latence Buffered SSE et adéquation au déploiement](latency.md)

Le gateway collecte et inspecte la réponse complète prise en charge avant de livrer le contenu. Le délai du premier contenu comprend la collecte et l’inspection. Ce mode convient aux tâches pouvant attendre un résultat complet ; le chat interactif exige un budget de latence explicite.
