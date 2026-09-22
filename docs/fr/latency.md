# Latence Buffered SSE et adéquation au déploiement — 0.44

[en](../en/latency.md) · [ko](../ko/latency.md) · [zh-CN](../zh-CN/latency.md) · [ja](../ja/latency.md) · [es](../es/latency.md) · [fr](../fr/latency.md)

Le gateway collecte et inspecte la réponse complète prise en charge avant de livrer le contenu. Le délai du premier contenu comprend la collecte et l’inspection. Ce mode convient aux tâches pouvant attendre un résultat complet ; le chat interactif exige un budget de latence explicite.

## Reproduire

Docker, Python 3.11+ et les dépendances console du projet sont requis. La commande construit une pile temporaire sans identifiants réels ni API payante et supprime conteneurs et volumes dans finally. Répétez au moins trois fois sur un hôte inactif avant une décision de déploiement.

```bash
python -m pip install -e ".[console,compat,llm-compat]"
python -m examples.latency.benchmark --output /tmp/latency.json
```

## Premier contenu p95 / fin p95 (ms)

2026-09-22 · synthetic fixture · short: 8 × 65 bytes content; long: 32 × 515 bytes content · 20 ms/chunk.

| Scenario | Concurrency | Direct | Gateway |
|---|---:|---:|---:|
| short | 1 | 56 / 202 | 232 / 233 |
| short | 8 | 58 / 197 | 420 / 421 |
| short | 32 | 97 / 219 | 1253 / 1253 |
| long | 1 | 53 / 752 | 822 / 822 |
| long | 8 | 69 / 745 | 1164 / 1164 |
| long | 32 | 89 / 726 | 3014 / 3014 |

Une exécution synthétique sur Docker ARM64 avec 14 CPU et 7.75 GiB, sans garantie de matériel minimal ni de capacité par utilisateur. Chaque cellule contient 12–64 échantillons ; p95 ne constitue pas un SLA. Connexion directe TLS, entrée locale du gateway HTTP et amont TLS. Sans identifiant fournisseur configuré, aucun modèle réel n’a été exécuté pour 0.44. Les preuves antérieures gardent leur date.

## Interprétation

La console affiche les 256 derniers échantillons par phase du processus. Le temps du gateway se termine avant la livraison client. Envoy inclut inspection de requête, collecte amont, inspection de réponse et transport. L’inspection inclut l’attente en file. Ces distributions incluent les échecs, ne sont pas corrélées par requête, ne peuvent être soustraites et sont effacées au redémarrage. Aucun échantillon signifie non mesuré, pas zéro.

## Limites

Sur 64 requêtes simultanées, 32 ont abouti et 32 ont reçu HTTP 503 ; aucune réponse HTTP 200 SSE incomplète. L’adresse PII fragmentée a été masquée. Avec la limite de test de 32 KiB, le dépassement a retourné HTTP 500 ; le délai amont de 10 secondes, 504, sans jeton de contenu. Les identifiants invalides ont retourné 401. Le statut seul n’identifie pas le composant ; les valeurs de production diffèrent.

## Limites des preuves

[JSON](../evidence/latency-044-synthetic.json) · [Guide opérateur](operator-workspace.md)


| Docker sampled resource | Peak CPU (100% = one core) | Peak memory (MiB) |
|---|---:|---:|
| App / Python inspector | 87.8% | 148.9 |
| Envoy | 3.91% | 37.38 |
| Synthetic fixture | 17.87% | 21.77 |

Ces pics échantillonnés couvrent toute l’exécution, ne sont pas des réservations ni des recommandations et peuvent manquer des pics brefs. La source synthétique partage l’hôte Docker : ce n’est pas une comparaison de langages. Plus d’attente et d’inspection ne prouve pas que Python est en cause ni que Go/Rust supprimerait le délai de buffering. Évaluez les tâches de fond par p95 de fin et taux d’erreur, le chat par p95 du premier contenu. Répétez sur l’hôte cible avec réponses et politiques représentatives, rejet de rafales et récupération. La génération peut continuer après annulation client. Dimensionnez selon concurrence, taille, fréquence et coût des politiques, pas le nombre d’employés.
