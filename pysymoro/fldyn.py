# -*- coding: utf-8 -*-


import sympy
from sympy import Matrix

from pysymoro.geometry import compute_screw_transform
from pysymoro.geometry import compute_rot_trans, Transform
from pysymoro.kinematics import compute_vel_acc
from pysymoro.kinematics import compute_omega
from symoroutils import symbolmgr
from symoroutils import tools
from symoroutils.paramsinit import ParamsInit


def inertia_spatial(inertia, ms_tensor, mass):
    """
    Compute spatial inertia matrix (internal function).
    """
    return Matrix([
        (mass * sympy.eye(3)).row_join(tools.skew(ms_tensor).transpose()),
        tools.skew(ms_tensor).row_join(inertia)
    ])


def compute_beta(robo, symo, j, w, beta):
    """
    Compute beta wrench which is a combination of coriolis forces,
    centrifugal forces and external forces (internal function).

    Notes
    =====
    beta is the output parameter
    """
    expr1 = robo.J[j] * w[j]
    expr1 = symo.mat_replace(expr1, 'JW', j)
    expr2 = tools.skew(w[j]) * expr1
    expr2 = symo.mat_replace(expr2, 'KW', j)
    expr3 = tools.skew(w[j]) * robo.MS[j]
    expr4 = tools.skew(w[j]) * expr3
    expr4 = symo.mat_replace(expr4, 'SW', j)
    expr5 = -robo.Nex[j] - expr2
    expr6 = -robo.Fex[j] - expr4
    beta[j] = Matrix([expr6, expr5])
    beta[j] = symo.mat_replace(beta[j], 'BETA', j)


def compute_gamma(robo, symo, j, antRj, antPj, w, wi, gamma):
    """
    Compute gyroscopic acceleration (internal function).

    Notes
    =====
    gamma is the output parameter
    """
    expr1 = tools.skew(wi[j]) * Matrix([0, 0, robo.qdot[j]])
    expr1 = symo.mat_replace(expr1, 'WQ', j)
    expr2 = (1 - robo.sigma[j]) * expr1
    expr3 = 2 * robo.sigma[j] * expr1
    expr4 = tools.skew(w[robo.ant[j]]) * antPj[j]
    expr5 = tools.skew(w[robo.ant[j]]) * expr4
    expr6 = antRj[j].transpose() * expr5
    expr7 = expr6 + expr3
    expr7 = symo.mat_replace(expr7, 'LW', j)
    gamma[j] = Matrix([expr7, expr2])
    gamma[j] = symo.mat_replace(gamma[j], 'GYACC', j)


def compute_zeta(robo, symo, j, gamma, jaj, zeta, qddot=None):
    """
    Compute relative acceleration (internal function).

    Note:
        zeta is the output parameter
    """
    if qddot == None:
        qddot = robo.qddot
    expr = gamma[j] + (qddot[j] * jaj[j])
    zeta[j] = symo.mat_replace(expr, 'ZETA', j)


def compute_composite_inertia(
    robo, symo, j, antRj, antPj,
    comp_inertia3, comp_ms, comp_mass, composite_inertia
):
    i = robo.ant[j]
    i_ms_j_c = antRj[j] * comp_ms[j]
    i_ms_j_c = symo.mat_replace(i_ms_j_c, 'AS', j)
    expr1 = antRj[j] * comp_inertia3[j]
    expr1 = symo.mat_replace(expr1, 'AJ', j)
    expr2 = expr1 * antRj[j].transpose()
    expr2 = symo.mat_replace(expr2, 'AJA', j)
    expr3 = tools.skew(antPj[j]) * tools.skew(i_ms_j_c)
    expr3 = symo.mat_replace(expr3, 'PAS', j)
    comp_inertia3[i] += expr2 - (expr3 + expr3.transpose()) + \
        (comp_mass[j] * tools.skew(antPj[j]) * \
        tools.skew(antPj[j]).transpose())
    comp_ms[i] = comp_ms[i] + i_ms_j_c + (antPj[j] * comp_mass[j])
    comp_mass[i] = comp_mass[i] + comp_mass[j]
    composite_inertia[i] = inertia_spatial(
        comp_inertia3[i], comp_ms[i], comp_mass[i]
    )


