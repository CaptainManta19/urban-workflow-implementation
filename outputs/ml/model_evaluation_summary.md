# Model Evaluation Summary

## Clustering

| model_name       |   cluster_count |   silhouette |   profile_count |   min_cluster_size |   max_cluster_size |   smallest_cluster_share |   largest_cluster_share |   tiny_cluster_count |   small_cluster_count |
|:-----------------|----------------:|-------------:|----------------:|-------------------:|-------------------:|-------------------------:|------------------------:|---------------------:|----------------------:|
| gaussian_mixture |               3 |   -0.0280536 |               3 |                567 |               2439 |                   0.1299 |                  0.5588 |                    0 |                     0 |
| gaussian_mixture |               4 |   -0.07621   |               4 |                333 |               1821 |                   0.0763 |                  0.4172 |                    0 |                     0 |
| gaussian_mixture |               5 |   -0.0656385 |               5 |                 31 |               1819 |                   0.0071 |                  0.4167 |                    1 |                     1 |
| gaussian_mixture |               6 |   -0.0577862 |               6 |                  4 |               1272 |                   0.0009 |                  0.2914 |                    1 |                     1 |
| gaussian_mixture |               7 |   -0.0782392 |               7 |                  1 |               1292 |                   0.0002 |                  0.296  |                    2 |                     3 |
| kmeans           |               3 |    0.3792    |               3 |                185 |               2341 |                   0.0424 |                  0.5363 |                    0 |                     1 |
| kmeans           |               4 |    0.343203  |               4 |                162 |               2035 |                   0.0371 |                  0.4662 |                    0 |                     1 |
| kmeans           |               5 |    0.302351  |               5 |                  4 |               1828 |                   0.0009 |                  0.4188 |                    1 |                     2 |
| kmeans           |               6 |    0.326924  |               6 |                  1 |               1924 |                   0.0002 |                  0.4408 |                    1 |                     2 |
| kmeans           |               7 |    0.304687  |               7 |                  1 |               1777 |                   0.0002 |                  0.4071 |                    2 |                     3 |

Warnings:
- gaussian_mixture with k=3 has a weak silhouette score below 0.25.
- gaussian_mixture with k=4 has a weak silhouette score below 0.25.
- gaussian_mixture with k=5 has a weak silhouette score below 0.25.
- gaussian_mixture with k=5 produced at least one tiny cluster below 1% of eligible cells.
- gaussian_mixture with k=6 has a weak silhouette score below 0.25.
- gaussian_mixture with k=6 produced at least one tiny cluster below 1% of eligible cells.
- gaussian_mixture with k=7 has a weak silhouette score below 0.25.
- gaussian_mixture with k=7 produced at least one tiny cluster below 1% of eligible cells.
- gaussian_mixture with k=7 produced multiple small clusters below 5% of eligible cells.
- kmeans with k=5 produced at least one tiny cluster below 1% of eligible cells.
- kmeans with k=5 produced multiple small clusters below 5% of eligible cells.
- kmeans with k=6 produced at least one tiny cluster below 1% of eligible cells.
- kmeans with k=6 produced multiple small clusters below 5% of eligible cells.
- kmeans with k=7 produced at least one tiny cluster below 1% of eligible cells.
- kmeans with k=7 produced multiple small clusters below 5% of eligible cells.

## Anomaly Detection

| district_name   | district_key   |   iforest_score | iforest_flag   | iforest_top_features                                                                |   lof_score | lof_flag   | lof_top_features                                                                    | flagged_by_both   | flagged_by_either   |
|:----------------|:---------------|----------------:|:---------------|:------------------------------------------------------------------------------------|------------:|:-----------|:------------------------------------------------------------------------------------|:------------------|:--------------------|
| Chamberí        | chamberí       |        0.553524 | True           | ['cluster_share_cluster_2', 'grid_height_mean_avg', 'grid_dense_urban_share']       |    0.989304 | False      | ['cluster_share_cluster_2', 'grid_height_mean_avg', 'grid_dense_urban_share']       | False             | True                |
| Barajas         | barajas        |        0.545467 | True           | ['housing_per_1000_residents', 'grid_pt_access_good_share', 'green_area_per_10000'] |    0.994525 | False      | ['housing_per_1000_residents', 'grid_pt_access_good_share', 'green_area_per_10000'] | False             | True                |
| Chamartín       | chamartín      |        0.536435 | True           | ['household_income', 'cluster_share_cluster_4', 'income_per_person']                |    0.997538 | False      | ['household_income', 'cluster_share_cluster_4', 'income_per_person']                | False             | True                |
| Hortaleza       | hortaleza      |        0.470971 | False          | ['grid_green_like_share', 'vulnerability_index', 'grid_pt_access_good_share']       |    1.00893  | True       | ['grid_green_like_share', 'vulnerability_index', 'grid_pt_access_good_share']       | False             | True                |
| Moratalaz       | moratalaz      |        0.444225 | False          | ['housing_per_1000_residents', 'vulnerability_index', 'household_income']           |    1.01381  | True       | ['housing_per_1000_residents', 'vulnerability_index', 'household_income']           | False             | True                |
| Ciudad Lineal   | ciudadlineal   |        0.442973 | False          | ['cluster_share_cluster_1', 'housing_per_1000_residents', 'green_area_per_10000']   |    1.01137  | True       | ['cluster_share_cluster_1', 'housing_per_1000_residents', 'green_area_per_10000']   | False             | True                |

Warnings:
- IsolationForest and LocalOutlierFactor do not agree on any flagged districts.
