-- Синтетические требования к документам: необязательная бухгалтерская отчётность для OCR (можно ввести вручную).
INSERT INTO catalog.document_requirement (product_id, product_version, requirement_id, title, reason, required,
                                          allowed_content_types, max_bytes, max_pages_for_extraction)
SELECT p.product_id, p.version, 'financial-statement', 'Бухгалтерская отчётность за год',
       'Позволяет заполнить финансовую анкету по документу; значения можно ввести вручную', false,
       ARRAY['application/pdf', 'image/jpeg', 'image/png'], 10485760, 5
FROM catalog.product p
WHERE p.product_id IN ('working-capital', 'credit-line', 'overdraft') AND p.version = 1
ON CONFLICT DO NOTHING;
