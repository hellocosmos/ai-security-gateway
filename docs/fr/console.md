# Installation et utilisation de la console

> **0.44:** [Espace d’exploitation (0.44)](operator-workspace.md)


> **AISG:** [Connecter, identifier, contrôler, vérifier](aisg.md). La passerelle utilise une clé de déploiement ou un JWT vérifié. agent_key identifie un agent enregistré sans IAM externe. JWT identity_mode: agent utilise les attributs vérifiés du tenant et de l’agent ; delegated exige aussi utilisateur, tâche et délégation. Les agents existants nécessitent une délégation par défaut.

> Docker 0.42 : [Auto-hébergement](self-hosting.md) · [Compatibilité de la passerelle](gateway-compatibility.md). Cette page décrit la démonstration synthétique distincte depuis les sources.

[English](../en/console.md) · [한국어](../ko/console.md) · [简体中文](../zh-CN/console.md) · [日本語](../ja/console.md) · [Español](../es/console.md) · [Français](../fr/console.md)

La console prend en charge le SSO Microsoft Entra ID à locataire unique avec les rôles Administrateur et Lecteur. L’identité de l’opérateur et l’autorisation de l’agent sont des frontières distinctes ; l’Access Broker intégré applique l’autorisation. [Entra SSO](identity.md).

## Installer et démarrer

Prérequis : Python 3.11+, Node.js 22.12+ ou 24, npm et Docker Engine/Desktop local en cours d’exécution. Ce dépôt suffit : aucun SDK, package runtime privé ni API de modèle n’est requis. Les scripts utilisent `uv` s’il est présent, sinon Python venv/pip. Exécutez sans sudo et gardez Docker local.

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway
./scripts/install-console.sh
./scripts/run-console.sh
```

Ouvrez [http://127.0.0.1:5176](http://127.0.0.1:5176). Le compte initial est **admin / 1234** . Modifiez le mot de passe dans **Paramètres → Mot de passe administrateur** ; toutes les sessions sont révoquées. La console écoute uniquement sur la boucle locale : c’est une installation d’évaluation, pas une appliance exposée à Internet. Un conflit de port bloque le démarrage sans arrêter d’autres services. Ctrl+C arrête le service et retire uniquement son conteneur Envoy étiqueté.

## Langue

Le sélecteur est disponible à la connexion et dans la barre supérieure. L’anglais est la langue par défaut ; coréen, chinois simplifié, japonais, espagnol et français sont inclus. Le choix est mémorisé dans le navigateur sans déconnexion. Les documents s’ouvrent dans la langue choisie. Les noms d’outils, codes de règles, identifiants et saisies restent inchangés. La traduction de l’interface n’étend pas les langues couvertes par la détection PII.

## Chemin réel du trafic

```text
Browser -> management API/UI :5176
                 -> signed synthetic sender -> Envoy :18082 -> HTTP destination :18090
                                                 <-> gRPC inspector :18101–18104
                 <- response inspection <- decision + receipt <- UI
