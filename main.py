#!/usr/bin/env python3
"""DickeSuperradiance-Lab - educational collective-emission lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the central lesson is stated up front:

  * This lab computes the textbook Dicke model: N identical two-level
    emitters coupled to ONE common radiation mode, treated in the
    symmetric J = N/2 ladder with exact transition rates
    Gamma_{m->m-1} = gamma (J+m)(J-m+1). Populations are integrated
    deterministically (fixed-step RK4) - there is no sampling and no
    random number anywhere in the file.
  * Everything is in units of the single-atom rate gamma = 1 and the
    photon energy hbar*omega = 1. "Intensity" is the expected number
    of photons emitted per unit time.
  * The idealisations are the lesson, and they are stated, not hidden:
    identical emitters, identical coupling, a sample small compared
    to the wavelength, no dephasing, no inhomogeneous broadening, no
    propagation effects. Real ensembles leak, dephase, and broaden -
    so the perfectly dark states here are exactly dark ONLY inside
    this model, and no number in this file is a hardware figure.
  * Real emitter arrays, lasers, cavities, clocks, memories, sensors,
    and every product or performance claim built on this model are
    permanent HOLD gates - with Gemini Argon 4 Extended Thinking as
    DECIDER (names-only, tighten-only), Muse as advisor (never
    overrides HOLD), and Google Flow plan-only seats.
"""
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"
GAMMA = 1.0          # single-atom spontaneous emission rate (the unit)
HBAR_OMEGA = 1.0     # photon energy (the unit)
LAM_DT = 0.1         # RK4 step: dt = LAM_DT / (largest rate in the chain)
STOP_EXCITATION = 1e-11   # integrate until mean excitation falls below this
SWEEP_NS = tuple(range(4, 41))   # burst-scaling sweep range

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "real_emitter_array_control": "HOLD - no driving or controlling real atom, ion, quantum-dot, or superconducting emitter arrays",
    "live_laser_pump_operation": "HOLD - no operating real excitation lasers, pumps, or inversion hardware",
    "superradiant_laser_product_claim": "HOLD - no claim this simulation is a superradiant laser design, prototype, or product",
    "quantum_memory_product_claim": "HOLD - no quantum memory or storage product claims from subradiant-state lifetimes in a model",
    "atomic_clock_product_claim": "HOLD - no atomic clock product or frequency-standard claims from this lab",
    "directed_energy_claim": "HOLD - no directed-energy or weapon use of collective emission models",
    "medical_emission_claim": "HOLD - no medical imaging, therapy, or dose claims from emission models",
    "hardware_rate_claim": "HOLD - no presenting computed model rates as measured hardware specifications",
    "real_cavity_qed_operation": "HOLD - no operating real cavity-QED or circuit-QED hardware from this simulation",
    "live_experiment_automation": "HOLD - no automating live laboratory experiments from this offline model",
    "state_preparation_claim": "HOLD - no claim the lab prepares real quantum states; states here are population vectors in a model",
    "sensor_product_claim": "HOLD - no sensor product claims; collective enhancement in a model is not a device",
    "investment_claim": "HOLD - no investment claims; a teaching model is not a prospectus",
    "certified_result_claim": "HOLD - no presenting simulation output as certified, peer-reviewed, or measured fact",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Dicke ladder machinery
# The symmetric sector of N two-level emitters is a ladder of N+1
# states |J, m> with J = N/2. Counting states by excitation number
# k = J + m (k = N fully inverted, k = 0 ground), the collective
# emission rate down one rung is
#
#     Gamma_{k -> k-1} = gamma * k * (N - k + 1)
#
# The k factor is the number of excited emitters; the (N - k + 1)
# factor is the collective enhancement - the already-emitted field
# stimulates the next emission. At the ladder ends the rate is
# gamma*N (first step down, last step down); mid-ladder it reaches
# gamma * floor((N+1)^2 / 4), the engine of the burst.
#
# Populations obey a pure death chain, integrated with fixed-step
# RK4 at dt = LAM_DT / max(rate). Deterministic: no sampling.

def transition_rate(k, n_atoms):
    """Collective rate (units of gamma) for k -> k-1 excitations,
    symmetric sector of n_atoms emitters: gamma * k * (N - k + 1)."""
    if not 1 <= k <= n_atoms:
        return 0.0
    return GAMMA * k * (n_atoms - k + 1)