def compute_composite_beta(
    robo, symo, j, jTant, zeta, composite_inertia, composite_beta
):
    """
    Compute composite beta (internal function).

    Note:
        composite_beta is the output parameter
    """
    i = robo.ant[j]
    expr1 = composite_inertia[j] * zeta[j]
    expr1 = symo.mat_replace(expr1, 'IZ', j)
    expr2 = jTant[j].transpose() * expr1
    expr2 = symo.mat_replace(expr2, 'SIZ', j)
    expr3 = jTant[j].transpose() * composite_beta[j]
    expr3 = symo.mat_replace(expr3, 'SBE', j)
    composite_beta[i] = composite_beta[i] + expr3 - expr2


def replace_composite_terms(
    symo, grandJ, beta, j, composite_inertia, composite_beta
):
    """
    Replace composite inertia and beta (internal function).

    Note:
        composite_inertia are composite_beta are the output parameters
    """
    composite_inertia[j] = symo.mat_replace(
        grandJ[j], 'MJE', j, symmet=True
    )
    composite_beta[j] = symo.mat_replace(beta[j], 'VBE', j)


def replace_star_terms(
    symo, grandJ, beta, j, star_inertia, star_beta
):
    """
    Replace star inertia and beta (internal function).

    Note:
        star_inertia are star_beta are the output parameters
    """
    star_inertia[j] = symo.mat_replace(
        grandJ[j], 'MJE', j, symmet=True
    )
    star_beta[j] = symo.mat_replace(beta[j], 'VBE', j)


def compute_composite_terms(
    robo, symo, j, jTant, zeta,
    composite_inertia, composite_beta
):
    """
    Compute composite inertia and beta (internal function).

    Note:
        composite_inertia are composite_beta are the output parameters
    """
    i = robo.ant[j]
    expr1 = jTant[j].transpose() * composite_inertia[j]
    expr1 = symo.mat_replace(expr1, 'GX', j)
    expr2 = expr1 * jTant[j]
    expr2 = symo.mat_replace(expr2, 'TKT', j, symmet=True)
    expr3 = expr1 * zeta[j]
    expr3 = symo.mat_replace(expr3, 'SIZ', j)
    expr4 = jTant[j].transpose() * composite_beta[j]
    expr4 = symo.mat_replace(expr4, 'SBE', j)
    composite_inertia[i] = composite_inertia[i] + expr2
    composite_beta[i] = composite_beta[i] + expr4 - expr3


def compute_hinv(robo, symo, j, jaj, star_inertia, inertia_jaj, h_inv):
    """
    Note:
        h_inv and inertia_jaj are the output parameters
    """
    inertia_jaj[j] = star_inertia[j] * jaj[j]
    inertia_jaj[j] = symo.mat_replace(inertia_jaj, 'JA', j)
    h = jaj[j].dot(inertia_jaj[j])  + robo.IA[j]
    h_inv[j] = 1 / h
    h_inv[j] = symo.mat_replace(h_inv[j], 'JD', j)


def compute_tau(robo, symo, j, jaj, star_beta, tau):
    """
    Note:
        tau is the output parameter
    """
    if robo.sigma[j] == 2:
        tau[j] = 0
    else:
        joint_friction = robo.fric_s(j) + robo.fric_v(j)
        tau[j] = jaj[j].dot(star_beta[j]) + robo.GAM[j] - joint_friction
    tau[j] = symo.replace(tau[j], 'GW', j)


def compute_star_terms(
    robo, symo, j, jaj, jTant, gamma, tau,
    h_inv, jah, star_inertia, star_beta
):
    """
    Note:
        h_inv, jah, star_inertia, star_beta are the output parameters
    """
    i = robo.ant[j]
    inertia_jaj = star_inertia[j] * jaj[j]
    inertia_jaj = symo.mat_replace(inertia_jaj, 'JA', j)
    h_inv[j] = 1 / (jaj[j].dot(inertia_jaj) + robo.IA[j])
    h_inv[j] = symo.mat_replace(h_inv[j], 'JD', j)
    jah[j] = inertia_jaj * h_inv[j]
    jah[j] = symo.mat_replace(jah[j], 'JU', j)
    k_inertia = star_inertia[j] - (jah[j] * inertia_jaj.transpose())
    k_inertia = symo.mat_replace(k_inertia, 'GK', j)
    expr1 = k_inertia * gamma[j]
    expr1 = symo.mat_replace(expr1, 'NG', j)
    expr2 = expr1 + (jah[j] * tau[j])
    expr2 = symo.mat_replace(expr2, 'VS', j)
    alpha = expr2 - star_beta[j]
    alpha = symo.mat_replace(alpha, 'AP', j)
    expr3 = jTant[j].transpose() * k_inertia
    expr3 = symo.mat_replace(expr3, 'GX', j)
    expr4 = expr3 * jTant[j]
    expr4 = symo.mat_replace(expr4, 'TKT', j, symmet=True)
    star_inertia[i] = star_inertia[i] + expr4
    star_beta[i] = star_beta[i] - (jTant[j].transpose() * alpha)


