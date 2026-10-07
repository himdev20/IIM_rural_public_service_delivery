"""Line-by-line re-implementation of the VBA savings macro in the course workbook.

Purpose: reproduce the spreadsheet results *exactly* (2,336.7 km at Q=20 and
2,237.5 km at Q=25, route by route), so every later comparison starts from a
verified baseline. Use :mod:`lastmile.solvers.savings` for analysis; this module
keeps the macro's behaviour, including its quirks:

1. **Sort order.** Pairs (i > j) are sorted by saving (descending), then within
   blocks of equal savings by distance (ascending) with Excel's rules: numbers
   before text, text compared as strings. Five matrix cells are stored as text
   in the workbook (e.g. d(149, 45) = "51"), which pushes those pairs to the end
   of their block. Excel's sort is stable, so remaining ties keep (i, j) order.
2. **First pair.** The first pair always opens truck 1 (``newtruck(2)``).
3. **Pairs are processed from row 3 to row ncom** -- the very last pair in the
   list is never examined (an off-by-one in ``getpath``).
4. **All savings are processed**, including negative ones: two routes are joined
   whenever capacity allows, even if joining lengthens the tour.
5. **Merging** (``link``) always keeps the lower-numbered truck slot and moves the
   last truck into the freed slot (``replace``); this only affects route order.
6. **checklast** (one location left unrouted at the very end) contains inverted
   logic in the VBA; it is replicated but never triggers on the case data.
7. Locations not reached by any pair are left unserved -- the returned solution
   then fails validation, which makes the issue visible instead of silent.
"""

from __future__ import annotations

from ..data import Instance, savings_matrix
from ..model import Problem, Solution


def vba_sorted_pairs(inst: Instance) -> list[tuple[int, int]]:
    """Pairs (i, j), i > j, in the exact order of the workbook's ``Sort`` sheet."""
    d0 = inst.depot_dist
    pairs = []
    for i in range(1, inst.n + 1):  # VBA loop order: i ascending, j < i ascending
        for j in range(1, i):
            saving = round(d0[i] + d0[j] - inst.dist[i, j], 6)
            if (i, j) in inst.text_cells:
                dist_key = (1, f"{inst.dist[i, j]:g}".lower())  # text sorts after numbers
            else:
                dist_key = (0, float(inst.dist[i, j]))
            pairs.append((saving, dist_key, i, j))
    pairs.sort(key=lambda p: (-p[0], p[1]))  # Python's sort is stable, like Excel's
    return [(i, j) for _, _, i, j in pairs]


def solve_vba(problem: Problem) -> Solution:
    """Run the macro's algorithm. Only capacity is considered (as in the workbook)."""
    inst = problem.instance
    if problem.customers is not None:
        raise ValueError("The VBA replica works on the full instance only")
    Q = problem.capacity
    pairs = [list(p) for p in vba_sorted_pairs(inst)]
    unassigned = {i: int(inst.demand[i]) for i in inst.customers}  # Run!F column
    trucks: list[dict] = []  # each {"route": [...], "load": int}

    def delete(node: int) -> None:  # zero every remaining pair containing `node`
        for p in pairs:
            if p[0] == node or p[1] == node:
                p[0] = p[1] = 0

    def new_truck(row: int) -> None:
        a, b = pairs[row]
        trucks.append({"route": [a, b], "load": unassigned[a] + unassigned[b]})
        unassigned[a] = unassigned[b] = 0

    new_truck(0)
    for row in range(1, len(pairs) - 1):  # quirk 3: last pair skipped
        a, b = pairs[row]
        if a == 0:
            continue
        f1 = f2 = False
        k1 = k2 = ad = None
        at_second = False  # VBA variable `l`
        for k, t in enumerate(trucks):
            if a in (t["route"][0], t["route"][-1]):
                f1, ad, k1 = True, k, k
            if b in (t["route"][0], t["route"][-1]):
                f2, ad, k2, at_second = True, k, k, True

        if f1 and f2:
            if k1 != k2 and Q >= trucks[k1]["load"] + trucks[k2]["load"]:
                _link(trucks, a, b, min(k1, k2), max(k1, k2))
                delete(a)
                delete(b)
        elif f1 or f2:
            end, other = (b, a) if at_second else (a, b)
            t = trucks[ad]
            if t["route"][0] == end and Q >= t["load"] + unassigned[other]:
                t["route"].insert(0, other)
            elif t["route"][-1] == end and Q >= t["load"] + unassigned[other]:
                t["route"].append(other)
            else:
                continue
            t["load"] += unassigned[other]
            unassigned[other] = 0
            delete(end)
        else:
            new_truck(row)

    left = [i for i, q in unassigned.items() if q]
    if len(left) == 1:
        _check_last(inst, trucks, left[0], unassigned, Q)
        left = [i for i, q in unassigned.items() if q]

    return Solution(problem, [t["route"] for t in trucks], method="cw_spreadsheet",
                    meta={"unserved": left})


def _link(trucks: list[dict], a: int, b: int, lo: int, hi: int) -> None:
    """Join truck `hi` into truck `lo` through edge (a, b), as in VBA ``link``."""
    r1, r2 = trucks[lo]["route"], trucks[hi]["route"]
    if (a == r1[0] and b == r2[-1]) or (b == r1[0] and a == r2[-1]):
        merged = r2 + r1
    elif (a == r2[0] and b == r1[-1]) or (b == r2[0] and a == r1[-1]):
        merged = r1 + r2
    elif (a == r2[0] and b == r1[0]) or (a == r1[0] and b == r2[0]):
        merged = r2[::-1] + r1
    else:  # both at the tail ends
        merged = r1 + r2[::-1]
    trucks[lo] = {"route": merged, "load": trucks[lo]["load"] + trucks[hi]["load"]}
    if hi != len(trucks) - 1:
        trucks[hi] = trucks[-1]
    trucks.pop()


def _check_last(inst: Instance, trucks: list[dict], node: int, unassigned: dict, Q: int) -> None:
    """VBA ``checklast``: only acts when *no* truck has spare capacity (sic)."""
    if any(t["load"] + unassigned[node] <= Q for t in trucks):
        return  # replicated quirk: the location stays unserved
    s = savings_matrix(inst)
    best, best_k, at_end = -2.0, None, False
    for k, t in enumerate(trucks):
        if s[t["route"][-1], node] > best:
            best, best_k, at_end = s[t["route"][-1], node], k, True
        if s[t["route"][0], node] > best:
            best, best_k, at_end = s[t["route"][0], node], k, False
    t = trucks[best_k]
    t["route"].append(node) if at_end else t["route"].insert(0, node)
    t["load"] += unassigned[node]
    unassigned[node] = 0
