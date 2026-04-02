from dataclasses import dataclass

@dataclass
class Trade:
    exchange: str
    price: float
    size: float
    timestamp: float

@dataclass
class Order:
    exchange: str
    side: str  # 'buy' or 'sell'
    price: float
    size: float

@dataclass
class BookLevel:
    price: float
    size: float
    exchange: str