def compute_joint_accel(
    robo, symo, j, jaj, jTant, h_inv, jah, gamma,
    tau, grandVp, star_beta, star_inertia, qddot
):
    """
    Compute joint acceleration (internal function)

    Note:
        qddot is the output parameter
    """
    i = robo.ant[j]
    expr1 = (jTant[j] * grandVp[i]) + gamma[j]
    expr1 = symo.mat_replace(expr1, 'VR', j)
    expr2 = jah[j].dot(expr1)
    expr2 = symo.replace(expr2, 'GU', j)
    if robo.sigma[j] == 2:
        qddot[j] = 0
    else:
        qddot[j] = (h_inv[j] * tau[j]) - expr2
    qddot[j] = symo.replace(qddot[j], str(robo.qddot[j]), forced=True)


def compute_link_accel(robo, symo, j, jTant, zeta, grandVp):
    """
    Compute link acceleration (internal function).

    Note:
        grandVp is the output parameter
    """
    i = robo.ant[j]
    grandVp[j] = (jTant[j] * grandVp[i]) + zeta[j]
    grandVp[j][:3, 0] = symo.mat_replace(grandVp[j][:3, 0], 'VP', j)
    grandVp[j][3:, 0] = symo.mat_replace(grandVp[j][3:, 0], 'WP', j)


def compute_base_accel(robo, symo, star_inertia, star_beta, grandVp):
    """
    Compute base acceleration (internal function).

    Note:
        grandVp is the output parameter
    """
    if robo.is_floating:
        grandVp[0] = star_inertia[0].inv() * star_beta[0]
    else:
        grandVp[0] = Matrix([robo.vdot0 - robo.G, robo.w0])
    grandVp[0][:3, 0] = symo.mat_replace(grandVp[0][:3, 0], 'VP', 0)
    grandVp[0][3:, 0] = symo.mat_replace(grandVp[0][3:, 0], 'WP', 0)


def compute_base_accel_composite(
    robo, symo, composite_inertia, composite_beta, grandVp
):
    """
    Compute base acceleration when using composite inertia matrix
    (internal function).

    Note:
        grandVp is the output parameter
    """
    if robo.is_floating:
        grandVp[0] = composite_inertia[0].inv() * composite_beta[0]
    else:
        grandVp[0] = Matrix([robo.vdot0 - robo.G, robo.w0])
    grandVp[0][:3, 0] = symo.mat_replace(grandVp[0][:3, 0], 'VP', 0)
    grandVp[0][3:, 0] = symo.mat_replace(grandVp[0][3:, 0], 'WP', 0)


def compute_reaction_wrench(
    robo, symo, j, grandVp, inertia, beta_wrench, react_wrench
):
    """
    Compute reaction wrench (internal function).

    Note:
        react_wrench is the output parameter
    """
    expr = inertia[j] * grandVp[j]
    expr = symo.mat_replace(expr, 'DY', j)
    wrench = expr - beta_wrench[j]
    react_wrench[j][:3, 0] = symo.mat_replace(wrench[:3, 0], 'E', j)
    react_wrench[j][3:, 0] = symo.mat_replace(wrench[3:, 0], 'N', j)


def compute_torque(robo, symo, j, jaj, react_wrench, torque):
    """
    Compute torque (internal function).

    Note:
        torque is the output parameter.
    """
    symbl_name = 'GAM' + str(j)
    if robo.sigma[j] == 2:
        tau_total = 0
    else:
        tau = react_wrench[j].transpose() * jaj[j]
        fric_rotor = robo.fric_s(j) + robo.fric_v(j) + robo.tau_ia(j)
        tau_total = tau[0, 0] + fric_rotor
    torque[j] = symo.replace(tau_total, symbl_name, forced=True)


