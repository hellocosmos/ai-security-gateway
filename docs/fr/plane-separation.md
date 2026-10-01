# Séparation du plan de contrôle et du plan de données (0.47)

[English](../en/plane-separation.md) · [한국어](../ko/plane-separation.md) · [简体中文](../zh-CN/plane-separation.md) · [日本語](../ja/plane-separation.md) · [Español](../es/plane-separation.md) · [Français](../fr/plane-separation.md)

**Garantie :** lorsque la console (plan de contrôle) s’arrête ou plante, ou que sa base de données est verrouillée ou endommagée, le plan de données continue d’appliquer son **dernier instantané de politique vérifié**. Lorsque l’inspection ou le stockage des preuves est indisponible, le plan de données échoue toujours en mode fermé. Aucune requête n’atteint la destination sans verdict d’inspection.

Il s’agit d’une séparation des domaines de panne sur un seul hôte Docker, pas d’une HA multinœud.

## Services

| Service Compose | Rôle | Écoute | Détient |
|---|---|---|---|
| `app` | Plan de contrôle : console, publication des politiques, CLI (`init`, `client-key`, `activate-config`) | 18080 (publié) | `console.sqlite`, clé Ed25519 de **signature** des politiques (volume `control-keys`) |
| `dataplane` | Passerelle, inspecteur (ou groupe d’inspecteurs), spool de preuves | 18084 (publié), 18081 et 18085 (internes) | Uniquement la clé de **vérification** des politiques (`policy-trust`, lecture seule), nonces, état du broker |
| `envoy` | Proxy d’inspection privé | 18082 (interne) | Configuration générée |

Le plan de données n’ouvre jamais `console.sqlite` et ne lit jamais `deployment.yaml`. La politique et les paramètres de connexion n’arrivent que sous forme d’instantané signé. Envoy démarre lorsque le plan de données est prêt, et non lorsque la console l’est.

## Instantanés de politique

- Chaque politique appliquée, et chaque démarrage, publie un instantané immuable dans `/state/policy/` (`history/` et un `current.json` remplacé de façon atomique). Un contenu inchangé n’est pas republié.
- Le plan de données recherche un nouvel instantané toutes les 0,25 seconde et vérifie la signature, le format, le schéma et l’ordre des révisions. Les nouvelles requêtes utilisent la nouvelle politique ; les requêtes en cours conservent celle avec laquelle elles ont commencé.
- **L’application répond une fois la politique en vigueur.** Lors de l’application d’une politique, la console attend jusqu’à 5 secondes que le plan de données, et chaque inspecteur du groupe, signale la nouvelle révision. Sans confirmation, la politique est enregistrée et `policy.dataplane_pending` est audité.
- Un instantané rejeté ne remplace jamais la politique en cours. Le rejet apparaît dans l’état du plan de données, sous Connexions, et est audité sous `dataplane.snapshot_rejected`.

| Motif de rejet | Signification |
|---|---|
| `policy_snapshot_signature_invalid` | Le contenu a changé après la signature, ou une autre clé l’a signé |
| `policy_snapshot_malformed` / `policy_snapshot_invalid` | Fichier tronqué, illisible ou non conforme au schéma |
| `policy_snapshot_revision_regressed` | Plus ancien que la révision en cours |
| `connection_changed_restart_required` | Les routes, la destination ou l’authentification ont changé ; redémarrez le plan de données |
| `policy_snapshot_missing` / `policy_trust_key_unavailable` | Rien de vérifiable n’est disponible ; au démarrage, le plan de données reste fermé |

## Preuves

Les enregistrements de décision sont ajoutés à un spool par processus dans `/state/dataplane/events/`, avec un `fsync` pour chaque enregistrement. La console les importe dans sa base de données. Elle valide les événements et la position de lecture dans une seule transaction : un redémarrage de la console ne perd ni ne duplique aucun enregistrement. Les enregistrements produits pendant l’arrêt de la console apparaissent à son retour. Les API des événements et de la vue d’ensemble importent les enregistrements en attente avant de répondre.

Si un enregistrement ne peut pas être écrit en mode **inline**, la requête concernée échoue en mode fermé. Les nouvelles requêtes sont refusées avec HTTP 503 `dataplane_unavailable` jusqu’à ce que le stockage soit de nouveau inscriptible. Le mode mirror continue et signale l’échec du stockage. Le motif exact n’apparaît que dans l’état destiné aux opérateurs, jamais dans les réponses aux clients.

## Comportement en cas de panne (vérifié)