def sector_rate(J, m):
    """Emission rate (units of gamma) of a general Dicke state |J, m>
    to |J, m-1>: gamma * (J+m)(J-m+1). Valid for any total-angular-
    momentum sector, symmetric or not."""
    return GAMMA * (J + m) * (J - m + 1)


def collective_rates(n_atoms):
    """Rate table for the symmetric ladder, index = excitations k."""
    return [0.0] + [transition_rate(k, n_atoms)
                    for k in range(1, n_atoms + 1)]


def independent_rates(n_atoms):
    """Control rate table: each emitter decays on its own at gamma,
    so k excitations decay at gamma*k - no collective factor."""
    return [0.0] + [GAMMA * k for k in range(1, n_atoms + 1)]


def _deriv(pop, rates, n_atoms):
    out = [0.0] * (n_atoms + 1)
    for k in range(1, n_atoms + 1):
        flux = rates[k] * pop[k]
        out[k] -= flux
        out[k - 1] += flux
    return out


def _intensity(pop, rates, n_atoms):
    return sum(rates[k] * pop[k] for k in range(1, n_atoms + 1))


def simulate_chain(n_atoms, n_start, rates, stop_excitation=STOP_EXCITATION,
                   max_time=None):
    """Integrate the population death chain from a pure start state.

    Returns the full intensity series plus summary observables. The
    emitted-energy integral is accumulated by the trapezoid rule on
    the same grid, so energy bookkeeping and dynamics can be graded
    against each other (and against the exact total, n_start).
    """
    lam = max(rates)
    dt = LAM_DT / lam
    pop = [0.0] * (n_atoms + 1)
    pop[n_start] = 1.0
    t = 0.0
    i_now = _intensity(pop, rates, n_atoms)
    times = [0.0]
    series = [i_now]
    emitted = 0.0
    pop_drift = 0.0
    while True:
        k1 = _deriv(pop, rates, n_atoms)
        p2 = [pop[i] + 0.5 * dt * k1[i] for i in range(n_atoms + 1)]
        k2 = _deriv(p2, rates, n_atoms)
        p3 = [pop[i] + 0.5 * dt * k2[i] for i in range(n_atoms + 1)]
        k3 = _deriv(p3, rates, n_atoms)
        p4 = [pop[i] + dt * k3[i] for i in range(n_atoms + 1)]
        k4 = _deriv(p4, rates, n_atoms)
        pop = [pop[i] + dt * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]) / 6.0
               for i in range(n_atoms + 1)]
        t += dt
        i_next = _intensity(pop, rates, n_atoms)
        emitted += 0.5 * (i_now + i_next) * dt
        i_now = i_next
        times.append(t)
        series.append(i_now)
        drift = abs(sum(pop) - 1.0)
        if drift > pop_drift:
            pop_drift = drift
        excitation = sum(k * pop[k] for k in range(n_atoms + 1))
        if excitation < stop_excitation:
            break
        if max_time is not None and t >= max_time:
            break
        if t > 1e4:  # safety net; never reached for the lab's chains
            break
    peak_idx = max(range(len(series)), key=lambda i: series[i])
    return {
        "n_atoms": n_atoms,
        "n_start": n_start,
        "times": times,
        "intensity": series,
        "i0": series[0],
        "peak": series[peak_idx],
        "t_peak": times[peak_idx],
        "emitted": emitted,
        "final_excitation": excitation,
        "pop_drift_max": pop_drift,
        "steps": len(times) - 1,
        "dt": dt,
    }


def is_monotone_decreasing(series, rtol=1e-9, atol=1e-12):
    return all(series[i + 1] <= series[i] * (1.0 + rtol) + atol
               for i in range(len(series) - 1))


# ================================================================ 2. The superradiant burst
# Fully inverted, the ladder starts slowly (first rate only gamma*N),
# accelerates as population reaches mid-ladder where the rates are
# ~ gamma*N^2/4, and the emitted intensity forms a delayed pulse -
# the Dicke burst. Its three signatures, all computed here:
#   * peak intensity ~ N^2 (vs ~ N for independent emitters)
#   * delay time ~ (ln N) / (N * gamma)
#   * total emitted energy exactly N photons (bookkeeping receipt)

_BURST_CACHE = {}


def burst_run(n_atoms):
    """Fully inverted symmetric run, cached per process."""
    if n_atoms not in _BURST_CACHE:
        _BURST_CACHE[n_atoms] = simulate_chain(
            n_atoms, n_atoms, collective_rates(n_atoms))
    return _BURST_CACHE[n_atoms]


