"""
Crated at 2019
"""

import numpy as np
from ..backends.numba.toms748 import toms748_solve
from ..physics import formulae
from ..backends.numba.conf import JIT_FLAGS
from numba import prange, njit

default_rtol = 1e-5


def r_wet_init(r_dry: np.ndarray, environment, cell_id: np.ndarray, kappa, rtol=default_rtol):
    T = environment["T"].to_ndarray()
    p = environment["p"].to_ndarray()
    RH = environment["RH"].to_ndarray()
    return r_wet_init_impl(r_dry, T, p, RH, cell_id, kappa, rtol)


@njit(**{**JIT_FLAGS, **{'parallel': False, 'fastmath': False}})
def r_wet_init_impl(r_dry: np.ndarray, T, p, RH, cell_id: np.ndarray, kappa, rtol, RH_range=(0, 1)):
    r_wet = np.empty_like(r_dry)

    for i in prange(len(r_dry)):
        r_d = r_dry[i]
        cid = cell_id[i]
        # root-finding initial guess
        a = r_d
        b = formulae.r_cr(kappa, r_d, T[cid])
        # minimisation
        args = (
            T[cid],
            p[cid],
            np.maximum(RH_range[0], np.minimum(RH_range[1], RH[cid])),
            kappa,
            r_d
        )
        fa = formulae.dr_dt_MM(a, *args)
        fb = formulae.dr_dt_MM(b, *args)
        max_iters = 64
        r_wet[i], iters_done = toms748_solve(formulae.dr_dt_MM, args, a, b, fa, fb, rtol=rtol, max_iter=max_iters)
        assert iters_done != max_iters
    return r_wet
