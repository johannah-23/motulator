# pylint: disable=C0103
"""
This module contains vector control for PMSM drives.

"""

# %%
import numpy as np
import matplotlib.pyplot as plt
from cycler import cycler
from helpers import abc2complex
from control.common import PWM


# %%
class VectorCtrl:
    """
    This class interconnects the subsystems of the PMSM control system and
    provides the interface to the solver.

    """

    def __init__(self, pars, speed_ctrl, current_ref, current_ctrl, datalog):
        """
        Instantiate the classes.

        """
        self.p = pars.p
        self.current_ctrl = current_ctrl
        self.speed_ctrl = speed_ctrl
        self.current_ref = current_ref
        self.pwm = PWM(pars)
        self.datalog = datalog

    def __call__(self, w_m_ref, w_M, theta_M, i_abc, u_dc):
        """
        Main control loop.

        Parameters
        ----------
        w_m_ref : float
            Rotor speed reference (in electrical rad/s).
        w_M : float
            Rotor speed (in mechanical rad/s).
        theta_M : float
            Rotor angle (in mechanical rad).
        i_s_abc : ndarray, shape (3,)
            Phase currents.
        u_dc : float
            DC-bus voltage.

        Returns
        -------
        d_abc_ref : ndarray, shape (3,)
            Duty ratio references.
        T_s : float
            Sampling period.

        """
        # Get the states
        u = self.pwm.realized_voltage
        w_m = self.p*w_M
        theta_m = np.mod(self.p*theta_M, 2*np.pi)

        # Space vector and coordinate transformation
        i = np.exp(-1j*theta_m)*abc2complex(i_abc)

        # Outputs
        T_M_ref, T_L = self.speed_ctrl.output(w_m_ref/self.p, w_M)
        i_ref, T_M = self.current_ref.output(T_M_ref)
        u_ref, e = self.current_ctrl.output(i_ref, i)
        d_abc_ref, u_ref_lim = self.pwm.output(u_ref, u_dc, theta_m, w_m)

        # Update all the states
        self.speed_ctrl.update(T_M, T_L)
        self.current_ref.update(T_M, u_ref, u_dc)
        self.current_ctrl.update(e, u_ref, u_ref_lim, w_m)
        self.pwm.update(u_ref_lim)

        # Data logging
        self.datalog.save([i_ref, i, u, 0, w_m_ref, w_m, theta_m, u_dc,
                           T_M, self.pwm.T_s])

        return d_abc_ref, self.pwm.T_s


# %%
class CurrentCtrl2DOFPI:
    """
    A current controller corresponding to the paper "Flux-linkage-based current
    control of saturated synchronous motors":

        https://doi.org/10.1109/TIA.2019.291925

    The continuous-time complex-vector design corresponding to (13) is used
    here. This design could be equivalently presented as a 2DOF PI controller.
    For better performance at high speed with low sampling frequencies, the
    discrete-time design in (18) is recommended.

    """

    def __init__(self, pars):
        """
        Parameters
        ----------
        pars : data object
            Controller parameters.

        """
        self.T_s = pars.T_s
        self.L_d = pars.L_d
        self.L_q = pars.L_q
        self.alpha_c = pars.alpha_c
        # Integral state
        self.u_i = 0

    def output(self, i_ref, i):
        """
        Computes the unlimited voltage reference.

        Parameters
        ----------
        i_ref : complex
            Current reference.
        i : complex
            Measured current.

        Returns
        -------
        u_ref : complex
            Unlimited voltage reference.

        """
        # Gains
        k_t = self.alpha_c
        k = 2*self.alpha_c
        # PM-flux linkage cancels out
        psi_ref = self.L_d*i_ref.real + 1j*self.L_q*i_ref.imag
        psi = self.L_d*i.real + 1j*self.L_q*i.imag
        u_ref = k_t*psi_ref - k*psi + self.u_i
        e = psi_ref - psi
        return u_ref, e

    def update(self, e, u_ref, u_ref_lim, w_m):
        """
        Updates the integral state.

        Parameters
        ----------
        e : complex
            Error signal (scaled, corresponds to the stator flux linkage).
        u_ref : complex
            Unlimited voltage reference.
        u_ref_lim : complex
            Limited voltage reference.
        w_m : float
            Angular rotor speed.

        """
        k_t = self.alpha_c
        k_i = self.alpha_c*(self.alpha_c + 1j*w_m)
        self.u_i += self.T_s*k_i*(e + (u_ref_lim - u_ref)/k_t)

    def __str__(self):
        desc = ('2DOF PI current control:\n'
                '    alpha_c=2*pi*{:.1f}')
        return desc.format(self.alpha_c/(2*np.pi))


