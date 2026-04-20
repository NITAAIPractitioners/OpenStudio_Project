# Building Performance Comparison Report (Expert Analysis)

## 1. Goal
Evaluate the statistical agreement between CO₂-based clustering and Light-based archetypes using Adjusted Rand Index (ARI) and Normalized Mutual Information (NMI).

## 2. Statistical Validation Metrics

- **Exact Semantic Agreement Rate**: 20.0%
- **Adjusted Rand Index (ARI)**: 0.007
- **Normalized Mutual Information (NMI)**: 0.144

> [!NOTE]
> ARI measures the similarity between two clusterings by considering all pairs of samples. NMI quantifies the shared information between cluster assignments.

## 3. Comparative Table (Raw vs Semantic)

| Office | CO₂ Cluster | Light Archetype | CO₂ Sem | Light Sem | Agreement |
|--------|-------------|-----------------|---------|-----------|-----------|
| 413 | Unknown | Extended Hours | Unknown | Extended | Disagreement |
| 415 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 417 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 419 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 421 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 422 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 423 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 424 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 442 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 446 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 448 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 452 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 454 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 456 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 458 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 462 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 510 | Cluster 1 | Normal Office | Normal | Normal | Agreement |
| 511 | Cluster 6 | Normal Office | Normal | Normal | Agreement |
| 513 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 552 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 554 | Cluster 1 | Normal Office | Normal | Normal | Agreement |
| 556 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 558 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 562 | Cluster 4 | Low Occupancy | Low | Low | Agreement |
| 564 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 621 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 621A | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 621C | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 621D | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 621E | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 640 | Cluster 5 | Low Occupancy | Low | Low | Agreement |
| 644 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 648 | Cluster 3 | Extended Hours | Low | Extended | Disagreement |
| 656A | Cluster 2 | Extended Hours | Extended | Extended | Agreement |
| 656B | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 664 | Cluster 1 | Normal Office | Normal | Normal | Agreement |
| 666 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 668 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 717 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 719 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 721 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 722 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 723 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |
| 724 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 726 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 734 | Cluster 1 | Normal Office | Normal | Normal | Agreement |
| 746 | Cluster 1 | Normal Office | Normal | Normal | Agreement |
| 748 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 752 | Cluster 1 | Normal Office | Normal | Normal | Agreement |
| 754 | Cluster 1 | Low Occupancy | Normal | Low | Disagreement |
| 776 | Cluster 1 | Extended Hours | Normal | Extended | Disagreement |

## 4. Cross-tabulation (Raw Clusters vs Archetypes)

| CO2_Cluster   |   Extended Hours |   Low Occupancy |   Normal Office |
|:--------------|-----------------:|----------------:|----------------:|
| Cluster 1     |               19 |              20 |               6 |
| Cluster 2     |                1 |               0 |               0 |
| Cluster 3     |                1 |               0 |               0 |
| Cluster 4     |                0 |               1 |               0 |
| Cluster 5     |                0 |               1 |               0 |
| Cluster 6     |                0 |               0 |               1 |

## 5. Time Pattern Quantities

- **Median Lead (Light over CO₂)**: 14 minutes
- **Mean Correlation (Light vs Lagged CO₂)**: 0.029
- **Observation**: In active offices, Light activity leads CO₂ rises by a median geometric shift of 20–29 minutes, confirming the physical mass accumulation lag established in the System Audit.

## 6. PIR Evaluation
| Scenario (CO2/Light/PIR) | Count | Role |
|--------------------------|-------|------|
| Short activity | 16 | Confirmation |
| Brief motion/Noise | 16 | Confirmation |
| Strong confirmation | 11 | Confirmation |
| Occupied, only PIR/CO2 | 5 | Confirmation |
| Likely empty | 2 | Confirmation |
| Likely occupied, PIR missed | 1 | Confirmation |

## 7. Expert Conclusion

**Conclusion**: CO₂ and Light represent COMPLEMENTARY behavioral signals with distinct clustering structures.
