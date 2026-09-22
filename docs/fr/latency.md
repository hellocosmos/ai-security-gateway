# Latence Buffered SSE et adéquation au déploiement — 0.46

[en](../en/latency.md) · [ko](../ko/latency.md) · [zh-CN](../zh-CN/latency.md) · [ja](../ja/latency.md) · [es](../es/latency.md) · [fr](../fr/latency.md)

## 0.46 : attente d’admission bornée et processus d’inspection facultatifs

`gateway_admission_wait_ms` accepte 0 à 2000 ms, avec 0 par défaut : en cas de saturation, HTTP 503 est renvoyé immédiatement. Une valeur positive permet à au plus `gateway_max_inflight` requêtes authentifiées d’attendre. Dépassement et expiration renvoient 503 avant la lecture du corps ou l’appel à la destination. Le gateway ne relance jamais automatiquement un appel, y compris une action non idempotente.

`inspector_replicas` accepte 1, 2 ou 4, avec 1 par défaut. Les valeurs 2 et 4 lancent des processus d’inspection supervisés sur le même hôte Docker. Envoy répartit les flux entre les processus sains et reste fail-closed si l’inspection est indisponible. Ce n’est pas une HA entre hôtes. La perte d’un processus peut faire échouer une requête en cours alors que le résultat côté destination reste inconnu ; le client ne doit pas relancer l’action sans vérification.

Configurez ces champs dans `deploy/selfhost/deployment.yaml`, préparez et activez le changement selon la [procédure d’auto-hébergement](self-hosting.md), puis qualifiez-le sur l’hôte cible. En mode multiprocessus, les durées affichées par la console couvrent uniquement le processus du gateway ; les temps internes de l’inspecteur ne sont pas disponibles. Ce réglage ne garantit pas à lui seul une amélioration du débit ou du délai du premier contenu ; la mise en tampon de la réponse entière reste en place.

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

## 0.45 Chronologies par requête et admission

La console affiche les 64 dernières requêtes terminées dans le processus actuel. Chaque ligne ne conserve que des durées numériques, le statut HTTP et l’état de fin. Un ID aléatoire signé relie en interne adaptateur et inspecteur sans être affiché. Aucun corps, chemin, identifiant ni identité d’agent n’est conservé. Les rejets précoces figurent dans les résultats du gateway.

L’attente du flux d’inspection, la file des travailleurs et l’exécution sont distinctes. L’attente du corps commence après l’inspection des métadonnées et finit quand le corps tamponné atteint l’inspecteur. Elle inclut génération amont, transport et tampon Envoy. Les intervalles se chevauchent ou laissent des écarts ; ne les additionnez pas et ne les attribuez pas entièrement au modèle. Ils disparaissent au redémarrage.

`gateway_max_inflight` accepte les entiers 4–64 ; la valeur par défaut reste 32. Le changement est préparé puis activé pendant un redémarrage de maintenance. L’assistant conserve la valeur. Les requêtes excédentaires reçoivent HTTP 503. Une valeur moindre convient si davantage de rejets sont acceptables pour réduire la latence. À 48, l’essai synthétique n’a pas accru les succès et a produit HTTP 500.

Un seul essai synthétique ne fixe pas une valeur universelle. Répétez le tableau sur l’hôte cible avec réponses représentatives, concurrence, quotas du fournisseur et budgets de premier contenu et de fin.

[Décision sur le streaming interactif](interactive-streaming.md)

### Comparaison synthétique locale (2026-09-22)

Deux répétitions par réglage ont utilisé un service SSE de 32 fragments différés, une limite de corps de 32 KiB, 16 flux d’inspection et quatre travailleurs. Chaque répétition à 32 requêtes simultanées en a envoyé 64 ; à 64 requêtes simultanées, 128. La plage p95 du premier contenu ne concerne que les réponses HTTP 200 complètes à concurrence 32.

| Limite de passerelle | Terminées à concurrence 32 | p95 du premier contenu | Terminées à concurrence 64 | HTTP 500 à concurrence 64 | Pic échantillonné CPU / mémoire de l’application |
|---:|---:|---:|---:|---:|---:|
| 8 | 8/64 par essai | 1,16–1,18 s | 8/128 par essai | 0 | 62 % / 116 MiB |
| 16 | 16/64 par essai | 1,53–1,54 s | 16/128 par essai | 0 | 110 % / 127 MiB |
| **32 (défaut)** | **64/64 par essai** | **3,02–3,10 s** | **32/128 par essai** | **0** | **118 % / 148 MiB** |
| 48 | 64/64 par essai | 2,96–3,06 s | 32/128 par essai | 13–16 | 124 % / 161 MiB |

Aux limites 8–32, tous les essais autres que 200 ont renvoyé 503. Toutes les réponses réussies étaient complètes et les quatre demandes de reprise par réglage ont abouti. L’échantillonnage peut manquer de brefs pics. La cause des HTTP 500 à la limite 48 n’a pas été isolée ; ce résultat ne prouve pas un goulot Python. La mise en tampon de la réponse entière reste le principal compromis pour le délai du premier contenu. [Données brutes](../evidence/latency-045-synthetic.json) · Reproduire : `.venv/bin/python -m examples.latency.sweep --output docs/evidence/latency-045-synthetic.json`.
