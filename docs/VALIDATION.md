# Vérifications effectuées

## Résultats locaux

- **16 tests API réussis** (`16 passed in 2.34s`) : modes secure/vulnerable, recherche SQLi, autorisation des commandes, sessions, achats, prix serveur, avis, entrées invalides et rollback sur stock insuffisant.
- Les migrations ont été exécutées deux fois sur la même base lors des tests.
- Moteur de test local : **PGlite (PostgreSQL compilé en WebAssembly), avec connexion psycopg via le protocole PostgreSQL**. Ce résultat ne vaut pas validation RDS native ni preuve de concurrence multi-AZ. Le workflow GitHub fourni utilise PostgreSQL 16 natif pour la prochaine vérification.
- Syntaxe Python compilée, JavaScript contrôlé avec `node --check`, Bash contrôlé avec `bash -n`.
- Fichiers Terraform parsés et module formaté par Terraform 1.9.8.
- Spécification OpenAPI JSON parsée.

## Vérifications restant à réaliser sur la cible

- `terraform validate` complet : l'installation du provider a abouti, mais sa vérification locale a échoué sur une différence de checksum du cache. Aucun contournement du contrôle d'intégrité n'a été utilisé. Relancer `terraform init` et `terraform validate` dans ton environnement habituel ; ne pas réutiliser le cache de cette session.
- Exécution du bootstrap AL2023, permissions IAM/KMS, accès Secrets Manager, TLS RDS et succès SSM.
- Démarrage et reconfiguration effectifs de systemd/Nginx dans les EC2.
- Test UI dans un navigateur réel : Chromium n'a pas pu être lancé dans cet environnement. La syntaxe JavaScript a été contrôlée, mais aucun résultat visuel ou XSS navigateur n'est annoncé comme validé.
- Mesure des blocages WAF/Network Firewall et tests de bascule entre zones dans ton compte AWS.
- Test Docker Compose complet : Docker n'est pas disponible dans cet environnement.

Aucune ressource AWS n'a été créée et aucun dépôt GitHub n'a été publié. Les scénarios du guide décrivent les résultats attendus, pas des mesures inventées dans ton compte.
