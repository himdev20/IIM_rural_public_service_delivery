# Replication notes (Component 0)

The targets are the three numbers the original spreadsheet work produced:

| Benchmark | Target | Python | How it is checked |
|---|---|---|---|
| Status quo, Table 1 (reported) | 2,602 km | 2,602 km | sum of the nine published route lengths |
| Spreadsheet savings model, Q = 20 (`Sheet20`) | 2,336.7 km | 2,336.7 km | total **and** every route, node by node, in the same order and direction |
| Spreadsheet savings model, Q = 25 (`Sheet25`) | 2,237.5 km | 2,237.5 km | as above |

The test suite (`tests/test_replication.py`) and Component 0 (`python -m lastmile c0`) both
fail loudly if any of these stop matching.

## Two status-quo numbers

Table 1 reports route lengths rounded to whole kilometres (sum 2,602). Re-measuring the same
nine sequences on the distance matrix gives **2,600.5 km** (differences of 0.3-0.5 km on six
routes). All comparisons between solutions use the matrix figure, so the status quo and the
optimised plans are measured with the same ruler; 2,602 is reported for continuity with the case.

## What the spreadsheet actually does

`01_IIM_Indore_project_for_SCM_MDP.xlsm` contains a VBA module (extracted with `olevba`) with
three buttons: *Saving* (build the savings matrix), *Sort* (sort the savings) and *Route*
(build routes). `lastmile/solvers/savings_vba.py` re-implements it line by line. Reproducing
the routes exactly required replicating several behaviours that are easy to miss:

1. **Excel sort semantics.** Pairs (i > j) are sorted by saving descending; each block of equal
   savings is then re-sorted by distance ascending. Five cells of the `Dmatrix` sheet are stored as
   **text**, e.g. d(149, 45) = `"51"`, d(172, 71) = `"62"`. Excel sorts text after all numbers, so
   these pairs fall to the end of their tie block. Excel's sort is stable, so remaining ties keep
   the generation order (i ascending, then j ascending). Our order matches all 15,576 rows of the
   workbook's `Sort` sheet.
2. **The first pair always opens truck 1.**
3. **Off-by-one:** the route loop runs over rows 3 to `ncom` of a list that ends at row `ncom + 1`,
   so the last pair is never examined.
4. **Negative savings are used.** Unlike the textbook algorithm, the macro keeps joining routes
   whenever capacity allows, even when the join lengthens the tour.
5. **Truck slots.** When two routes merge, the lower slot keeps the merged route and the last truck
   is moved into the freed slot. This only affects the order in which routes are printed, but it is
   needed for a route-by-route match.
6. **`checklast`** (one location left over at the end) contains inverted logic: it does nothing if
   *any* truck has spare capacity, and force-inserts the location (ignoring capacity) only if none
   does. It never triggers on the case data; it is replicated for completeness.
7. Locations never reached by a pair would silently be left out. The Python version records them
   in `solution.meta["unserved"]`, and the solution then fails validation.

For analysis, the code uses `lastmile/solvers/savings.py`, a clean textbook version (all pairs,
positive savings only, optional duration limit). It differs slightly from the spreadsheet
(Component 0 reports both), which is why the spreadsheet result is labelled
"spreadsheet CW" throughout.

## Data quirks found during replication

* The two workbooks (`02_Main_Case_Data_File.xlsx` and the `.xlsm`) contain the same distance
  matrix and the same depot distances.
* Table 3 of the case PDF (25 sample locations) differs from the full matrix by up to 0.5 km
  (rounding in the paper). The analysis uses the full matrix.
* The matrix is **not metric**: for 58 % of location pairs there is a shorter path via a third
  location (mean shortcut 8.6 km, maximum 82 km). See `data_limitations.md`.
