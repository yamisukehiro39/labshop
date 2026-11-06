# API et schéma PostgreSQL

Spécification importable : [openapi.json](openapi.json).

Base publique : `/api`. Nginx retire ce préfixe avant l'API Flask. JSON UTF-8. Les écritures demandent `Content-Type: application/json` et `X-LabShop-Client: web`. Aucun CORS permissif. Sessions opaques stockées sous forme SHA-256 en DB, durée 8 h, cookie HttpOnly SameSite=Lax.

| Méthode | Chemin public | Auth | Fonction |
|---|---|---|---|
| GET | `/api/health` | Non | Readiness DB ; 200 ou 503 |
| GET | `/api/config` | Non | Mode et version du lab |
| GET | `/api/products?q=cloud` | Non | Catalogue/recherche |
| POST | `/api/auth/login` | Non | `{ "email": "alice@labshop.test", "password": "LabShop-Demo-2026!" }` |
| POST | `/api/auth/logout` | Non | Révoque la session courante ; corps `{}` |
| GET | `/api/me` | Oui | Identité du client |
| GET | `/api/orders` | Oui | Commandes du client |
| GET | `/api/orders/{id}` | Oui | Détail ; contrôle du propriétaire en mode secure |
| POST | `/api/orders` | Oui | `{ "items": [{ "product_id": 1, "quantity": 1 }] }` |
| GET | `/api/products/{id}/reviews` | Non | 50 derniers avis |
| POST | `/api/products/{id}/reviews` | Oui | `{ "body": "Très bon produit de démonstration" }` |

Créations : HTTP 201. Erreurs JSON `{error,request_id}`. Erreurs usuelles : 400 entrée invalide, 401 session absente, 403 accès refusé, 404 inconnu, 409 stock insuffisant, 413 corps trop grand, 415 format incorrect. Les prix sont des entiers en centimes MAD ; le serveur recalcule les totaux et verrouille les stocks en transaction. Les quantités sont de 1 à 10, 20 lignes maximum, sans doublon de produit.

## Tables

| Table | Données et relations |
|---|---|
| `users` | email unique, nom, hash de mot de passe |
| `products` | nom, prix, stock, visibilité ; produit 7 caché pour SQLi |
| `orders` | propriétaire → users, montant, statut, date |
| `order_items` | commande → orders, produit → products, prix figé, quantité |
| `reviews` | auteur → users, produit → products, contenu |
| `sessions` | hash du token, utilisateur, expiration |
| `schema_migrations` | versions appliquées |

Le seed SQL insère uniquement les produits manquants. Le script de migration crée les utilisateurs avec des mots de passe hashés et une commande de démonstration pour chacun. Les commandes et stocks existants sont conservés au redéploiement. Un verrou transactionnel protège les migrations ; un second verrou de session protège le bootstrap AWS complet. Aucune table ne contient de données de paiement.

Les futures migrations doivent recevoir un numéro/version supplémentaire dans `scripts/migrate.py`. Ne pas modifier une migration déjà appliquée en espérant qu'elle soit rejouée. Les changements de colonnes doivent être explicités dans un nouveau fichier SQL.

## Exemple curl

```bash
BASE=http://localhost:8080
curl -c /tmp/labshop.cookies -H 'Content-Type: application/json' \
  -H 'X-LabShop-Client: web' \
  -d '{"email":"alice@labshop.test","password":"LabShop-Demo-2026!"}' \
  "$BASE/api/auth/login"
curl -b /tmp/labshop.cookies "$BASE/api/orders"
curl -b /tmp/labshop.cookies -H 'Content-Type: application/json' \
  -H 'X-LabShop-Client: web' \
  -d '{"items":[{"product_id":1,"quantity":1}]}' "$BASE/api/orders"
```