# %%
class SensorlessVectorCtrl:
    """
    This class interconnects the subsystems of the PMSM control system and
    provides the interface to the solver.

    """

    def __init__(self, pars, speed_ctrl, current_ref, current_ctrl, observer,
                 datalog):
        """
        Instantiate the classes.

        """
        self.p = pars.p
        self.current_ctrl = current_ctrl
        self.speed_ctrl = speed_ctrl
        self.current_ref = current_ref
        self.observer = observer
        self.pwm = PWM(pars)
        self.datalog = datalog

    def __call__(self, w_m_ref, i_abc, u_dc):
        """
        Main control loop.

        Parameters
        ----------
        w_m_ref : float
            Rotor speed reference (in electrical rad/s).
        i_s_abc : ndarray, shape (3,)
            Phase currents.
        u_dc : float
            DC-bus voltage.

        Returns
        -------
        d_abc_ref : ndarray, shape (3,)
            Duty ratio references.
        T_s : float
            Sampling period.

        """
        # Get the states
        u = self.pwm.realized_voltage
        w_m = self.observer.w_m
        theta_m = self.observer.theta_m
        psi = self.observer.psi

        # Space vector and coordinate transformation
        i = np.exp(-1j*theta_m)*abc2complex(i_abc)

        # Outputs
        T_M_ref, T_L = self.speed_ctrl.output(w_m_ref/self.p, w_m/self.p)
        i_ref, T_M = self.current_ref.output(T_M_ref)
        u_ref = self.current_ctrl.output(i_ref, i, psi, w_m)
        d_abc_ref = self.pwm(u_ref, u_dc, theta_m, w_m)

        # Update all the states
        self.speed_ctrl.update(T_M, T_L)
        self.observer.update(u, i)
        self.current_ref.update(T_M, u_ref, u_dc)

        # Data logging
        self.datalog.save([i_ref, i, u, psi, w_m_ref, w_m, theta_m, u_dc,
                           T_M, self.pwm.T_s])

        return d_abc_ref, self.pwm.T_s