```

L’émetteur simule un relais de confiance et signe les requêtes synthétiques exactes ; ce n’est ni un déchiffreur TLS ni un IdP. Envoy et la destination HTTP sont réels. La démo utilise le véritable Access Broker intégré avec des identités synthétiques et une approbation liée à la requête, sans action métier externe.

## Pages et premier parcours

1. **Tableau de bord :** lancez lecture, masquage client, blocage d’identifiant divulgué, suppression, injection, transfert externe et PII de réponse. Les données proviennent de vraies requêtes, pas de décisions préremplies.
2. **Trafic / Événements :** filtrez et consultez statut HTTP, réception à destination, masquage et version de politique. Le CSV contient des métadonnées expurgées.
3. **Politiques :** bloquez `notes.read`, validez, appliquez puis rejouez. Rétablissez l’autorisation ensuite. Les nouveaux flux prennent la mise à jour ; les flux en cours gardent leur politique.
4. **Connexions / Système :** vérifiez composants et chemin. ** Audit :** examinez les changements de connexion, politique et réseau.
5. **Paramètres :** consultez les interfaces et modifiez port, délai ou limite du corps. Le validateur Envoy contrôle la configuration. L’application redémarre brièvement le conteneur propre, vérifie la nouvelle écoute et restaure l’ancienne en cas d’échec.

## Politique PII par route et outil

L’action PII globale est la valeur par défaut. Une route HTTP/MCP peut la remplacer, puis une action mappée ou un outil MCP peut remplacer la route. La priorité exacte est **outil/action → route → global** ; une valeur omise est héritée. L’action et la portée choisies sont enregistrées dans la preuve nettoyée et réutilisées pour inspecter la réponse correspondante.

Dans **Politiques → Dérogation PII**, réglez chaque outil de démonstration sur hériter, masquer ou bloquer. En mode Mirror, la requête et la réponse d’origine restent inchangées ; l’interface affiche **Autoriserait**, **Masquerait** ou **Bloquerait**. `unknown` reste réservé aux captures incomplètes ou aux échecs d’inspection. Un résultat Mirror est une preuve d’évaluation, pas une preuve d’application en production.

## Réseau et cartes NIC

| Paramètre | Valeur par défaut / sens |
|---|---|
| Déploiement | L7 explicite, une interface de boucle locale |
| API/UI de gestion | `127.0.0.1:5176` |
| Entrée du proxy | `127.0.0.1:18082`, port non privilégié configurable |
| Inspecteur | `127.0.0.1:18101–18104`, gRPC ExtProc |
| Destination | `127.0.0.1:18090`, HTTP synthétique uniquement |
| Délai de requête | 5 secondes, réglable de 2 à 30 |
| Limite du corps | 1 MiB, réglable de 1 KiB à 1 MiB |
| Interfaces | Noms, adresses, état du lien, MTU et rôle réels du système |

Le nombre d’interfaces n’est pas celui des cartes physiques : il inclut boucle locale, ponts et tunnels. Ce profil ne configure ni routage physique à une/deux cartes, ni pont transparent, ni IP/routes du système, ni interface de sortie imposée. Le formulaire n’accepte pas de destinations de production arbitraires. macOS utilise le transfert Docker Desktop vers l’hôte ; Linux utilise host networking pour la boucle locale. Envoy 1.39.1 est fixé par un digest multi-architecture amd64/arm64.

## Inspection et pannes

**Inline** autorise, bloque ou masque. Les requêtes non déclarées ou non signées sont refusées ; une panne de communication avec l’inspecteur bloque le trafic. ** Mirror dans cette console** observe le même chemin synchrone sans modifier le contenu ni consommer d’approbation ; les pannes de communication bloquent toujours. Le collecteur mirror indépendant reçoit des copies et ne peut agir sur l’original. Aucun mode n’offre de streaming illimité. Le proxy défaillant n’est jamais remplacé par un appel direct au moteur.

## Persistance et dépannage

`.runtime-state/console` conserve les empreintes des comptes/sessions, politiques, paramètres réseau et événements SQLite expurgés. Utilisez `TD_CONSOLE_STATE` pour un autre répertoire privé. Sauvegardez à l’arrêt ; changer de chemin crée une installation distincte. Ce répertoire est exclu de Git. La clé de signature est éphémère dans la démo ; aucun relais externe n’est configuré. Les compteurs de destination repartent de zéro au redémarrage, les preuves enregistrées restent. L’audit local est modifiable, non immuable.

En cas d’échec, vérifiez Docker, les ports 5176/18101–18104/18111–18114/18090 et le port du proxy. N’arrêtez pas automatiquement des services tiers. L’absence de preuves est une erreur, pas un succès. La latence inclut les effets locaux et du conteneur ; ce n’est pas un benchmark de production. TLS réel, IAM, routage imposé, HA et durcissement nécessitent une validation distincte.

## Vérification et traductions

```bash
.venv/bin/python -m pytest -q
npm run check --prefix console
npm run build --prefix console
# Stop the running console before this Docker test.
TD_CONSOLE_E2E=1 .venv/bin/python -m pytest tests/test_console.py -q
```

Sans `TD_CONSOLE_E2E=1`, les tests Docker sont ignorés. Les contrôles vérifient les mêmes clés et paramètres dans les six dictionnaires et un code en anglais. Modifiez ensemble les clés anglaises et tous les JSON, sans changer les codes API stables. En cas de divergence, le document anglais fait référence. Consultez [architecture](architecture.md), [éditions](editions.md), [migration](migration.md) et [sécurité](security.md).


## Exploitation sur un même hôte

[1 / 2 / 4 inspectors · Linux service](operations.md)
