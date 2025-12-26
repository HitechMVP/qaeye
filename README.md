# <div align="center">Check for Drowsiness</div>

## Table of Contents

- [About](#about)
- [Structure](#structure)
- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Usage](#usage)
    - [`main.py`](#mainpy)

## About

This project focuses on detecting worker drowsiness during the final inspection stage of a manufacturing process. Using MediaPipe’s Face Landmarker with Blendshapes, the system extracts facial features — specifically the eye openness ratio — to estimate the worker’s level of alertness in real time.

A custom logic module was implemented to analyze the degree of eye openness and determine drowsiness status. The solution is optimized and deployed on Raspberry Pi 4, enabling real-time monitoring with efficient on-edge inference.

This project aims to improve workplace safety and productivity by providing an automated, lightweight, and deployable solution for human condition monitoring in industrial environments