# %%
class CurrentRef:
    """
    This reference calculation method resembles the method "Analytical design
    and autotuning of adaptive flux-weakening voltage regulation loop in IPMSM
    drives with accurate torque regulation":

        https://doi.org/10.1109/TIA.2019.2942807

    Instead of the PI controller, we use a simpler integral controller with a
    constant gain. The resulting operating-point-dependent closed-loop pole
    could be derived using (12) of the paper. The MTPV limit is also used.

    """

    def __init__(self, pars):
        """
        Parameters
        ----------
        pars : data object
            Controller parameters.

        """
        self.T_s = pars.T_s
        self.i_max = pars.i_max
        self.p = pars.p
        self.L_d = pars.L_d
        self.L_q = pars.L_q
        self.psi_f = pars.psi_f
        self.i_d_mtpa = pars.i_d_mtpa
        self.i_q_mtpv = pars.i_q_mtpv
        self.i_d_ref = self.i_d_mtpa(0)
        self.k = pars.alpha_fw/(pars.w_nom*self.L_d)

    def output(self, T_M_ref):
        """
        Compute the stator current reference.

        Parameters
        ----------
        T_M_ref : float
            Torque reference.
        psi_R : float
            Rotor flux magnitude.

        Returns
        -------
        i_ref : complex
            Stator current reference.
        T_M : float
            Limited torque reference (i.e. torque estimate).

        """
        def q_axis_current_limit(i_d_ref):
            # Limit corresponding to the maximum current
            i_q_curr = np.sqrt(self.i_max**2 - i_d_ref**2)
            # Take the MTPV limit into account
            i_q_mtpv = self.i_q_mtpv(i_d_ref)
            if i_q_mtpv:
                i_q_max = np.min([i_q_curr, i_q_mtpv])
            else:
                i_q_max = i_q_curr
            return i_q_max

        psi_t = self.psi_f + (self.L_d - self.L_q)*self.i_d_ref
        if psi_t != 0:
            i_q_ref = T_M_ref/(1.5*self.p*psi_t)
        else:
            i_q_ref = 0
        # Limit the current
        i_q_max = q_axis_current_limit(self.i_d_ref)
        if np.abs(i_q_ref) > i_q_max:
            i_q_ref = np.sign(i_q_ref)*i_q_max
        # Current reference
        i_ref = self.i_d_ref + 1j*i_q_ref
        # Limited torque (for the speed controller)
        T_M = 1.5*self.p*psi_t*i_q_ref
        return i_ref, T_M

    def update(self, T_M, u_ref, u_dc):
        """
        Field-weakening based on the unlimited reference voltage.

        Parameters
        ----------
        u_ref : complex
            Unlimited stator voltage reference.
        u_dc : DC-bus voltage.
            float.

        """
        u_max = u_dc/np.sqrt(3)
        i_d_mtpa = self.i_d_mtpa(np.abs(T_M))
        self.i_d_ref += self.T_s*self.k*(u_max - np.abs(u_ref))
        if self.i_d_ref > i_d_mtpa:
            self.i_d_ref = i_d_mtpa
        elif self.i_d_ref < -self.i_max:
            self.i_d_ref = -self.i_max

    def __str__(self):
        desc = ('Current reference computation and field weakening:\n'
                '    i_s_max={:.1f}')
        return desc.format(self.i_max)


# %%
class CurrentCtrl:
    """
    This class represents a state-feedback current controller, with reference
    feedforward, without integral action.

    """

    def __init__(self, pars):
        """
        Parameters
        ----------
        pars : data object
            Controller parameters.

        """
        self.alpha_c = pars.alpha_c
        self.L_d = pars.L_d
        self.L_q = pars.L_q
        self.R = pars.R

    def output(self, i_ref, i, psi, w_m):
        """
        State-feedback current controller.

        Parameters
        ----------
        i_ref : complex
            Stator current reference.
        i : complex
            Stator current.
        w_m : float
            Rotor speed (in electrical rad/s).

        Returns
        -------
        u_ref : complex
            Voltage reference.

        """
        # Map current error to the flux linkage error
        err = self.L_d*np.real(i_ref - i) + 1j*self.L_q*np.imag(i_ref - i)
        # Voltage reference in rotor coordinates
        u_ref = self.R*i + 1j*w_m*psi + self.alpha_c*err
        return u_ref

    def update(self, *_):
        """
        No states, nothing to update. This method is just for compatibility.

        """

    def __str__(self):
        desc = ('State-feedback current control (without integral action):\n'
                '    alpha_c=2*pi*{:.1f}')
        return desc.format(self.alpha_c/(2*np.pi))


