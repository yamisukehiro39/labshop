-- Synthetic lab data only. No real customers or payment data.
INSERT INTO products(id,name,description,price_cents,stock,visible,icon) VALUES
(1,'Cloud Starter Kit','Le kit essentiel pour construire votre premier cloud.',49000,50,true,'cloud'),
(2,'Network Lab Switch','Un laboratoire réseau sur votre bureau.',89000,25,true,'network'),
(3,'Security Key','Une clé pour vos expériences de sécurité.',29000,100,true,'key'),
(4,'Observability Pack','Logs, métriques et traces, réunis.',39000,60,true,'chart'),
(5,'DevOps Notebook','Du commit au déploiement, toutes vos notes.',14900,80,true,'book'),
(6,'Platform Hoodie','Le confort des longues sessions de debug.',34900,40,true,'shirt'),
(7,'INTERNAL-DEMO-PRODUCT','Produit caché : preuve de SQL injection.',100,5,false,'lock')
ON CONFLICT(id) DO NOTHING;
SELECT setval(pg_get_serial_sequence('products','id'), (SELECT max(id) FROM products));
