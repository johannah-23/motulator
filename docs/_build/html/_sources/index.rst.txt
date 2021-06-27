.. modulator documentation master file, created by
   sphinx-quickstart on Sat Jun 26 01:22:12 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to modulator's documentation!
=====================================

*Open-Source Simulator for Motor Drives and Power Converters*

This document is the reference documentation for the motulator -simulation platform developed using Python.

This simulation platform includes simulation models for an induction motor, a synchronous reluctance motor, and a permanent-magnet synchronous motor. Furthermore, some simple control algorithms are included as examples. The motor models are simulated in the continuous-time domain while the control algorithms run in discrete time. The default solver is the explicit Runge-Kutta method of order 5(4) from scipy.integrate.solve_ivp.

Documentation contents
----------------------

.. toctree::
   :maxdepth: 2
   :numbered:

   Introduction
   Configuration and structure
   Simulation models
   Reference

Search
----------------------

* :ref:`search`