def composite_newton_euler(robo, symo):
    # antecedent angular velocity, projected into jth frame
    # j^omega_i
    wi = ParamsInit.init_vec(robo)
    # j^omega_j
    w = ParamsInit.init_w(robo)
    # j^a_j -- joint axis in screw form
    jaj = ParamsInit.init_vec(robo, 6)
    # Twist transform list of Matrices 6x6
    grandJ = ParamsInit.init_mat(robo, 6)
    jTant = ParamsInit.init_mat(robo, 6)
    gamma = ParamsInit.init_vec(robo, 6)
    beta = ParamsInit.init_vec(robo, 6)
    zeta = ParamsInit.init_vec(robo, 6)
    composite_inertia = ParamsInit.init_mat(robo, 6)
    composite_beta = ParamsInit.init_vec(robo, 6)
    comp_inertia3, comp_ms, comp_mass = ParamsInit.init_jplus(robo)
    grandVp = ParamsInit.init_vec(robo, 6)
    react_wrench = ParamsInit.init_vec(robo, 6)
    torque = ParamsInit.init_scalar(robo)
    # init transformation
    antRj, antPj = compute_rot_trans(robo, symo)
    # first forward recursion
    for j in xrange(1, robo.NL):
        # compute spatial inertia matrix for use in backward recursion
        grandJ[j] = inertia_spatial(robo.J[j], robo.MS[j], robo.M[j])
        # set jaj vector
        if robo.sigma[j] == 0:
            jaj[j] = Matrix([0, 0, 0, 0, 0, 1])
        elif robo.sigma[j] == 1:
            jaj[j] = Matrix([0, 0, 1, 0, 0, 0])
        # compute j^omega_j and j^omega_i
        compute_omega(robo, symo, j, antRj, w, wi)
        # compute j^S_i : screw transformation matrix
        compute_screw_transform(robo, symo, j, antRj, antPj, jTant)
    # first forward recursion (still)
    for j in xrange(1, robo.NL):
        # compute j^gamma_j : gyroscopic acceleration (6x1)
        compute_gamma(robo, symo, j, antRj, antPj, w, wi, gamma)
        # compute j^beta_j : external+coriolis+centrifugal wrench (6x1)
        compute_beta(robo, symo, j, w, beta)
        # compute j^zeta_j : relative acceleration (6x1)
        compute_zeta(robo, symo, j, gamma, jaj, zeta)
    # first backward recursion - initialisation step
    for j in reversed(xrange(0, robo.NL)):
        if j == 0:
            # compute spatial inertia matrix for base
            grandJ[j] = inertia_spatial(robo.J[j], robo.MS[j], robo.M[j])
            # compute 0^beta_0
            compute_beta(robo, symo, j, w, beta)
        replace_composite_terms(
            symo, grandJ, beta, j, composite_inertia, composite_beta
        )
    # second backward recursion - compute composite term
    for j in reversed(xrange(0, robo.NL)):
        if j == 0:
            # compute 0^\dot{V}_0 : base acceleration
            compute_base_accel_composite(
                robo, symo, composite_inertia, composite_beta, grandVp
            )
            continue
        # compute i^I_i^c and i^beta_i^c
        #compute_composite_terms(
        #    robo, symo, j, jTant, zeta,
        #    composite_inertia, composite_beta
        #)
        compute_composite_inertia(
            robo, symo, j, antRj, antPj,
            comp_inertia3, comp_ms, comp_mass, composite_inertia
        )
        compute_composite_beta(
            robo, symo, j, jTant, zeta, composite_inertia, composite_beta
        )
        replace_composite_terms(
            symo, composite_inertia, composite_beta, robo.ant[j],
            composite_inertia, composite_beta
        )
    # second forward recursion
    for j in xrange(1, robo.NL):
        # compute j^Vdot_j : link acceleration
        compute_link_accel(robo, symo, j, jTant, zeta, grandVp)
        # compute j^F_j : reaction wrench
        compute_reaction_wrench(
            robo, symo, j, grandVp,
            composite_inertia, composite_beta, react_wrench
        )
        # compute torque
        compute_torque(robo, symo, j, jaj, react_wrench, torque)


