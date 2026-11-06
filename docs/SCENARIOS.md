# Démontrer les protections sans confondre les couches

Effectuer ces essais uniquement sur ce laboratoire, avec des données fictives, depuis l'IP autorisée dans `allowed_client_cidr`. Aucun scan externe, flood ou cible tierce. Garder la même requête et le même mode applicatif entre les essais « WAF Count » et « WAF Block ».

## Tableau de comparaison

| Scénario | Vulnérable sans blocage WAF | Protection applicative | Composant AWS / observation |
|---|---|---|---|
| SQLi dans la recherche | Le produit caché 7 apparaît | Paramètres SQL ; le payload ne correspond à aucun produit | WAF SQLi : détection/blocage à vérifier dans ses logs |
| XSS dans un avis | Le navigateur interprète le HTML enregistré | `textContent` + CSP stricte | WAF Common Rule Set : peut bloquer l'injection HTTP initiale |
| IDOR sur commande de Bob | Alice peut lire la commande de Bob | Vérification du propriétaire → 403 | WAF/SG ne connaissent pas la propriété métier |
| Web → RDS 5432 | Connexion réseau refusée même en mode vulnérable | Aucun changement de code nécessaire | SG Database autorise seulement SG Application |
| API → Internet | Dépend de la politique d'inspection | Aucun endpoint de fetch arbitraire fourni | Network Firewall et routes ; journaux FLOW/ALERT |
| Secret RDS depuis Web | AccessDenied attendu | Profil IAM séparé | IAM / Secrets Manager / CloudTrail |
| Panne API A | API B peut répondre si déployée | Sessions partagées dans PostgreSQL | Nginx upstream, ALB, health checks |

Un 403 seul ne prouve pas un blocage WAF : identifier la règle terminante dans les logs WAF et vérifier que la requête n'est pas arrivée à l'application. Les signatures managées peuvent évoluer et produire des faux positifs. Ne pas affirmer qu'elles bloquent toutes les variantes.

## 1. SQL injection — lecture contrôlée

1. Déployer `labshop_mode="vulnerable"`. WAF désactivé ou règles en Count.
2. Chercher `Cloud` dans le catalogue : seuls les produits visibles correspondants apparaissent.
3. Dans la recherche de **LabShop**, saisir :

```text
' OR 1=1 -- 
```

Résultat attendu : apparition de `INTERNAL-DEMO-PRODUCT`. La recherche vulnérable concatène la saisie ; la transaction est read-only et limitée à 2 secondes. Cela limite les dégâts du scénario, mais ne transforme pas la requête en requête sûre.

4. Activer le groupe WAF SQLi en Block, rejouer et consulter le résultat réel et les logs.
5. Désactiver le blocage WAF / revenir à Count, passer l'application en `secure` puis rejouer : liste vide, HTTP 200, aucun produit caché.

## 2. XSS stockée — effet visible sans exfiltration

1. Se connecter comme Alice, en mode vulnérable.
2. Ouvrir les avis d'un produit et poster :

```html
<img src=x onerror="alert('LabShop XSS demo')">
```

3. Réouvrir les avis : une alerte de démonstration doit apparaître.
4. Passer WAF Common Rule Set en Block et tenter un nouvel avis avec le même contenu. Vérifier la règle exacte dans les logs ; les inspections du corps JSON ne garantissent pas toutes les détections.
5. Passer en `secure` : même les avis déjà stockés deviennent du texte inerte ; la CSP bloque aussi les gestionnaires inline.

WAF ne nettoie pas les payloads déjà enregistrés dans RDS. Il inspecte les nouvelles requêtes qui le traversent.

## 3. IDOR — montrer la limite de l'infrastructure

1. Connexion comme Bob ; ouvrir sa commande et noter son ID (ne pas supposer qu'il vaut toujours 2).
2. Déconnexion puis connexion comme Alice.
3. Dans la console développeur de ton navigateur sur LabShop :

```javascript
fetch('/api/orders/ID_DE_BOB').then(r => r.json()).then(console.log)
```

Remplacer `ID_DE_BOB`. Mode vulnérable : données de Bob visibles. Mode secure : 403. Même avec WAF en Block, un ID numérique ordinaire ne représente pas une signature d'attaque suffisante : l'autorisation doit être dans le code.

## 4. Segmentation et inspection sortante

Depuis Session Manager sur **Web**, tester seulement le RDS du lab :

```bash
python3 - <<'CHECK'
import socket
try:
    socket.create_connection(('TON_ENDPOINT_RDS',5432),timeout=5)
    print('Joignable : vérifier les règles SG, résultat inattendu depuis Web')
except (TimeoutError,OSError):
    print('Connexion impossible ; confirmer la cause avec SG/Flow Logs')
CHECK
```

Depuis Application, le même test doit réussir si RDS est prêt. Un timeout peut aussi venir des routes ou de RDS : corroborer avec la configuration réseau et les VPC Flow Logs.

Pour l'inspection sortante, choisir une URL HTTPS de test autorisée puis la bloquer explicitement dans **ta** politique Network Firewall ; effectuer un `curl -I --max-time 10 https://DOMAINE_DE_TEST` depuis Application, avant/après. Choisir un domaine sans rapport avec SSM/GitHub/PyPI pour ne pas casser l'administration. Conserver timestamp UTC, source et journal firewall. Le routage doit réellement traverser l'endpoint firewall. Le HTTPS chiffré n'est pas inspectable en contenu sans une configuration de déchiffrement appropriée ; ne pas attribuer à Network Firewall le filtrage SQLi de l'ALB.

## 5. Disponibilité (si B est déployée)

Arrêter `labshop` avec `sudo systemctl stop labshop` sur Application A, vérifier l'accès via ALB et l'utilisation d'Application B, puis redémarrer A. Répéter sur Web A pour tester le target group ALB. Attendre les seuils de health check/failover ; quelques requêtes peuvent échouer pendant la transition. Les nouvelles requêtes POST ne sont pas rejouées aveuglément sur une autre API. Cela ne prouve pas une tolérance à une panne RDS Single-AZ.

## Fiche de preuve à remplir

| UTC | Mode app | WAF Count/Block | Requête / test | HTTP / résultat | Log / règle / capture | Conclusion |
|---|---|---|---|---|---|---|
| | | | | | | |

Les logs applicatifs fournissent `request_id`, chemin sans query string, statut, durée et mode. Les requêtes bloquées avant l'API n'ont pas d'ID applicatif : utiliser les informations WAF/ALB et l'horodatage pour les corréler.
