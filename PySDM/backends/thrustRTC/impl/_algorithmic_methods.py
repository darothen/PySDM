"""
Created at 10.12.2019
"""

from functools import reduce
from PySDM.backends.thrustRTC.conf import NICE_THRUST_FLAGS
from PySDM.backends.thrustRTC.nice_thrust import nice_thrust
from ..conf import trtc
from .precision_resolver import PrecisionResolver


class AlgorithmicMethods:

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def adaptive_sdm_end(dt_left, cell_start):
        i = trtc.Find(dt_left.data, PrecisionResolver.get_floating_point(0))
        if i is None:
            i = len(dt_left)
        return cell_start[i]

    __adaptive_sdm_gamma_body_1 = trtc.For(['dt_todo', 'dt_left', 'dt_max'], 'cid', '''
            dt_todo[cid] = min(dt_left[cid], dt_max);
    ''')

    __adaptive_sdm_gamma_body_2 = trtc.For(['gamma', 'idx', 'n', 'cell_id', 'dt', 'is_first_in_pair', 'dt_todo'], 'i', '''
            if (gamma[i] == 0) {
                return;
            }
            auto offset = 1 - is_first_in_pair[2 * i];
            auto j = idx[2 * i + offset];
            auto k = idx[2 * i + 1 + offset];
            auto prop = (int64_t)(n[j] / n[k]);
            auto dt_optimal = dt * prop / gamma[i];
            auto cid = cell_id[j];
            static_assert(sizeof(dt_todo[0]) == sizeof(unsigned int), "");
            atomicMin((unsigned int*)&dt_todo[cid], __float_as_uint(dt_optimal));
    ''')

    __adaptive_sdm_gamma_body_3 = trtc.For(['gamma', 'idx', 'cell_id', 'dt', 'is_first_in_pair', 'dt_todo'], 'i', '''
            if (gamma[i] == 0) {
                return;
            }
            auto offset = 1 - is_first_in_pair[2 * i];
            auto j = idx[2 * i + offset];
            gamma[i] *= dt_todo[cell_id[j]] / dt;
    ''')

    __adaptive_sdm_gamma_body_4 = trtc.For(['dt_left', 'dt_todo', 'stats_n_substep'], 'cid', '''
            dt_left[cid] -= dt_todo[cid];
            if (dt_todo[cid] > 0) {
                stats_n_substep[cid] += 1;
            }
    ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def adaptive_sdm_gamma(gamma, n, cell_id, dt_left, dt, dt_range, is_first_in_pair, stats_n_substep, stats_dt_min):
        # TODO #406 implement stats_dt_min
        dt_todo = trtc.device_vector('float', len(dt_left))
        d_dt_max = PrecisionResolver.get_floating_point(dt_range[1])
        d_dt = PrecisionResolver.get_floating_point(dt)

        AlgorithmicMethods.__adaptive_sdm_gamma_body_1.launch_n(len(dt_left), (dt_todo, dt_left.data, d_dt_max))
        AlgorithmicMethods.__adaptive_sdm_gamma_body_2.launch_n(
            len(n) // 2,
            (gamma.data, n.idx.data, n.data, cell_id.data, d_dt,
             is_first_in_pair.indicator.data, dt_todo))
        AlgorithmicMethods.__adaptive_sdm_gamma_body_3.launch_n(
            len(n) // 2, (gamma.data, n.idx.data, cell_id.data, d_dt, is_first_in_pair.indicator.data, dt_todo))
        AlgorithmicMethods.__adaptive_sdm_gamma_body_4.launch_n(len(dt_left), [dt_left.data, dt_todo, stats_n_substep.data])

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def calculate_displacement(dim, scheme, displacement, courant, cell_origin, position_in_cell):
        dim = trtc.DVInt64(dim)
        n_sd = trtc.DVInt64(position_in_cell.shape[1])
        courant_length = trtc.DVInt64(courant.shape[0])
        loop = trtc.For(
            ['dim', 'n_sd', 'displacement', 'courant', 'courant_length', 'cell_origin', 'position_in_cell'], "i",
            f'''
            // Arakawa-C grid
            auto _l_0 = cell_origin[i + 0];
            auto _l_1 = cell_origin[i + n_sd];
            auto _l = _l_0 + _l_1 * courant_length;
            auto _r_0 = cell_origin[i + 0] + 1 * (dim == 0);
            auto _r_1 = cell_origin[i + n_sd] + 1 * (dim == 1);
            auto _r = _r_0 + _r_1 * courant_length;
            auto omega = position_in_cell[i + n_sd * dim];
            auto c_r = courant[_r];
            auto c_l = courant[_l];
            displacement[i, dim] = {scheme(None, None, None)}
            ''')
        loop.launch_n(
            displacement.shape[1],
            [dim, n_sd, displacement.data, courant.data, courant_length, cell_origin.data, position_in_cell.data])

    __cell_id_body = trtc.For(['cell_id', 'cell_origin', 'strides', 'n_dims', 'size'], "i", '''
        cell_id[i] = 0;
        for (auto j = 0; j < n_dims; j += 1) {
            cell_id[i] += cell_origin[size * j + i] * strides[j];
        }
        ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def cell_id(cell_id, cell_origin, strides):
        assert cell_origin.shape[0] == strides.shape[1]
        assert cell_id.shape[0] == cell_origin.shape[1]
        assert strides.shape[0] == 1
        n_dims = trtc.DVInt64(cell_origin.shape[0])
        size = trtc.DVInt64(cell_origin.shape[1])
        AlgorithmicMethods.__cell_id_body.launch_n(len(cell_id), [cell_id.data, cell_origin.data, strides.data, n_dims, size])

    __distance_pair_body = trtc.For(['data_out', 'data_in', 'is_first_in_pair'], "i", '''
        if (is_first_in_pair[i]) {
            data_out[(int64_t)(i/2)] = abs(data_in[i] - data_in[i + 1]);
        }
        ''')

    __coalescence_body = trtc.For(
        ['n', 'idx', 'n_sd', 'attributes', 'n_attr', 'gamma', 'healthy'], "i", '''
        if (gamma[i] == 0) {
            return;
        }
        auto j = idx[2 * i];
        auto k = idx[2 * i + 1];
            
        auto new_n = n[j] - gamma[i] * n[k];
        if (new_n > 0) {
            n[j] = new_n;
            for (auto attr = 0; attr < n_attr * n_sd; attr+=n_sd) {
                attributes[attr + k] += gamma[i] * attributes[attr + j];
            }
        }
        else {  // new_n == 0
            n[j] = (int64_t)(n[k] / 2);
            n[k] = n[k] - n[j];
            for (auto attr = 0; attr < n_attr * n_sd; attr+=n_sd) {
                attributes[attr + j] = gamma[i] * attributes[attr + j] + attributes[attr + k];
                attributes[attr + k] = attributes[attr + j];
            }
        }
        if (n[k] == 0 || n[j] == 0) {
            healthy[0] = 0;
        }
        ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def coalescence(n, idx, length, attributes, gamma, healthy, is_first_in_pair):
        n_sd = trtc.DVInt64(attributes.shape[1])
        n_attr = trtc.DVInt64(attributes.shape[0])
        AlgorithmicMethods.__coalescence_body.launch_n(length // 2,
                                                       [n.data, idx.data, n_sd,
                                                        attributes.data,
                                                        n_attr, gamma.data, healthy.data])

    __compute_gamma_body = trtc.For(['gamma', 'rand', "idx", "n", "cell_id",
                                     "collision_rate_deficit", "collision_rate"], "i", '''
        gamma[i] = ceil(gamma[i] - rand[i]);
        
        if (gamma[i] == 0) {
            return;
        }

        auto j = idx[2 * i];
        auto k = idx[2 * i + 1];

        auto prop = (int64_t)(n[j] / n[k]);
        if (prop > gamma[i]) {
            prop = gamma[i];
        }
        
        gamma[i] = prop;
        ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def compute_gamma(gamma, rand, n, cell_id,
                      collision_rate_deficit, collision_rate, is_first_in_pair):
        AlgorithmicMethods.__compute_gamma_body.launch_n(
            len(n) // 2,
            [gamma.data, rand.data, n.idx.data, n.data, cell_id.data,
             collision_rate_deficit.data, collision_rate.data])

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def condensation(
            solver,
            n_cell, cell_start_arg,
            v, particle_temperatures, n, vdry, idx, rhod, thd, qv, dv, prhod, pthd, pqv, kappa,
            rtol_x, rtol_thd, dt, substeps, cell_order
    ):
        raise NotImplementedError()

    __flag_precipitated_body = trtc.For(['idx', 'n_sd', 'n_dims', 'healthy', 'cell_origin', 'position_in_cell',
                                         'volume', 'n'], "i", '''
        if (cell_origin[n_sd * (n_dims-1) + idx[i]] + position_in_cell[n_sd * (n_dims-1) + idx[i]] < 0) {
            idx[i] = n_sd;
            healthy[0] = 0;
        }
        ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def flag_precipitated(cell_origin, position_in_cell, volume, n, idx, length, healthy):
        n_sd = trtc.DVInt64(cell_origin.shape[1])
        n_dims = trtc.DVInt64(len(cell_origin.shape))
        AlgorithmicMethods.__flag_precipitated_body.launch_n(
            length, [idx.data, n_sd, n_dims, healthy.data, cell_origin.data, position_in_cell.data,
                     volume.data, n.data])
        return 0  # TODO #332

    __linear_collection_efficiency_body = trtc.For(
        ['A', 'B', 'D1', 'D2', 'E1', 'E2', 'F1', 'F2', 'G1', 'G2', 'G3', 'Mf', 'Mg', 'output', 'radii',
         'is_first_in_pair', 'idx', 'unit'], "i", '''
        if (is_first_in_pair[i]) {
            real_type r = 0;
            real_type r_s = 0;
            if (radii[idx[i]] > radii[idx[i + 1]]) {
                r = radii[idx[i]] / unit;
                r_s = radii[idx[i + 1]] / unit;
            }
            else {
                r = radii[idx[i + 1]] / unit;
                r_s = radii[idx[i]] / unit;
            }
            real_type p = r_s / r;
            if (p != 0 && p != 1) {
                real_type G = pow((G1 / r), Mg) + G2 + G3 * r;
                real_type Gp = pow((1 - p), G);
                if (Gp != 0) {
                    real_type D = D1 / pow(r, D2);
                    real_type E = E1 / pow(r, E2);
                    real_type F = pow((F1 / r), Mf) + F2;
                    output[int(i / 2)] = A + B * p + D / pow(p, F) + E / Gp;
                    if (output[int(i / 2)] < 0) {
                        output[int(i / 2)] = 0;
                    }
                }
            }
        }
    '''.replace("real_type", PrecisionResolver.get_C_type()))

    @staticmethod
    def linear_collection_efficiency(params, output, radii, is_first_in_pair, unit):
        A, B, D1, D2, E1, E2, F1, F2, G1, G2, G3, Mf, Mg = params
        dA = PrecisionResolver.get_floating_point(A)
        dB = PrecisionResolver.get_floating_point(B)
        dD1 = PrecisionResolver.get_floating_point(D1)
        dD2 = PrecisionResolver.get_floating_point(D2)
        dE1 = PrecisionResolver.get_floating_point(E1)
        dE2 = PrecisionResolver.get_floating_point(E2)
        dF1 = PrecisionResolver.get_floating_point(F1)
        dF2 = PrecisionResolver.get_floating_point(F2)
        dG1 = PrecisionResolver.get_floating_point(G1)
        dG2 = PrecisionResolver.get_floating_point(G2)
        dG3 = PrecisionResolver.get_floating_point(G3)
        dMf = PrecisionResolver.get_floating_point(Mf)
        dMg = PrecisionResolver.get_floating_point(Mg)
        dunit = PrecisionResolver.get_floating_point(unit)
        trtc.Fill(output.data, trtc.DVDouble(0))
        AlgorithmicMethods.__linear_collection_efficiency_body.launch_n(
            len(is_first_in_pair) - 1,
            [dA, dB, dD1, dD2, dE1, dE2, dF1, dF2, dG1, dG2, dG3, dMf, dMg,
             output.data, radii.data, is_first_in_pair.indicator.data, radii.idx.data, dunit])

    __interpolation_body = trtc.For(['output', 'radius', 'factor', 'a', 'b'], 'i', '''
        auto r_id = (int64_t)(factor * radius[i]);
        auto r_rest = (factor * radius[i] - r_id) / factor;
        output[i] = a[r_id] + r_rest * b[r_id];
    ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def interpolation(output, radius, factor, b, c):
        factor_device = trtc.DVInt64(factor)
        AlgorithmicMethods.__interpolation_body.launch_n(len(radius),
                                                         [output.data, radius.data, factor_device, b.data, c.data])

    @staticmethod
    def make_cell_caretaker(idx, cell_start, scheme=None):
        return AlgorithmicMethods._sort_by_cell_id_and_update_cell_start

    __loop_reset = trtc.For(['vector_to_clean'], "i",
                            '''
        vector_to_clean[i] = 0;
    ''')

    __moments_body_0 = trtc.For(
        ['idx', 'min_x', 'attr_data', 'x_attr', 'max_x', 'moment_0', 'cell_id', 'n',
         'n_ranks', 'moments', 'ranks',
         'n_sd', 'n_cell'],
        "fake_i",
        '''
        auto i = idx[fake_i];
        if (min_x < x_attr[i] && x_attr[i] < max_x) {
            atomicAdd((unsigned long long int*)&moment_0[cell_id[i]], (unsigned long long int)n[i]);
            for (auto k = 0; k < n_ranks; k+=1) {
                atomicAdd((real_type*) &moments[n_cell * k + cell_id[i]], n[i] * pow((real_type)(attr_data[i]), (real_type)(ranks[k])));
            }
        }
    '''.replace("real_type", PrecisionResolver.get_C_type()))

    __moments_body_1 = trtc.For(['n_ranks', 'moments', 'moment_0', 'n_cell'], "c_id",
                                '''
        for (auto k = 0; k < n_ranks; k+=1) {
            if (moment_0[c_id] == 0) {
                moments[n_cell * k  + c_id] = 0;
            } 
            else {
                moments[n_cell * k + c_id] = moments[n_cell * k + c_id] / moment_0[c_id];
            }
        }
    ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def moments(moment_0, moments, n, attr_data, cell_id, idx, length, ranks,
                min_x, max_x, x_attr):
        n_cell = trtc.DVInt64(moments.shape[1])
        n_sd = trtc.DVInt64(moments.shape[0])
        n_ranks = trtc.DVInt64(ranks.shape[0])

        AlgorithmicMethods.__loop_reset.launch_n(moment_0.shape[0], [moment_0.data])
        AlgorithmicMethods.__loop_reset.launch_n(reduce(lambda x, y: x * y, moments.shape), [moments.data])

        AlgorithmicMethods.__moments_body_0.launch_n(length,
                                                     [idx.data,
                                                      PrecisionResolver.get_floating_point(min_x),
                                                      attr_data.data,
                                                      x_attr.data,
                                                      PrecisionResolver.get_floating_point(max_x),
                                                      moment_0.data,
                                                      cell_id.data,
                                                      n.data,
                                                      n_ranks,
                                                      moments.data,
                                                      ranks.data,
                                                      n_sd,
                                                      n_cell
                                                      ]
                                                     )

        AlgorithmicMethods.__moments_body_1.launch_n(
            moment_0.shape[0], [n_ranks, moments.data, moment_0.data, n_cell])

    __normalize_body_0 = trtc.For(['cell_start', 'norm_factor', 'dt_div_dv'], "i", '''
        auto sd_num = cell_start[i + 1] - cell_start[i];
        if (sd_num < 2) {
            norm_factor[i] = 0;
        }
        else {
            auto half_sd_num = sd_num / 2;
            norm_factor[i] = dt_div_dv * sd_num * (sd_num - 1) / 2 / half_sd_num;
        }
        ''')

    __normalize_body_1 = trtc.For(['prob', 'cell_id', 'norm_factor'], "i", '''
        prob[i] *= norm_factor[cell_id[i]];
        ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def normalize(prob, cell_id, cell_idx, cell_start, norm_factor, dt, dv):
        n_cell = cell_start.shape[0] - 1
        device_dt_div_dv = PrecisionResolver.get_floating_point(dt / dv)
        AlgorithmicMethods.__normalize_body_0.launch_n(n_cell, [cell_start.data, norm_factor.data, device_dt_div_dv])
        AlgorithmicMethods.__normalize_body_1.launch_n(prob.shape[0], [prob.data, cell_id.data, norm_factor.data])

    __remove_zero_n_or_flagged_body = trtc.For(['data', 'idx', 'n_sd'], "i", '''
        if (idx[i] < n_sd && data[idx[i]] == 0) {
            idx[i] = n_sd;
        }
        ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def remove_zero_n_or_flagged(data, idx, length) -> int:
        n_sd = trtc.DVInt64(idx.size())

        # Warning: (potential bug source): reading from outside of array
        AlgorithmicMethods.__remove_zero_n_or_flagged_body.launch_n(length, [data, idx, n_sd])

        trtc.Sort(idx)

        result = idx.size() - trtc.Count(idx, n_sd)
        return result

    ___sort_by_cell_id_and_update_cell_start_body = trtc.For(['cell_id', 'cell_start', 'idx'], "i", '''
        if (i == 0) {
            cell_start[cell_id[idx[0]]] = 0;
        } 
        else {
            auto cell_id_curr = cell_id[idx[i]];
            auto cell_id_next = cell_id[idx[i + 1]];
            auto diff = (cell_id_next - cell_id_curr);
            for (auto j = 1; j < diff + 1; j += 1) {
                cell_start[cell_id_curr + j] = idx[i + 1];
            }
        }
        ''')

    @staticmethod
    @nice_thrust(**NICE_THRUST_FLAGS)
    def _sort_by_cell_id_and_update_cell_start(cell_id, cell_idx, cell_start, idx):
        # TODO #330
        n_sd = cell_id.shape[0]
        trtc.Fill(cell_start.data, trtc.DVInt64(n_sd))
        AlgorithmicMethods.___sort_by_cell_id_and_update_cell_start_body.launch_n(len(idx) - 1,
                                                                                  [cell_id.data, cell_start.data,
                                                                                   idx.data])
        return idx
