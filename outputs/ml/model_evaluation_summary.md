# Model Evaluation Summary

## Clustering

| model_name   |   cluster_count |   silhouette |   profile_count |   min_cluster_size |   max_cluster_size |   smallest_cluster_share |   largest_cluster_share |   tiny_cluster_count |   small_cluster_count |
|:-------------|----------------:|-------------:|----------------:|-------------------:|-------------------:|-------------------------:|------------------------:|---------------------:|----------------------:|
| kmeans       |               3 |     0.3792   |               3 |                185 |               2341 |                   0.0424 |                  0.5363 |                    0 |                     1 |
| kmeans       |               4 |     0.343203 |               4 |                162 |               2035 |                   0.0371 |                  0.4662 |                    0 |                     1 |
| kmeans       |               5 |     0.302351 |               5 |                  4 |               1828 |                   0.0009 |                  0.4188 |                    1 |                     2 |
| kmeans       |               6 |     0.326924 |               6 |                  1 |               1924 |                   0.0002 |                  0.4408 |                    1 |                     2 |
| kmeans       |               7 |     0.304687 |               7 |                  1 |               1777 |                   0.0002 |                  0.4071 |                    2 |                     3 |

Warnings:
- kmeans with k=5 produced at least one tiny cluster below 1% of eligible cells.
- kmeans with k=5 produced multiple small clusters below 5% of eligible cells.
- kmeans with k=6 produced at least one tiny cluster below 1% of eligible cells.
- kmeans with k=6 produced multiple small clusters below 5% of eligible cells.
- kmeans with k=7 produced at least one tiny cluster below 1% of eligible cells.
- kmeans with k=7 produced multiple small clusters below 5% of eligible cells.

## Anomaly Detection

| district_name         | district_key      |   anomaly_score | anomaly_flag   | anomaly_top_features                                                                   |
|:----------------------|:------------------|----------------:|:---------------|:---------------------------------------------------------------------------------------|
| Chamberí              | chamberí          |        0.556541 | True           | ['grid_height_mean_avg', 'grid_dense_urban_share', 'cluster_share_cluster_2']          |
| Barajas               | barajas           |        0.546201 | True           | ['housing_per_1000_residents', 'green_area_per_10000', 'grid_pt_access_good_share']    |
| Centro                | centro            |        0.533423 | False          | ['cluster_share_cluster_1', 'grid_dense_urban_share', 'population_density_km2']        |
| Salamanca             | salamanca         |        0.530517 | False          | ['grid_dense_urban_share', 'grid_height_mean_avg', 'income_per_person']                |
| Fuencarral - El Pardo | fuencarralelpardo |        0.528553 | False          | ['grid_green_like_share', 'grid_pt_access_good_share', 'population_density_km2']       |
| Chamartín             | chamartín         |        0.528221 | False          | ['household_income', 'income_per_person', 'vulnerability_employment']                  |
| Moncloa - Aravaca     | moncloaaravaca    |        0.52245  | False          | ['cluster_share_cluster_0', 'household_income', 'cluster_share_cluster_2']             |
| Puente de Vallecas    | puentedevallecas  |        0.516682 | False          | ['unemployment_rate', 'vulnerability_index', 'vulnerability_employment']               |
| Villaverde            | villaverde        |        0.507528 | False          | ['housing_per_1000_residents', 'vulnerability_employment', 'unemployment_rate']        |
| Retiro                | retiro            |        0.502734 | False          | ['grid_height_mean_avg', 'cluster_share_cluster_1', 'vulnerability_index']             |
| Villa de Vallecas     | villadevallecas   |        0.500597 | False          | ['green_area_per_10000', 'grid_green_like_share', 'grid_pt_access_good_share']         |
| Tetuán                | tetuán            |        0.49995  | False          | ['cluster_share_cluster_1', 'population_density_km2', 'grid_dense_urban_share']        |
| Arganzuela            | arganzuela        |        0.4852   | False          | ['cluster_share_cluster_1', 'cluster_share_cluster_2', 'cluster_share_cluster_0']      |
| Vicálvaro             | vicálvaro         |        0.484473 | False          | ['green_area_per_10000', 'cluster_share_cluster_0', 'grid_pt_access_good_share']       |
| Usera                 | usera             |        0.483769 | False          | ['vulnerability_employment', 'unemployment_rate', 'income_per_person']                 |
| Hortaleza             | hortaleza         |        0.480574 | False          | ['vulnerability_index', 'green_area_per_10000', 'housing_per_1000_residents']          |
| Carabanchel           | carabanchel       |        0.464922 | False          | ['vulnerability_employment', 'income_per_person', 'household_income']                  |
| Moratalaz             | moratalaz         |        0.460984 | False          | ['cluster_share_cluster_0', 'housing_per_1000_residents', 'cluster_share_cluster_2']   |
| Ciudad Lineal         | ciudadlineal      |        0.457556 | False          | ['cluster_share_cluster_0', 'housing_per_1000_residents', 'grid_pt_access_good_share'] |
| Latina                | latina            |        0.437195 | False          | ['household_income', 'income_per_person', 'unemployment_rate']                         |
| San Blas - Canillejas | sanblascanillejas |        0.431092 | False          | ['population_density_km2', 'cluster_share_cluster_1', 'grid_dense_urban_share']        |

Warnings:
- IsolationForest anomaly flags are exploratory and sensitive to the small district count.
- The top-ranked districts are more defensible as a relative mismatch signal than as a hard anomaly diagnosis.