| Panne | Comportement | Preuve |
|---|---|---|
| Processus de la console tué | Les décisions d’autorisation et de blocage continuent ; les preuves sont importées après le redémarrage | `tests/runtime/test_plane_faults_runtime.py` F1 |
| `console.sqlite` verrouillée en exclusif | Aucun délai d’inspection supplémentaire | F2 (Docker) et `tests/test_plane_isolation.py` |
| `console.sqlite` endommagée ou supprimée | Plan de données non affecté | `tests/test_plane_isolation.py` |
| Instantané altéré, tronqué, signé par une autre clé ou plus ancien | Dernière politique valide conservée ; rejet audité | F4 (Docker) et tests unitaires |
| Aucun instantané au démarrage du plan de données | Aucune requête n’est servie | F5 |
| Worker d’inspection tué | La requête concernée échoue ; le worker est remplacé | Test du groupe dans `test_selfhost_runtime.py` |
| Envoy arrêté | HTTP 503, aucun repli direct | F10 |
| Échec d’écriture des preuves (inline) | La requête échoue en mode fermé ; l’admission est fermée jusqu’au rétablissement du stockage | Tests unitaires |

Exécutez la suite d’injection de pannes Docker avec `TD_FAULT_E2E=1 python -m pytest tests/runtime/test_plane_faults_runtime.py -q`.

## Exploitation

```bash
docker compose ps
docker compose logs --tail=100 app dataplane envoy
# Disponibilité et état du plan de données (port interne, non publié) :
docker compose exec -T dataplane python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:18085/_trapdefense/status').read().decode())"
```

L’activation de paramètres de connexion préparés exige d’arrêter les trois services. `activate-config` refuse de s’exécuter tant que la console, le plan de données ou Envoy fonctionne.

```bash
docker compose stop app dataplane envoy
docker compose run --rm app activate-config
docker compose up -d app dataplane envoy
```

Montez les identifiants fixes de destination (`static_bearer` et `static_api_key`) dans **les deux** services : `dataplane` (qui les utilise) et `app` (que l’activation valide). Redémarrez `dataplane` après une rotation.

Sauvegarde : `state` et `generated` sont indispensables. Si `control-keys` ou `policy-trust` est perdu, la console crée une nouvelle paire de clés au démarrage suivant et republie l’instantané.

## Mise à niveau depuis 0.46

1. Sauvegardez comme décrit dans [auto-hébergement](self-hosting.md) et arrêtez la pile.
2. Mettez à jour les sources, puis exécutez `docker compose build app`.
3. Déplacez les overrides Compose privés : les changements du port publié de la passerelle et les montages de secrets de destination vont sur `dataplane` (les montages de secrets aussi sur `app`).
4. Exécutez `docker compose up -d`. La console publie le premier instantané signé à partir de la politique enregistrée ; le plan de données l’attend puis devient prêt.

La commande par défaut de l’image, `serve`, exécute les deux plans comme des processus supervisés distincts dans un seul conteneur. Si la console s’arrête, seule la console redémarre ; si le plan de données s’arrête, le conteneur s’arrête. Utilisez les services Compose séparés pour l’isolation décrite ci-dessus.

## Performances

p95 du premier contenu de la passerelle, en millisecondes, avec le même benchmark synthétique et le même hôte que pour la [latence](latency.md) (2026-10-01, Docker ARM64, 14 CPU). Les écarts restent dans la variation d’une seule exécution. Les limites de rafale, de PII, de taille, de délai et d’identifiants sont inchangées. Le processus séparé de la console ajoute environ 110 Mio de mémoire (pic échantillonné : plan de données 149,5 Mio et 85,6 % de CPU, console 109,4 Mio). [JSON](../evidence/latency-047-synthetic.json)

| Scénario · concurrence | 0.46 | 0.47 |
|---|---:|---:|
| short · 1 / 8 / 32 | 232 / 420 / 1253 | 224 / 430 / 1232 |
| long · 1 / 8 / 32 | 822 / 1164 / 3014 | 810 / 1183 / 3112 |

## Limites

- Un seul hôte. Les approbations, l’enregistrement d’agents et l’émission d’identifiants nécessitent la console ; les approbations et identifiants déjà émis continuent de fonctionner pendant son arrêt.
- La clé de signature ne protège le canal des instantanés que si l’accès en écriture à `policy-trust` et `control-keys` reste restreint. Quiconque peut écrire dans les deux volumes peut signer une politique.
- L’ordre des révisions est appliqué tant que le processus du plan de données s’exécute. Après un redémarrage, le plan de données accepte l’instantané signé actuel.
- L’état du broker et les identifiants locaux des agents restent des fichiers partagés sur le volume `state`.
