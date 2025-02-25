# pylint: disable=C0103
"""
This script configures V/Hz control for an induction motor. The default values
correspond to a 2.2-kW induction motor.

"""
# %%
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from helpers import Step  # Sequence
from control.im.scalar import ScalarCtrl, Datalogger
from config.mdl_im_2kW import mdl


# %% Define the controller parameters
@dataclass
class CtrlParameters:
    """
    This data class contains parameters for the V/Hz control system.

    """
    T_s: float = 250e-6
    psi_s_nom: float = .95
    k_u: float = 1
    k_w: float = 4
    rate_limit: float = 2*np.pi*120
    R_s: float = 3.7
    R_R: float = 2.1
    L_sgm: float = .021
    L_M: float = .224


# %%
pars = CtrlParameters()
# Open-loop V/Hz control can be obtained by choosing:
# pars.k_u, pars.k_w, pars.R_s, pars.R_R = 0, 0, 0, 0
datalog = Datalogger()
ctrl = ScalarCtrl(pars, datalog)

# %% Profiles
# Speed reference
mdl.speed_ref = Step(.4, 2*np.pi*50)
# External load torque
mdl.mech.T_L_ext = Step(1, 14.6)
# Stop time of the simulation
mdl.t_stop = 1.6
# Speed reference
# times = np.array([0, .5, 1, 1.5, 2, 2.5,  3, 3.5, 4])
# values = np.array([0,  0, 1,   1, 0,  -1, -1,   0, 0])*2*np.pi*50
# mdl.speed_ref = Sequence(times, values)
# External load torque
# times = np.array([0, .5, .5, 3.5, 3.5, 4])
# values = np.array([0, 0, 1, 1, 0, 0])*14.6
# mdl.mech.T_L_ext = Sequence(times, values)
# Stop time of the simulation
# mdl.t_stop = mdl.speed_ref.times[-1]

# %% Print the control system data
print('\nScalar control')
print('--------------')
print('Sampling period:')
print('    T_s={}'.format(pars.T_s))
print(ctrl)

# %% Print the profiles
print('\nProfiles')
print('--------')
print('Speed reference:')
with np.printoptions(precision=1, suppress=True):
    print('    {}'.format(mdl.speed_ref))
print('External load torque:')
with np.printoptions(precision=1, suppress=True):
    print('    {}'.format(mdl.mech.T_L_ext))
