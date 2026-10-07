from lastmile.config import load_settings


def test_profiles_override():
    quick, full = load_settings("quick"), load_settings("full")
    assert full.solver.ortools_time_limit_s > quick.solver.ortools_time_limit_s
    assert quick.economics.rate_per_km == 19.0
    assert load_settings("smoke").results_dir.name == "results_smoke"