# %%
class SensorlessObserver:
    """
    A sensorless observer corresponding to the paper "Observers for sensorless
    synchronous motor drives: Framework for design and analysis":

        https://doi.org/10.1109/TIA.2018.2858753

    The observer gain decouples the electrical and mechanical dynamicas and
    allows placing the poles of the corresponding linearized estimation
    error dynamics.

    """

    def __init__(self, pars):
        """
        Parameters
        ----------
        pars : data object
            Controller parameters.

        """
        self.T_s = pars.T_s
        self.R = pars.R
        self.L_d = pars.L_d
        self.L_q = pars.L_q
        self.psi_f = pars.psi_f
        self.k_p = 2*pars.w_o
        self.k_i = pars.w_o**2
        self.b_p = pars.b_p
        self.zeta = pars.zeta
        # Initial states
        self.theta_m, self.w_m, self.psi = 0, 0, pars.psi_f

    def update(self, u, i):
        """
        Update the states for the next sampling period.

        Parameters
        ----------
        u : complex
            Stator voltage in estimated rotor coordinates.
        i : complex
            Stator current in estimated rotor coordinates.

        Returns
        -------
        w_m : float
            Angular rotor speed.
        dpsi : float
            Increment of the flux magnitude for the state update.

        """
        def corr_vector(w_m):
            # Choose pole location according to (36)
            b = self.b_p + 2*self.zeta*np.abs(w_m)
            c_per_w_m = .5*b/self.zeta*np.sign(w_m)
            # Gain (30), implemented using the complex quantities
            k = b + (c_per_w_m - w_m)*1j
            if psi_a.real != 0:
                beta = -psi_a.imag/psi_a.real
            else:
                beta = 0
            T = np.array([[1, -beta], [-beta, beta**2]])/(1 + beta**2)
            v = T.dot([e.real, e.imag])
            # Correction voltage vector for the observer (6)
            return k*(v[0] + 1j*v[1])
        # Estimation error (6)
        e = self.L_d*i.real + 1j*self.L_q*i.imag + self.psi_f - self.psi
        # Auxiliary flux (12)
        psi_a = (self.L_d - self.L_q)*np.conj(i) + self.psi_f
        # Projection vector for speed estimation
        if psi_a.real > 0:
            lmbd = 1/psi_a.real                 # (34)
            # lmbd = psi_a/np.abs(psi_a)**2      # (33)
        else:
            lmbd = 0
        # Generalized error signal (10)
        eps = np.imag(lmbd*np.conj(e))
        # Speed estimation (9)
        w_m = self.k_p*eps + self.w_m
        # Stator flux increment (6)
        dpsi = u - self.R*i - 1j*w_m*self.psi + corr_vector(self.w_m)
        # Update the states
        self.w_m += self.T_s*self.k_i*eps
        self.psi += self.T_s*dpsi
        self.theta_m += self.T_s*w_m
        self.theta_m = np.mod(self.theta_m, 2*np.pi)    # Limit to [0, 2*pi]

    def __str__(self):
        desc = ('Sensorless observer:\n'
                '    w_o=2*pi*{:.1f}')
        return desc.format(.5*self.k_p/(2*np.pi))


