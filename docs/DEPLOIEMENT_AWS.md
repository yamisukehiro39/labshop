# Déploiement AWS avec le Terraform existant

## 1. Préparer le dépôt applicatif

Publier la racine de ce dossier sur GitHub, comme indiqué dans le README. Copier le SHA complet renvoyé par `git rev-parse HEAD`. Chaque version est déterministe ; ne pas utiliser `main` comme SHA.

## 2. Installer le module dans TON projet Terraform

Ne pas exécuter `terraform apply` depuis le dépôt LabShop : `infra/module` est un module enfant, il ne crée ni VPC, ni ALB, ni EC2, ni RDS.

Copier :

| Source LabShop | Destination dans ton Terraform |
|---|---|
| `infra/module/` (tout le dossier) | `modules/labshop_deploy/` |
| `infra/integration/labshop_deploy.tf.example` | `labshop_deploy.tf` à la racine |
| Valeurs de `infra/integration/terraform.tfvars.example` | Ajouter à ton `terraform.tfvars` local |

Conserver les modules et fichiers réseau existants. Ton archive fournie référence `./modules/...`, mais ne contient pas ces modules : il faut utiliser ton dossier Terraform de travail complet.

## 3. Retirer les anciens déploiements

- Supprimer l'ancien bloc `aws_ssm_association.labshop` de `application_deploy.tf`.
- Supprimer **uniquement** le bloc `aws_ssm_association.web_nginx` de `web_ec2.tf` ; conserver l'EC2 et les outputs.
- Les anciens fichiers `labshop/app.py` et `labshop/install.sh` du Terraform deviennent inutilisés.
- Dans `aws_instance.application`, remplacer `iam_instance_profile` par :

```hcl
iam_instance_profile = aws_iam_instance_profile.labshop_application.name
```

Faire la même modification pour l'instance Application B si elle existe. Le rôle de l'EC2 Web reste `test_ec2`, sans accès aux secrets RDS. Le nouveau fichier d'intégration crée le rôle Application et son profil. L'ancien service peut porter un autre nom : vérifier `systemctl list-units --type=service` et désactiver tout ancien processus écoutant sur 8000 avant migration si nécessaire.

## 4. Variables et prérequis

```hcl
labshop_repository = "https://github.com/TON_COMPTE/labshop.git"
labshop_commit     = "LE_SHA_COMPLET_DE_40_CARACTERES"
labshop_mode       = "vulnerable"
```

Le fichier d'intégration utilise `cookie_secure=false` pour rester compatible avec ton ALB HTTP actuel. Après ajout du listener HTTPS et du certificat ACM, passer à `true` et rediriger HTTP vers HTTPS. Les identifiants de démonstration transitent en clair sur HTTP : n'utiliser que ces données fictives dans le labo restreint.

Prérequis AWS :

- Amazon Linux 2023 x86_64, agent SSM démarré, rôle `AmazonSSMManagedInstanceCore`.
- Les SG existants : poste `/32` → ALB 80 ; ALB → Web 80 ; Web → App 8000 ; App → RDS 5432.
- Sortie HTTPS fonctionnelle via TGW → Network Firewall → NAT → IGW, ainsi que résolution DNS.
- Accès aux endpoints SSM/ssmmessages, Secrets Manager, GitHub, PyPI (`pypi.org`, `files.pythonhosted.org`), dépôts Amazon Linux et `truststore.pki.rds.amazonaws.com`. Une allowlist restrictive doit autoriser leurs dépendances de téléchargement effectivement observées.
- RDS PostgreSQL privé avec `manage_master_user_password=true`, DB `awslab`.
- Si les secrets utilisent une clé KMS client, ajouter `kms:Decrypt` au rôle Application sur cette clé et autoriser ce rôle dans la key policy. Le module suppose les clés AWS gérées par défaut.

## 5. Appliquer et vérifier

```bash
terraform fmt -recursive
terraform init
terraform validate
terraform plan
terraform apply
```

Le module attend le succès des associations Application, puis déploie Web. Le premier bootstrap peut durer plusieurs minutes. Un agent SSM non enregistré ou une propagation IAM retardée peut faire échouer la première tentative : corriger le prérequis puis réexécuter l'association ou modifier `redeploy_token` dans le module et appliquer.

Ouvrir le DNS ALB affiché par `labshop_alb_dns_name`, puis :

```bash
python scripts/smoke.py http://TON_DNS_ALB
```

Depuis le dossier LabShop pour ce script. Le health check `/api/health` vérifie aussi la présence de la table `products` dans PostgreSQL.

## 6. Deux zones de disponibilité

Décommenter les entrées `b` dans `application_instances` et `web_instance_ids` **seulement après création des EC2 B**, en adaptant leurs vrais noms Terraform. Le module accepte une map de 1 à N instances ; Nginx utilise toutes les adresses privées des APIs.

Les deux Web doivent aussi être enregistrés dans le target group ALB, avec leurs routes et SG. Les sessions sont en PostgreSQL, donc pas besoin de sticky sessions. Les verrous PostgreSQL sérialisent le provisioning simultané. Cela ne rend pas la base hautement disponible : ton RDS actuel a `multi_az=false`. Activer Multi-AZ est une décision d'infrastructure et de coût distincte.

## 7. Mise à jour, redéploiement, rollback

```bash
# Dans LabShop, après modification
git add .
git commit -m "Update LabShop"
git push
git rev-parse HEAD
```

Copier ce SHA dans `labshop_commit`, puis appliquer dans Terraform. Chaque modification du commit, de la configuration, des cibles ou du token de redéploiement modifie l'association. Il n'y a pas de polling GitHub périodique.

Pour rejouer exactement la même version : ajouter/incrémenter `redeploy_token = "2"` dans l'appel du module puis appliquer. Cela permet aussi de rafraîchir le fichier local après rotation du secret applicatif. Pour rollback du code, remettre l'ancien SHA et appliquer. Les migrations restent en avant : ne jamais revenir vers une version incompatible avec un schéma déjà migré.

## 8. Secrets et privilèges

Le mot de passe master n'apparaît ni dans Terraform ni dans les commandes SSM. Le bootstrap lit le secret RDS, crée `labshop_app`, génère son mot de passe et le stocke dans un secret distinct. Le service utilise `/etc/labshop/db.json`, root:labshop 0640, avec `sslmode=verify-full` et certificat CA RDS. L'API ne reçoit pas le mot de passe master.

Le rôle EC2 Application conserve l'accès de provisioning au secret master pour les redéploiements. Le service systemd interdit l'accès aux adresses IMDS ; ce n'est pas une séparation de confiance équivalente à une machine de migration dédiée. Pour un déploiement de production, séparer le runner de migration et les permissions runtime.

Aucun secret runtime n'est prérempli dans Terraform. Le secret vide créé par Terraform est rempli par le bootstrap. Son délai de suppression est de 7 jours ; les noms utilisent un suffixe aléatoire pour permettre une recréation sans collision.

## 9. Publication et destruction

Le ZIP Terraform source contient `terraform.tfstate` et `.backup` : **ne pas les publier**. Le dépôt LabShop exclut états, tfvars réels, `.env`, configuration runtime et clés. Ne pas copier l'archive Terraform entière dans ce dépôt.

`terraform destroy` dans ton projet existant supprime les ressources selon ses règles. Son RDS utilise `skip_final_snapshot=true` : les données sont perdues sans restauration externe. Les associations SSM ne déclenchent pas de suppression des tables à chaque arrêt. LabShop ne modifie pas cette politique existante.
