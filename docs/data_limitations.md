# Data limits (to state up front)

| Limit | Consequence | How the analysis handles it |
|---|---|---|
| **No travel times** | Route durations cannot be measured. | Durations are built from assumed speeds (35-45 km/h) and stop times (15-30 min), treated as ranges (C3 sensitivity). A calibration table shows which combinations are consistent with the case narrative. |
| **One per-km rate** (Rs 19/km, hired truck) | No cost data for larger trucks; no fixed or crew cost per trip. | Capacity is valued with a break-even (willingness-to-pay) curve, not an "optimal capacity". Rate and diesel sensitivity in C5. |
| **Every location demands one cryocan** | Capacity = number of stops per route. | Stylised two-cryocan summer shock in C5, clearly labelled as illustrative. |
| **One district** (Nagpur) | External validity is unknown. | Statewide figures are a 0.5-1.5× scaling of Nagpur, labelled illustrative. |
| **Non-metric distance matrix** | 58 % of location pairs have a shorter path via a third location (mean shortcut 8.6 km). Distances look partly inconsistent (e.g. manual or mixed-source entries). | Headline results use the matrix as supplied (needed for exact replication); C5 re-solves on the shortest-path closure. C4 lets the truck drive through a dropped village so marginal costs cannot be negative. |
| **Status-quo routes exceed capacity** | Several current routes carry 24-28 cryocans on a 20-cryocan truck. | C1 reports a capacity-matched comparison (Q = 28) as well as the nominal one. |
| **Rounded published distances** | Table 1 sums to 2,602 km; the same routes measure 2,600.5 km on the matrix. | Both reported; comparisons use the matrix figure. |
| **Visit frequency is a range** | 22-25 days (summer), 30-35 days (winter). | Low / mid / high cycles per year (12.5 / 13.4 / 14.4) carried through every annual figure. |
| **Heuristic optimum** | No optimality certificate for a 177-location VRP. | Portfolio of solvers + solution pool + convergence evidence; `full` profile for longer searches. |
| **Text-typed cells** | Five matrix cells are stored as text in the workbook. | Values are read as numbers; their text type is kept only to replicate Excel's sort order. |