# %%
class Datalogger:
    """
    This class contains a data logger.

    """

    def __init__(self):
        """
        Initialize the attributes.

        """
        self.t = []
        self.i_ref = []
        self.i = []
        self.u = []
        self.psi = []
        self.w_m_ref = []
        self.w_m = []
        self.theta_m = []
        self.u_dc = []
        self.T_M = []
        self.u_s, self.i_s = 0j, 0j

    def save(self, data):
        """
        Saves the solution.

        Parameters
        ----------
        mdl : instance of a class
            Continuous-time model.

        """
        (i_ref, i, u, psi, w_m_ref, w_m, theta_m, u_dc, T_M, T_s) = data
        try:
            t_new = self.t[-1] + T_s
        except IndexError:
            t_new = 0   # At the first step t = []
        self.t.extend([t_new])
        self.i_ref.extend([i_ref])
        self.i.extend([i])
        self.u.extend([u])
        self.psi.extend([psi])
        self.w_m_ref.extend([w_m_ref])
        self.w_m.extend([w_m])
        self.theta_m.extend([theta_m])
        self.u_dc.extend([u_dc])
        self.T_M.extend([T_M])

    def post_process(self):
        """
        Transforms the lists to the ndarray format and post-process them.

        """
        self.i_ref = np.asarray(self.i_ref)
        self.i = np.asarray(self.i)
        self.u = np.asarray(self.u)
        self.psi = np.asarray(self.psi)
        self.w_m_ref = np.asarray(self.w_m_ref)
        self.w_m = np.asarray(self.w_m)
        self.theta_m = np.asarray(self.theta_m)
        self.u_dc = np.asarray(self.u_dc)
        self.T_M = np.asarray(self.T_M)
        self.u_s = np.exp(1j*self.theta_m)*self.u
        self.i_s = np.exp(1j*self.theta_m)*self.i

    def plot(self, mdl):
        """
        Plots some example figures.

        Parameters
        ----------
        t : ndarray
            Discrete time.
        mdl : instance of a class
            Continuous-time solution.

        """
        # Continuous-time data
        data = mdl.datalog
        # Time spans
        t_range = (0, self.t[-1])
        plt.rcParams['axes.prop_cycle'] = cycler(color='brgcmyk')
        plt.rcParams['lines.linewidth'] = 1.
        plt.rcParams.update({"text.usetex": True,
                             "font.family": "serif",
                             "font.sans-serif": ["Computer Modern Roman"]})
        # Plots speeds and torques
        fig1, (ax1, ax2) = plt.subplots(2, 1)
        ax1.step(self.t, self.w_m_ref, '--', where='post')
        ax1.plot(data.t, data.w_m)
        ax1.step(self.t, self.w_m, where='post')
        ax1.legend([r'$\omega_\mathrm{m,ref}$',
                    r'$\omega_\mathrm{m}$',
                    r'$\hat \omega_\mathrm{m}$'])
        ax1.set_xlim(t_range)
        ax1.set_ylabel('Angular speed (rad/s)')
        ax2.plot(data.t, data.T_L, '--')
        ax2.plot(data.t, data.T_M)
        ax2.plot(self.t, self.T_M)  # Limited torque reference
        ax2.set_xlim(t_range)
        ax2.legend([r'$\tau_\mathrm{L}$', r'$\tau_\mathrm{m}$',
                    r'$\tau_\mathrm{m,ref}$'])
        ax2.set_ylabel('Torque (Nm)')
        ax2.set_xlabel('Time (s)')
        # Plots currents, fluxes, and voltages
        fig2, (ax1, ax2, ax3) = plt.subplots(3, 1)
        ax1.step(self.t, self.i_ref.real, '--', where='post')
        ax1.step(self.t, self.i.real, where='post')
        ax1.step(self.t, self.i_ref.imag, '--', where='post')
        ax1.step(self.t, self.i.imag, where='post')
        ax1.set_ylabel('Current (A)')
        ax1.legend([r'$i_\mathrm{d,ref}$', r'$i_\mathrm{d}$',
                    r'$i_\mathrm{q,ref}$', r'$i_\mathrm{q}$'])
        ax1.set_xlim(t_range)
        ax2.plot(data.t, data.psi.real)
        ax2.step(self.t, self.psi.real, '--', where='post')
        ax2.plot(data.t, data.psi.imag)
        ax2.step(self.t, self.psi.imag, '--', where='post')
        ax2.set_xlim(t_range)
        ax2.legend([r'$\psi_\mathrm{d}$', r'$\hat\psi_\mathrm{d}$',
                    r'$\psi_\mathrm{q}$', r'$\hat\psi_\mathrm{q}$'])
        ax2.set_ylabel('Flux linkage (Vs)')
        ax2.set_xlabel('Time (s)')
        # ax3.step(self.t, self.u.real, where='post')
        # ax3.step(self.t, self.u.imag, where='post')
        ax3.step(self.t, np.abs(self.u), where='post')
        ax3.step(self.t, self.u_dc/np.sqrt(3), '--', where='post')
        ax3.set_xlim(t_range)
        ax3.legend([r'$u$', r'$u_\mathrm{dc}/\sqrt{3}$'])
        # ax3.legend([r'$u_\mathrm{d}$', r'$u_\mathrm{q}$', r'$u$'])
        ax3.set_ylabel('Voltage (V)')
        ax3.set_xlabel('Time (s)')
        # Flux estimation
        fig3, (ax1, ax2) = plt.subplots(2, 1)
        ax1.plot(data.t, data.theta_m)
        ax1.step(self.t, self.theta_m, '--', where='post')
        ax1.set_ylabel('Angle (rad)')
        ax1.legend([r'$\vartheta_\mathrm{m}$', r'$\hat \vartheta_\mathrm{m}$'])
        ax1.set_xlim(t_range)
        ax2.plot(data.t, np.abs(data.psi))
        ax2.step(self.t, np.abs(self.psi), '--', where='post')
        ax2.set_xlim(t_range)
        ax2.legend([r'$|\psi|$', r'$|\hat\psi|$'])
        ax2.set_ylabel('Flux linkage (Vs)')
        ax2.set_xlabel('Time (s)')
        plt.show()
        # plt.savefig('test.pdf')
        return fig1, fig2, fig3