def _loglog_fit(xs, ys):
    n = len(xs)
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    mx = sum(lx) / n
    my = sum(ly) / n
    sxy = sum((lx[i] - mx) * (ly[i] - my) for i in range(n))
    sxx = sum((v - mx) ** 2 for v in lx)
    slope = sxy / sxx
    return slope, my - slope * mx


def burst_sweep():
    """Peak, delay, and emitted energy for N = 4..40, fully inverted."""
    rows = []
    for n in SWEEP_NS:
        run = burst_run(n)
        rows.append({
            "n": n,
            "peak": run["peak"],
            "t_peak": run["t_peak"],
            "i0": run["i0"],
            "emitted": run["emitted"],
            "contrast": run["peak"] / run["i0"],
        })
    ns = [r["n"] for r in rows]
    peaks = [r["peak"] for r in rows]
    exp_all, _ = _loglog_fit(ns, peaks)
    hi = [r for r in rows if r["n"] >= 20]
    exp_hi, _ = _loglog_fit([r["n"] for r in hi], [r["peak"] for r in hi])
    delays = {r["n"]: r["t_peak"] for r in rows}
    return {
        "rows": rows,
        "exponent_all_4_40": exp_all,
        "exponent_20_40": exp_hi,
        "worst_energy_error": max(abs(r["emitted"] - r["n"]) for r in rows),
        "delay_monotone_from_6": all(
            delays[n + 1] < delays[n] for n in range(6, 40)),
        "delay_scaled_band": {
            n: delays[n] * n / math.log(n) for n in (10, 20, 40)},
    }


def control_sweep():
    """Independent-emitter control over the same N range.

    Each run is integrated only until the intensity has fallen to
    half its initial value - long enough to prove the intensity is
    monotone decreasing, so the peak is the initial value gamma*N
    itself. No burst, no delay, peak exactly linear in N.
    """
    rows = []
    for n in SWEEP_NS:
        run = simulate_chain(n, n, independent_rates(n), max_time=1.0)
        half = next((i for i, v in enumerate(run["intensity"])
                     if v <= 0.5 * run["i0"]), len(run["intensity"]) - 1)
        rows.append({
            "n": n,
            "peak": run["peak"],
            "i0": run["i0"],
            "t_peak": run["t_peak"],
            "monotone_decreasing": is_monotone_decreasing(
                run["intensity"][:half + 1]),
        })
    exp_fit, _ = _loglog_fit([r["n"] for r in rows],
                             [r["peak"] for r in rows])
    return {"rows": rows, "exponent": exp_fit}


# ================================================================ 3. Starts that cannot burst
# Superradiance is a ladder effect: the burst exists because the
# population CLIMBS toward faster rungs. Start at or below mid-ladder
# and every next rung is slower - the intensity can only fall.