def direct_dynamic_model(robo):
    symo = symbolmgr.SymbolManager()
    symo.file_open(robo, 'flddm')
    title = 'Direct Dynamic Model - NE'
    symo.write_params_table(robo, title, inert=True, dynam=True)
    # antecedent angular velocity, projected into jth frame
    # j^omega_i
    wi = ParamsInit.init_vec(robo)
    # j^omega_j
    w = ParamsInit.init_w(robo)
    # j^a_j -- joint axis in screw form
    jaj = ParamsInit.init_vec(robo, 6)
    # Twist transform list of Matrices 6x6
    grandJ = ParamsInit.init_mat(robo, 6)
    jTant = ParamsInit.init_mat(robo, 6)
    gamma = ParamsInit.init_vec(robo, 6)
    beta = ParamsInit.init_vec(robo, 6)
    zeta = ParamsInit.init_vec(robo, 6)
    h_inv = ParamsInit.init_scalar(robo)
    jah = ParamsInit.init_vec(robo, 6)   # Jj*aj*Hinv_j
    tau = ParamsInit.init_scalar(robo)
    star_inertia = ParamsInit.init_mat(robo, 6)
    star_beta = ParamsInit.init_vec(robo, 6)
    qddot = ParamsInit.init_scalar(robo)
    grandVp = ParamsInit.init_vec(robo, 6)
    react_wrench = ParamsInit.init_vec(robo, 6)
    torque = ParamsInit.init_scalar(robo)
    # init transformation
    antRj, antPj = compute_rot_trans(robo, symo)
    # first forward recursion
    for j in xrange(1, robo.NL):
        # compute spatial inertia matrix for use in backward recursion
        grandJ[j] = inertia_spatial(robo.J[j], robo.MS[j], robo.M[j])
        # set jaj vector
        if robo.sigma[j] == 0:
            jaj[j] = Matrix([0, 0, 0, 0, 0, 1])
        elif robo.sigma[j] == 1:
            jaj[j] = Matrix([0, 0, 1, 0, 0, 0])
        # compute j^omega_j and j^omega_i
        compute_omega(robo, symo, j, antRj, w, wi)
        # compute j^S_i : screw transformation matrix
        compute_screw_transform(robo, symo, j, antRj, antPj, jTant)
    # first forward recursion (still)
    for j in xrange(1, robo.NL):
        # compute j^gamma_j : gyroscopic acceleration (6x1)
        compute_gamma(robo, symo, j, antRj, antPj, w, wi, gamma)
        # compute j^beta_j : external+coriolis+centrifugal wrench (6x1)
        compute_beta(robo, symo, j, w, beta)
    # first backward recursion - initialisation step
    for j in reversed(xrange(0, robo.NL)):
        if j == 0:
            # compute spatial inertia matrix for base
            grandJ[j] = inertia_spatial(robo.J[j], robo.MS[j], robo.M[j])
            # compute 0^beta_0
            compute_beta(robo, symo, j, w, beta)
        replace_star_terms(
            symo, grandJ, beta, j, star_inertia, star_beta
        )
    # second backward recursion - compute star terms
    for j in reversed(xrange(0, robo.NL)):
        if j == 0: continue
        compute_tau(robo, symo, j, jaj, star_beta, tau)
        compute_star_terms(
            robo, symo, j, jaj, jTant, gamma, tau,
            h_inv, jah, star_inertia, star_beta
        )
        replace_star_terms(
            symo, star_inertia, star_beta, robo.ant[j],
            star_inertia, star_beta
        )
    # second forward recursion
    for j in xrange(0, robo.NL):
        if j == 0:
            # compute 0^\dot{V}_0 : base acceleration
            compute_base_accel(
                robo, symo, star_inertia, star_beta, grandVp
            )
            continue
        # compute qddot_j : joint acceleration
        compute_joint_accel(
            robo, symo, j, jaj, jTant, h_inv, jah, gamma,
            tau, grandVp, star_beta, star_inertia, qddot
        )
        # compute j^zeta_j : relative acceleration (6x1)
        compute_zeta(robo, symo, j, gamma, jaj, zeta, qddot)
        # compute j^Vdot_j : link acceleration
        compute_link_accel(robo, symo, j, jTant, zeta, grandVp)
        # compute j^F_j : reaction wrench
        compute_reaction_wrench(
            robo, symo, j, grandVp,
            star_inertia, star_beta, react_wrench
        )
    symo.file_close()
    return symo


