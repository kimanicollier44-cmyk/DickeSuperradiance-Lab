"""Tests for DickeSuperradiance-Lab. Every test grades a computed
number against a closed form or an independent route in main.py."""
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main as ds


def test_rate_endpoints_are_gamma_N():
    for n in (2, 3, 10, 25, 40):
        assert ds.transition_rate(n, n) == float(n)
        assert ds.transition_rate(1, n) == float(n)


def test_rate_mid_ladder_closed_form():
    assert ds.transition_rate(5, 10) == 30.0
    assert ds.transition_rate(6, 10) == 30.0
    assert max(ds.collective_rates(40)) == 420.0
    assert max(ds.collective_rates(9)) == 25.0  # floor((9+1)^2/4)


def test_rate_out_of_range():
    assert ds.transition_rate(0, 10) == 0.0
    assert ds.transition_rate(11, 10) == 0.0


def test_sector_rate_matches_ladder_in_symmetric_sector():
    for n in (10, 20):
        for k in range(1, n + 1):
            assert ds.sector_rate(n / 2, k - n / 2) == ds.transition_rate(k, n)


def test_independent_rates_have_no_collective_factor():
    rates = ds.independent_rates(12)
    assert rates[1] == 1.0 and rates[12] == 12.0


def test_population_conserved_and_drained():
    run = ds.burst_run(10)
    assert run["pop_drift_max"] < 1e-6
    assert run["final_excitation"] < 1e-9


def test_fully_inverted_starts_at_gamma_N():
    for n in (4, 10, 20, 40):
        assert ds.burst_run(n)["i0"] == float(n)


def test_total_emitted_energy_is_N_photons():
    sweep = ds.burst_sweep()
    assert sweep["worst_energy_error"] < 1e-3
    for row in sweep["rows"]:
        assert abs(row["emitted"] - row["n"]) < 1e-3


def test_burst_peak_exponent_windows():
    sweep = ds.burst_sweep()
    assert 1.80 <= sweep["exponent_all_4_40"] <= 1.92
    assert 1.88 <= sweep["exponent_20_40"] <= 2.02


def test_burst_contrast_grows():
    rows = {r["n"]: r for r in ds.burst_sweep()["rows"]}
    assert rows[20]["contrast"] > 3.0
    assert rows[40]["contrast"] > 5.0
    assert rows[40]["contrast"] > rows[10]["contrast"] > rows[4]["contrast"]


def test_delay_monotone_from_N6_and_scales_lnN_over_N():
    sweep = ds.burst_sweep()
    assert sweep["delay_monotone_from_6"]
    for v in sweep["delay_scaled_band"].values():
        assert 0.85 <= v <= 1.15


def test_control_peak_linear_and_monotone():
    control = ds.control_sweep()
    assert 0.95 <= control["exponent"] <= 1.05
    for row in control["rows"]:
        assert row["peak"] == float(row["n"])
        assert row["t_peak"] == 0.0
        assert row["monotone_decreasing"]


def test_half_inverted_cannot_burst():
    rep = ds.half_inverted_report()
    assert rep["i0"] == 110.0 == rep["i0_closed_form"]
    assert rep["peak"] == rep["i0"] and rep["t_peak"] == 0.0
    assert rep["monotone_decreasing"]
    assert abs(rep["emitted"] - 10.0) < 1e-3


def test_single_excitation_is_pure_exponential():
    rep = ds.single_excitation_report()
    assert rep["i0"] == 20.0
    assert rep["peak"] == rep["i0"] and rep["t_peak"] == 0.0
    assert rep["monotone_decreasing"]
    assert rep["worst_probe_error"] < 1e-3
    assert abs(rep["emitted"] - 1.0) < 1e-3


def test_singlet_exactly_dark():
    sub = ds.subradiance_report()
    assert sub["singlet_rate_J0_m0"] == 0.0
    assert sub["dark_single_excitation_rate"] == 0.0


def test_bright_single_excitation_enhanced():
    sub = ds.subradiance_report()
    assert sub["bright_single_excitation_rate"] == 20.0
    assert sub["triplet_top_rate_N2"] == 2.0


def test_leaky_dark_state_suppressed():
    leaky = ds.subradiance_report()["leaky_state"]
    assert leaky["rate"] == 0.02
    assert leaky["rate"] < ds.GAMMA / 10.0
    assert leaky["suppression_factor_vs_gamma"] == 50.0


def test_classifier_scenarios():
    rep = ds.classifier_report()
    assert rep["fully_inverted_N20"]["label"] == "superradiant-burst"
    assert rep["half_inverted_N20"]["label"] == "collective-monotone"
    assert rep["single_excitation_N20"]["label"] == "collective-monotone"
    assert rep["independent_N20"]["label"] == "independent-like"
    assert rep["singlet_N2"]["label"] == "subradiant-dark"
    assert rep["leaky_dark_N2"]["label"] == "subradiant-dark"


def test_classifier_matches_policy_everywhere():
    rep = ds.classifier_report()
    assert all(v["label"] == v["policy"] for v in rep.values())
    assert all(ds.classify_regime(*feats) == label
               for feats, label in ds.TRAINING_GRID)


def test_hold_gates():
    assert len(ds.HOLD_GATES) == 14
    assert all(v.startswith("HOLD") for v in ds.HOLD_GATES.values())
    assert ds.gate("real_emitter_array_control") == "HOLD"
    assert ds.gate("superradiant_laser_product_claim") == "HOLD"
    assert ds.gate("run_simulation") == "PROCEED"


def test_seats_never_override():
    brains = ds.brains_report()
    assert brains["decider"]["can_override_hold"] is False
    assert brains["decider"]["seat"] == "Gemini Argon 4 Extended Thinking"
    assert brains["advisor"]["can_override_hold"] is False
    assert brains["flow"]["rendered"] is False
    assert brains["flow"]["live"] == 0


def test_hold_demo_exits_2():
    proc = subprocess.run(
        [sys.executable, "main.py", "hold-demo"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "HOLD" in proc.stdout


def test_checks_all_pass():
    checks = ds.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]
    assert len(checks) == 49