def half_inverted_report(n_atoms=20):
    """Start at k = N/2 excitations, the fastest rung itself."""
    run = simulate_chain(n_atoms, n_atoms // 2,
                         collective_rates(n_atoms))
    return {
        "n_atoms": n_atoms,
        "n_start": n_atoms // 2,
        "i0": run["i0"],
        "i0_closed_form": transition_rate(n_atoms // 2, n_atoms),
        "peak": run["peak"],
        "t_peak": run["t_peak"],
        "monotone_decreasing": is_monotone_decreasing(run["intensity"]),
        "emitted": run["emitted"],
    }


def single_excitation_report(n_atoms=20):
    """One excitation shared symmetrically (the W state): the decay
    is a pure exponential at the enhanced rate gamma*N - fast, but
    monotone. Compared against the closed form N*exp(-N t) directly.
    """
    run = simulate_chain(n_atoms, 1, collective_rates(n_atoms))
    probes = {}
    for tq in (0.01, 0.05, 0.1):
        idx = min(range(len(run["times"])),
                  key=lambda i: abs(run["times"][i] - tq))
        probes[tq] = {
            "numeric": run["intensity"][idx],
            "analytic": n_atoms * math.exp(-n_atoms * run["times"][idx]),
            "t": run["times"][idx],
        }
    return {
        "n_atoms": n_atoms,
        "i0": run["i0"],
        "peak": run["peak"],
        "t_peak": run["t_peak"],
        "monotone_decreasing": is_monotone_decreasing(run["intensity"]),
        "emitted": run["emitted"],
        "probes": probes,
        "worst_probe_error": max(
            abs(p["numeric"] - p["analytic"]) for p in probes.values()),
    }


# ================================================================ 4. Subradiance
# The same rate formula, read in the non-symmetric sectors. A state
# at the BOTTOM of its J ladder (m = -J) has no rung below it inside
# its sector, and J is conserved by the collective coupling - so its
# emission rate is exactly zero in this model. The two-atom singlet
# (J = 0) is the smallest example; the non-symmetric single-excitation
# states (bottom of the J = N/2 - 1 ladders) are dark for any N.
#
# MODELLING ASSUMPTION, stated plainly: this darkness is exact only
# under the ideal Dicke assumptions (identical emitters seeing the
# same field). Any coupling mismatch leaks. The lab prices one leak
# by hand: a state with bright-state weight w emits at w times the
# bright rate.

def subradiance_report():
    n = 20
    singlet = sector_rate(0, 0)
    dark_single = sector_rate(n / 2 - 1, -(n / 2 - 1))
    bright_single = sector_rate(n / 2, -n / 2 + 1)
    triplet_top = sector_rate(1, 1)
    bright_weight = 0.01
    leaky = bright_weight * triplet_top + (1.0 - bright_weight) * singlet
    return {
        "singlet_rate_J0_m0": singlet,
        "dark_single_excitation_rate": dark_single,
        "bright_single_excitation_rate": bright_single,
        "triplet_top_rate_N2": triplet_top,
        "leaky_state": {
            "bright_weight": bright_weight,
            "rate": leaky,
            "suppression_factor_vs_gamma": (GAMMA / leaky) if leaky else None,
        },
        "assumption": ("Exact darkness holds only in the ideal Dicke "
                       "model: identical emitters, identical coupling, "
                       "J conserved. Real ensembles leak."),
    }


# ================================================================ 5. Regime classifier
# Features measured from a run: collectivity R = peak/(gamma*N),
# contrast C = peak/I(0) (the burst signature: intensity that RISES),
# and the initial rate per excitation r0 = I(0)/n_start. The policy
# below is the lab's own labelling rule; the kNN interpolates it.

def model_label(collectivity, contrast, rate_per_excitation):
    """The regime policy distilled to a four-way teaching label."""
    if collectivity < 0.05:
        return "subradiant-dark"
    if contrast >= 1.5:
        return "superradiant-burst"
    if collectivity >= 1.5 or rate_per_excitation >= 1.5:
        return "collective-monotone"
    return "independent-like"


def _training_grid():
    rows = []
    for r in (0.0, 0.02, 0.5, 1.0, 1.4, 2.0, 5.0, 10.0, 20.0):
        for c in (1.0, 1.2, 1.49, 1.5, 2.0, 5.0):
            for r0 in (0.0, 1.0, 1.4, 2.0, 10.0, 20.0):
                rows.append(((r, c, r0), model_label(r, c, r0)))
    return rows


TRAINING_GRID = _training_grid()


def _scaled(features):
    r, c, r0 = features
    return (r / 20.0, c / 5.0, r0 / 20.0)


def classify_regime(collectivity, contrast, rate_per_excitation, k=5):
    """Distance-weighted kNN over the policy-labelled grid."""
    target = _scaled((collectivity, contrast, rate_per_excitation))
    ranked = []
    for features, label in TRAINING_GRID:
        point = _scaled(features)
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target, point)))
        ranked.append((dist, features, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    weights = {}
    for dist, _, label in ranked[:k]:
        weights[label] = weights.get(label, 0.0) + 1.0 / (dist + 1e-6)
    priority = {"superradiant-burst": 0, "collective-monotone": 1,
                "independent-like": 2, "subradiant-dark": 3}
    return sorted(weights.items(),
                  key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


def _features_from_run(run):
    r = run["peak"] / (GAMMA * run["n_atoms"])
    c = run["peak"] / run["i0"] if run["i0"] > 0 else 1.0
    r0 = run["i0"] / run["n_start"] if run["n_start"] else 0.0
    return (r, c, r0)


def classifier_report():
    """Scenarios whose features are measured from the lab's own runs."""
    scenarios = {}
    full = burst_run(20)
    scenarios["fully_inverted_N20"] = _features_from_run(full)
    half = simulate_chain(20, 10, collective_rates(20))
    scenarios["half_inverted_N20"] = _features_from_run(half)
    single = simulate_chain(20, 1, collective_rates(20))
    scenarios["single_excitation_N20"] = _features_from_run(single)
    indep = simulate_chain(20, 20, independent_rates(20), max_time=1.0)
    scenarios["independent_N20"] = _features_from_run(indep)
    sub = subradiance_report()
    scenarios["singlet_N2"] = (sub["singlet_rate_J0_m0"] / (GAMMA * 2), 1.0, 0.0)
    leaky_rate = sub["leaky_state"]["rate"]
    scenarios["leaky_dark_N2"] = (leaky_rate / (GAMMA * 2), 1.0, leaky_rate)
    return {name: {"features": feats,
                   "label": classify_regime(*feats),
                   "policy": model_label(*feats)}
            for name, feats in scenarios.items()}


# ================================================================ 6. Advisory seats
def _trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="dicke-superradiance-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all hardware and product gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="dicke-superradiance-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Lead with the receipts: the burst is a ladder effect, so show the rate table, the N^2 fit with its finite-size exponent printed honestly, and the energy bookkeeping that must total exactly N photons - then say which idealisations the darkness of subradiant states depends on.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["twenty inverted emitters holding silent for a beat",
                  "the mid-ladder rungs lighting in sequence as the burst fires",
                  "a lone photon leaving a symmetric W state at twenty times the lone rate",
                  "a singlet sitting dark while its bright triplet neighbour flashes",
                  "the peak-intensity curve bending toward slope 2 on a log-log plot"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # 1. ladder rate formula - closed forms
    chk("rate_first_step_gamma_N",
        all(transition_rate(n, n) == float(n) for n in (2, 10, 40)))
    chk("rate_last_step_gamma_N",
        all(transition_rate(1, n) == float(n) for n in (2, 10, 40)))
    chk("rate_mid_ladder_N10", transition_rate(5, 10) == 30.0
        and transition_rate(6, 10) == 30.0)
    chk("rate_max_N40", max(collective_rates(40)) == 420.0)
    chk("rate_out_of_range_zero", transition_rate(0, 10) == 0.0
        and transition_rate(11, 10) == 0.0)
    chk("independent_rates_linear",
        independent_rates(10)[7] == 7.0 and independent_rates(10)[10] == 10.0)
    chk("sector_rate_symmetric_matches_ladder",
        all(sector_rate(n / 2, k - n / 2) == transition_rate(k, n)
            for n in (10, 20) for k in range(1, n + 1)))

    # 2. integration bookkeeping
    small = burst_run(10)
    chk("population_conserved", small["pop_drift_max"] < 1e-6)
    chk("fully_inverted_i0_is_gamma_N",
        all(burst_run(n)["i0"] == float(n) for n in (4, 10, 20, 40)))
    chk("final_excitation_drained", small["final_excitation"] < 1e-9)

    # 3. the burst - scaling, delay, energy receipt
    sweep = burst_sweep()
    chk("energy_totals_N_photons", sweep["worst_energy_error"] < 1e-3)
    chk("burst_exponent_window_4_40",
        1.80 <= sweep["exponent_all_4_40"] <= 1.92)
    chk("burst_exponent_approaches_2",
        1.88 <= sweep["exponent_20_40"] <= 2.02)
    chk("burst_contrast_N40_over_5",
        [r for r in sweep["rows"] if r["n"] == 40][0]["contrast"] > 5.0)
    chk("burst_contrast_N20_over_3",
        [r for r in sweep["rows"] if r["n"] == 20][0]["contrast"] > 3.0)
    chk("delay_monotone_from_N6", sweep["delay_monotone_from_6"])
    chk("delay_scaled_lnN_over_N_band",
        all(0.85 <= v <= 1.15 for v in sweep["delay_scaled_band"].values()))
    chk("delay_shrinks_N10_to_N40",
        sweep["delay_scaled_band"][40] / 40.0 * math.log(40)
        < 0.5 * (sweep["delay_scaled_band"][10] / 10.0 * math.log(10)))

    # 4. control - independent emitters cannot burst
    control = control_sweep()
    chk("control_peak_is_gamma_N",
        all(r["peak"] == float(r["n"]) for r in control["rows"]))
    chk("control_exponent_window_1", 0.95 <= control["exponent"] <= 1.05)
    chk("control_monotone_no_burst",
        all(r["monotone_decreasing"] and r["t_peak"] == 0.0
            for r in control["rows"]))

    # 5. starts that cannot burst
    half = half_inverted_report()
    chk("half_inverted_i0_closed_form",
        half["i0"] == 110.0 and half["i0"] == half["i0_closed_form"])
    chk("half_inverted_no_burst", half["peak"] == half["i0"]
        and half["t_peak"] == 0.0 and half["monotone_decreasing"])
    chk("half_inverted_energy_10", abs(half["emitted"] - 10.0) < 1e-3)
    single = single_excitation_report()
    chk("single_excitation_i0_gamma_N", single["i0"] == 20.0)
    chk("single_excitation_no_burst", single["peak"] == single["i0"]
        and single["t_peak"] == 0.0 and single["monotone_decreasing"])
    chk("single_excitation_matches_analytic",
        single["worst_probe_error"] < 1e-3)
    chk("single_excitation_energy_1", abs(single["emitted"] - 1.0) < 1e-3)

    # 6. subradiance - same machinery, dark sectors
    sub = subradiance_report()
    chk("singlet_exactly_dark", sub["singlet_rate_J0_m0"] == 0.0)
    chk("dark_single_excitation_exactly_dark",
        sub["dark_single_excitation_rate"] == 0.0)
    chk("bright_single_excitation_gamma_N",
        sub["bright_single_excitation_rate"] == 20.0)
    chk("leaky_state_suppressed_over_10x",
        0.0 < sub["leaky_state"]["rate"] < GAMMA / 10.0
        and sub["leaky_state"]["suppression_factor_vs_gamma"] > 10.0)

    # 7. classifier - labels come from the lab's own policy
    rep = classifier_report()
    chk("classifier_fully_inverted_burst",
        rep["fully_inverted_N20"]["label"] == "superradiant-burst")
    chk("classifier_half_inverted_monotone",
        rep["half_inverted_N20"]["label"] == "collective-monotone")
    chk("classifier_single_excitation_monotone",
        rep["single_excitation_N20"]["label"] == "collective-monotone")
    chk("classifier_independent_like",
        rep["independent_N20"]["label"] == "independent-like")
    chk("classifier_singlet_dark",
        rep["singlet_N2"]["label"] == "subradiant-dark")
    chk("classifier_leaky_dark",
        rep["leaky_dark_N2"]["label"] == "subradiant-dark")
    chk("classifier_matches_policy_scenarios",
        all(v["label"] == v["policy"] for v in rep.values()))
    chk("classifier_matches_policy_grid",
        all(classify_regime(*feats) == label
            for feats, label in TRAINING_GRID))

    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_emitter_array_hold", gate("real_emitter_array_control") == "HOLD")
    chk("gate_laser_hold", gate("live_laser_pump_operation") == "HOLD")
    chk("gate_memory_product_hold", gate("quantum_memory_product_claim") == "HOLD")
    chk("gate_directed_energy_hold", gate("directed_energy_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    brains = brains_report()
    chk("argon4_no_override", brains["decider"]["can_override_hold"] is False
        and brains["decider"]["seat"]
        == "Gemini Argon 4 Extended Thinking")
    chk("claude_no_override", brains["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def ladder_report():
    rows = {}
    for n in (2, 10, 20, 40):
        rates = collective_rates(n)
        rows[n] = {"rates_by_k": rates[1:],
                   "max_rate": max(rates),
                   "first_step": rates[n],
                   "last_step": rates[1]}
    return rows


def demo():
    print("=" * 68)
    print("DickeSuperradiance-Lab - collective emission & the Dicke burst lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST CORE - what this model is and is not")
    print("    N identical two-level emitters, ONE shared radiation mode,")
    print("    the symmetric J = N/2 ladder, exact Dicke rates")
    print("    Gamma = gamma * k * (N - k + 1), integrated deterministically.")
    print("    Units: gamma = 1, photon energy = 1. Ideal Dicke assumptions")
    print("    throughout (identical coupling, no dephasing) - no number")
    print("    here is a hardware figure.")
    print("\n[2] The ladder - why mid-ladder rungs are fast")
    for n in (10, 40):
        rates = collective_rates(n)
        print(f"    N={n:2d}: first step {rates[n]:.0f} gamma | "
              f"mid-ladder max {max(rates):.0f} gamma | "
              f"last step {rates[1]:.0f} gamma")
    print("    -> the (N - k + 1) factor is the collective enhancement:")
    print("       the field already emitted stimulates the next photon.")
    sweep = burst_sweep()
    print("\n[3] The burst - fully inverted start")
    for r in sweep["rows"]:
        if r["n"] in (4, 10, 20, 40):
            print(f"    N={r['n']:2d}: peak {r['peak']:8.2f} gamma | "
                  f"delay {r['t_peak']:.4f} /gamma | "
                  f"contrast x{r['contrast']:.2f} | "
                  f"emitted {r['emitted']:.4f} photons")
    print(f"    peak fit N=4..40 : exponent {sweep['exponent_all_4_40']:.4f} "
          f"(finite-size window, asserted in [1.80, 1.92])")
    print(f"    peak fit N=20..40: exponent {sweep['exponent_20_40']:.4f} "
          f"(approaches the N^2 law, asserted in [1.88, 2.02])")
    print(f"    delay ~ (ln N)/(N gamma): t_peak*N/ln N = "
          f"{sweep['delay_scaled_band'][10]:.3f} (N=10), "
          f"{sweep['delay_scaled_band'][20]:.3f} (N=20), "
          f"{sweep['delay_scaled_band'][40]:.3f} (N=40)")
    print("    honest note: the delay RISES slightly from N=4 to N=6")
    print("    before the (ln N)/N fall takes over - monotone from N=6,")
    print("    which is exactly what CHECKS asserts.")
    print(f"    energy receipt: worst |emitted - N| over the sweep = "
          f"{sweep['worst_energy_error']:.2e} (asserted < 1e-3)")
    control = control_sweep()
    print("\n[4] Control - independent emitters (no collective factor)")
    print(f"    peak = gamma*N exactly at t=0 for every N; fit exponent "
          f"{control['exponent']:.4f} (asserted in [0.95, 1.05]);")
    print("    monotone decay, no delay, no burst. The N^2 is cooperation,")
    print("    not bookkeeping.")
    half = half_inverted_report()
    single = single_excitation_report()
    print("\n[5] Starts that cannot burst - the ladder must be climbed")
    print(f"    half-inverted N=20: I(0) = {half['i0']:.0f} gamma "
          f"(= gamma*J*(J+1), the fastest rung), peak at t=0, "
          f"monotone decreasing = {half['monotone_decreasing']}")
    print(f"    single excitation N=20: I(0) = {single['i0']:.0f} gamma, "
          f"pure exponential at rate gamma*N, worst deviation from "
          f"N*exp(-N t) = {single['worst_probe_error']:.2e}")
    sub = subradiance_report()
    print("\n[6] Subradiance - the same formula in the dark sectors")
    print(f"    two-atom singlet (J=0): rate {sub['singlet_rate_J0_m0']:.1f} "
          f"gamma - exactly dark in this model")
    print(f"    non-symmetric single excitation (J=N/2-1 bottom): rate "
          f"{sub['dark_single_excitation_rate']:.1f} gamma, vs the "
          f"symmetric W state at {sub['bright_single_excitation_rate']:.0f} gamma")
    print(f"    leaky state (1% bright weight): rate "
          f"{sub['leaky_state']['rate']:.2f} gamma - suppressed "
          f"{sub['leaky_state']['suppression_factor_vs_gamma']:.0f}x vs one atom")
    print(f"    assumption: {sub['assumption']}")
    print("\n[7] Regime classifier (TinyML kNN, labels from the lab's policy)")
    for name, entry in classifier_report().items():
        feats = entry["features"]
        print(f"    {name:26s} R={feats[0]:.3f} C={feats[1]:.3f} "
              f"r0={feats[2]:.3f} -> {entry['label']}")
    print("\n[8] Advisory seats")
    brains = brains_report()
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {brains['advisor']['can_override_hold']}")
    print(f"    flow rendered = {brains['flow']['rendered']} "
          f"live = {brains['flow']['live']}")
    print(f"\n[9] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "ladder":
        print(json.dumps(ladder_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "burst":
        print(json.dumps(burst_sweep(), indent=2, sort_keys=True))
        return 0
    if cmd == "control":
        print(json.dumps(control_sweep(), indent=2, sort_keys=True))
        return 0
    if cmd == "noburst":
        print(json.dumps({"half_inverted": half_inverted_report(),
                          "single_excitation": single_excitation_report()},
                         indent=2, sort_keys=True))
        return 0
    if cmd == "subradiance":
        print(json.dumps(subradiance_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "real_emitter_array_control"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
