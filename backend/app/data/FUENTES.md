# Fuentes de la tabla de alimentos

La tabla de alimentos de Kcalia (`alimentos.json` + `recetas.json`) toma sus valores nutricionales de estas fuentes.
Las cifras están copiadas sin alterar en los extractos `ciqual_2025.tsv` y `usda_fdc.tsv`; el código solo lee la
coma decimal y trata «-», «traces» y «< x» (cantidades no medibles) como 0.

## CIQUAL 2025 (ANSES)

> Anses. 2025. Table de composition nutritionnelle des aliments Ciqual. https://doi.org/10.57745/RDMHWY

Datos abiertos con la [Licence Ouverte](https://www.etalab.gouv.fr/licence-ouverte-open-licence/): se pueden
reutilizar citando la fuente y la versión y sin alterar su sentido. Columnas usadas: energía según el Reglamento
(UE) 1169/2011 en kcal, proteínas (N × 6,25), hidratos de carbono disponibles («glucides»), grasas («lipides»),
fibra alimentaria y alcohol, todo por 100 g.

## USDA FoodData Central

> U.S. Department of Agriculture, Agricultural Research Service. FoodData Central (SR Legacy 2018 y FNDDS 2024).
> https://fdc.nal.usda.gov/

Dominio público (CC0). Solo para lo que CIQUAL no tiene (proteína whey, requesón, queso cottage, edamame, huevo frito
en aceite y churros). USDA publica los hidratos «por diferencia», con la fibra incluida; la tabla resta la fibra para
quedarse con los disponibles, como CIQUAL y las etiquetas europeas.

## Recetas estándar de Kcalia

Platos españoles que no están en ninguna de las dos (tortilla de patatas, croquetas, lentejas con chorizo, cocido,
fabada, salmorejo…). Cada receta de `recetas.json` indica sus ingredientes (alimentos de la tabla), sus gramos y el
rendimiento (peso final ÷ peso de los ingredientes, por el agua que se pierde o se añade al cocinar). Los valores por
100 g son la suma de los ingredientes dividida por el peso final. Son estimaciones de una receta tipo, no medidas.

## Pesos de las unidades y densidades

Los pesos de una pieza, loncha, rebanada, plato o cucharada son la parte comestible de raciones habituales en España
(convenciones de medidas caseras: cucharada sopera de aceite 10 g, de azúcar o miel 15 g; cucharadita 5 g; huevo M
50 g sin cáscara). Las densidades (g/ml) pasan los mililitros a gramos (aceite 0,915; leche 1,03; miel 1,42).

## Regenerar los extractos

    uv run --with openpyxl python scripts/food_sources.py --ciqual "Table Ciqual 2025_FR_2025_11_03.xlsx" \
        --usda FoodData_Central_sr_legacy_food_csv_2018-04 FoodData_Central_survey_food_csv_2024-10-31
