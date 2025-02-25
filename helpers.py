# pylint: disable=C0103
# pylint: disable=R0903
"""
This module contains various helper functions and classes.

"""
# %%
import numpy as np


# %%
def abc2complex(u):
    """
    Transform three-phase quantities to a complex space vector.

    Parameters
    ----------
    u : array_like, shape (3,)
        Phase quantities.

    Returns
    -------
    complex
        Complex space vector (peak-value scaling).

    Examples
    --------
    >>> y = abc2complex([1, 2, 3])
    >>> y
    (-1-0.5773502691896258j)

    """
    return (2/3)*u[0] - (u[1] + u[2])/3 + 1j*(u[1] - u[2])/np.sqrt(3)


# %%
def complex2abc(u):
    """
    Transform a complex space vector to three-phase quantities.

    Parameters
    ----------
    u : complex
        Complex space vector (peak-value scaling).

    Returns
    -------
    ndarray, shape (3,)
        Phase quantities.

    Examples
    --------
    >>> y = complex2abc(1-.5j)
    >>> y
    array([ 1.       , -0.9330127, -0.0669873])

    """
    return np.array([u.real,
                     .5*(-u.real + np.sqrt(3)*u.imag),
                     .5*(-u.real - np.sqrt(3)*u.imag)])


# %%
class Sequence:
    """
    This class represents a sequence generator. The time array must be
    increasing. The output values are interpolated between the data points.

    """

    def __init__(self, times, values, periodic=False):
        self.times = times
        self.values = values
        if periodic is True:
            self.__period = times[-1] - times[0]
        else:
            self.__period = None

    def __call__(self, t):
        """
        Interpolates the output.

        Parameters
        ----------
        t : float
            Time.

        Returns
        -------
        float or complex
            Interpolated output.

        """
        return np.interp(t, self.times, self.values, period=self.__period)

    def __str__(self):
        desc = ('Sequence:\n    times={}\n    values={}')
        return desc.format(self.times, self.values)


# %%
class Step:
    """
    This data class represents a step function.

    """

    def __init__(self, step_time, step_value, initial_value=0):
        self.step_time = step_time
        self.step_value = step_value
        self.initial_value = initial_value

    def __call__(self, t):
        """
        Step function.

        Parameters
        ----------
        t : float
            Time.

        Returns
        -------
        float
            Step output.

        """
        return self.initial_value + (t >= self.step_time)*self.step_value

    def __str__(self):
        desc = ('Step(step_time={}, initial_value={:.1f}, step_value={:.1f})')
        return desc.format(self.step_time,
                           self.initial_value, self.step_value)


# %%
class LUT:
    """
    This class represents a 1-D look-up table with linear interpolation.

    """

    def __init__(self, x_data, y_data):
        self.x_data = x_data
        self.y_data = y_data

    def __call__(self, x):
        """
        Interpolates the output.

        Parameters
        ----------
        x : float
            Reference.

        Returns
        -------
        complex
            Interpolated output value.

        """
        return np.interp(x, self.x_data, self.y_data)
