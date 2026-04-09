"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

from dataclasses import dataclass

@dataclass
class Trade:
    exchange  : str
    price     : float
    size      : float
    timestamp : float

@dataclass
class Order:
    exchange : str
    side     : str  # 'buy' or 'sell'
    price    : float
    size     : float
    ts_sent  : float

@dataclass
class BookLevel:
    side        : str  # 'buy' or 'sell'
    price       : float
    size        : float
    exchange    : str # if we want to create a consolidated book, we will need this info
    last_update : float 
