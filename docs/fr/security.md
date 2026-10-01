# Périmètre de sécurité et signalement

[English](../en/security.md) · [한국어](../ko/security.md) · [简体中文](../zh-CN/security.md) · [日本語](../ja/security.md) · [Español](../es/security.md) · [Français](../fr/security.md)

**Canal de politique 0.47 :** le plan de contrôle signe les instantanés avec une clé Ed25519 du volume `control-keys` ; le plan de données les vérifie avec la clé publique du volume en lecture seule `policy-trust` et conserve sa dernière politique vérifiée en cas de rejet. Restreignez l’écriture sur les deux volumes. Voir [séparation des plans](plane-separation.md).

La console prend en charge le SSO Microsoft Entra ID à locataire unique avec les rôles Administrateur et Lecteur. L’identité de l’opérateur et l’autorisation de l’agent sont des frontières distinctes ; l’Access Broker intégré applique l’autorisation. [Entra SSO](identity.md).

Signalez les vulnérabilités en privé à **hellocosmos@gmail.com** , avec révision, reproduction synthétique et impact. Ne publiez pas de données client, jetons ou identifiants réels dans les issues. Aucun SLA de réponse fixe n’est promis.

## Couverture PII

L’inspection hors ligne évalue les six profils linguistiques pour chaque charge prise en charge :

- Anglais : e-mail, téléphone, carte bancaire, IBAN et SSN américain.
- Coréen : numéros d’enregistrement des résidents et étrangers, permis, passeport et entreprise.
- Chinois simplifié : téléphone et numéro d’identité résident GB 11643.
- Japonais : téléphone et numéro individuel à 12 chiffres (My Number).
- Espagnol : téléphone, NIF, NIE et passeport.
- Français : téléphone et numéro de sécurité sociale NIR, y compris les codes corses.

Les identifiants nationaux valident le format et la clé lorsque la norme en définit une. Il s’agit d’une inspection déterministe de motifs, pas d’un NER général : noms, lieux, adresses postales, images, OCR et fichiers arbitraires sont hors périmètre de cette version.

### Sélection de politique et preuve Mirror

Le traitement PII suit une priorité déterministe : **outil/action mappé → route → valeur globale**. L’action choisie pour la requête s’applique aussi à sa réponse prise en charge, y compris un flux SSE entièrement mis en mémoire tampon. La preuve enregistre uniquement l’action et la portée, jamais le contenu capturé. En mode Mirror, une détection complète conserve `would_redact` ou `would_block` et les octets d’origine restent inchangés ; un transport ou une inspection incomplets restent `unknown`.

## Couverture des fuites de secrets

L’inspection hors ligne bloque les clés privées reconnues, les formats courants de jetons AWS, GitHub, GCP, Slack, Stripe et OpenAI, les JWT signés dont la structure est valide, les combinaisons de paramètres SAS Azure Storage et les valeurs à forte entropie dans les champs JSON sensibles. Elle couvre les corps de requête pris en charge, les réponses et les flux SSE réassemblés.

Les en-têtes `Authorization`, cookie et API-key des requêtes ne sont conservés que pour le chemin de destination déjà vérifié par signature et explicitement mappé ; ils sont exclus de l’audit. Les en-têtes de réponse sont inspectés. Les textes ressemblant à un JWT mais invalides, les paramètres `sig` ordinaires et les valeurs fictives de documentation ne sont pas bloqués. Seul `secret_detected` est enregistré, jamais la valeur capturée. Cette couverture déterministe peut manquer de nouveaux formats ou des formats internes et produire des faux positifs ; renouvelez tout identifiant réel susceptible d’avoir franchi une frontière non fiable.

Le périmètre couvre les flux HTTP/MCP pris en charge et explicitement routés depuis un relais signé de confiance. Les exemples locaux sont synthétiques, pas des appliances de production durcies.

- Restreignez les listeners en clair, ExtProc et mirror aux réseaux et émetteurs fiables.
- Protégez et renouvelez les clés de signature ; ne les donnez jamais aux agents. Imposez le routage amont contre le contournement.
- Les défaillances inline de l’inspecteur ou de l’autorisation doivent bloquer. Le collecteur mirror séparé ne bloque pas l’original ; Mirror de la console est synchrone et bloque si la communication avec l’inspecteur échoue.
- Configurez les limites de corps/durée, les mappages et le masquage par champ. SSE avec tampon est borné, pas un streaming illimité.
- La protection anti-rejeu et l’audit SQLite local ne garantissent ni HA distribuée ni conservation immuable.
- Les signatures et la détection PII produisent des faux positifs et négatifs.
- Une source signée ne prouve pas l’identité humaine ou de l’agent. Le mode Broker exige une chaîne JWT vérifiée et un mapping explicite des claims.

Le compte initial est `admin`, mot de passe `1234` ; changez-le dans les paramètres. La gestion écoute sur loopback. Les réglages réseau gèrent le conteneur Envoy propre à la démo, pas les adresses des interfaces du système, les routes physiques ni les règles du pare-feu. Authentification, contrôles CSRF et hachage ne transforment pas cette démo en IAM de production. MIT couvre tout le runtime et l’Access Broker ; les actifs et credentials client restent hors du dépôt.
