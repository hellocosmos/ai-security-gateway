# Décision sur le streaming interactif — 0.45

La voie actuelle inspecte toute la réponse SSE avant livraison. La livraison partielle reste désactivée. Une future voie doit prouver la détection PII et secrets entre fragments, la décision avant chaque octet, le traitement SSE malformé ou rejoué, les limites mémoire et contre-pression, le blocage sûr en cas d’annulation ou délai, et l’approbation avant action aval. Un contenu déjà livré ne peut être repris. Sinon, gardez le tampon complet et mesurez l’expérience.
