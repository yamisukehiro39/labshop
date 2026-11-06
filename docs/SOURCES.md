# Références officielles consultées

- AWS SSM — plugins des documents, dont `aws:runShellScript` : https://docs.aws.amazon.com/systems-manager/latest/userguide/documents-command-ssm-plugin-reference.html
- Terraform AWS provider — `aws_ssm_association`, cibles et attente du succès : https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_association
- RDS PostgreSQL — SSL/TLS et `verify-full` : https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html
- AWS WAF — Common Rule Set et XSS : https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html
- AWS WAF — SQLi Rule Set : https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-use-case.html
- Network Firewall — limites de l'inspection TLS : https://docs.aws.amazon.com/network-firewall/latest/developerguide/tls-inspection-considerations.html
- Psycopg — installation : https://www.psycopg.org/psycopg3/docs/basic/install.html

Ces références étayent les choix techniques. Elles ne remplacent pas les tests dans ton compte AWS ni la mesure des règles réellement activées.
