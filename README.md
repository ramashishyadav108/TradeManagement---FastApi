# Cryptocurrency Matching Engine 🚀

A high-performance cryptocurrency matching engine implementing REG NMS-inspired principles with real-time trading capabilities.

## 🌟 Features

- **REG NMS-Inspired Matching**: Price-time priority with strict trade-through prevention
- **Multiple Order Types**: Market, Limit, IOC (Immediate-Or-Cancel), FOK (Fill-Or-Kill)
- **Real-time Data Streaming**: WebSocket feeds for order book and trade execution
- **High Performance**: Process 1000+ orders per second with sub-millisecond latency
- **Interactive UI**: Streamlit-based trading interface with live updates
- **Comprehensive Testing**: 90%+ code coverage with unit, integration, and performance tests

## 📋 Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Testing](#testing)
- [Performance](#performance)
- [Contributing](#contributing)

## 🏗️ Architecture

The system consists of three main layers:

1. **Core Engine**: Order book management and matching algorithm
2. **API Layer**: FastAPI REST endpoints and WebSocket streams
3. **Frontend**: Streamlit-based trading interface

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip or conda

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd gQnt
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Start the backend:
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

5. Start the frontend (in a new terminal):
```bash
streamlit run frontend/app.py --server.port 8501
```

6. Access the application:
- Frontend UI: http://localhost:8501
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## 📁 Project Structure

```
gQnt/
├── backend/          # FastAPI backend
│   ├── core/        # Domain models and matching engine
│   ├── api/         # REST and WebSocket endpoints
│   ├── services/    # Business logic layer
│   ├── utils/       # Utilities and helpers
│   └── tests/       # Test suite
├── frontend/         # Streamlit frontend
│   ├── components/  # UI components
│   ├── services/    # API clients
│   └── utils/       # Frontend utilities
└── docs/            # Documentation
```

## 📚 API Documentation

### REST Endpoints

- `POST /api/v1/orders` - Submit new order
- `DELETE /api/v1/orders/{order_id}` - Cancel order
- `GET /api/v1/orders/{order_id}` - Get order status
- `GET /api/v1/orderbook/{symbol}` - Get order book snapshot

### WebSocket Streams

- `WS /ws/orderbook/{symbol}` - Real-time order book updates
- `WS /ws/trades` - Real-time trade execution feed

See [docs/api_specification.md](docs/api_specification.md) for complete API reference.

## 🛠️ Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest backend/tests/test_matching_engine.py -v

# Run performance tests
pytest -m performance
```

### Code Quality

```bash
# Type checking
mypy backend/

# Linting
flake8 backend/

# Formatting
black backend/ frontend/
```

## ⚡ Performance

Target benchmarks:

- **Throughput**: >1000 orders/second
- **Latency**: 
  - Limit orders: <1ms (p95)
  - Market orders: <5ms (p95)
  - WebSocket broadcast: <50ms (p95)
- **Memory**: <500MB for 100k active orders

Run benchmarks:
```bash
python backend/tests/benchmark.py
```

## 🧪 Testing

The project includes comprehensive test coverage:

- Unit tests for core components
- Integration tests for API endpoints
- Performance benchmarks
- Stress tests for concurrent operations

Minimum coverage requirement: 85%

## 📖 Documentation

- [Architecture](docs/architecture.md) - System design and components
- [API Specification](docs/api_specification.md) - Complete API reference
- [Design Decisions](docs/design_decisions.md) - Technical trade-offs and rationale

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 👥 Authors

- Your Name - Initial work

## 🙏 Acknowledgments

- REG NMS regulations for market structure inspiration
- FastAPI and Streamlit communities

---

**Built with ❤️ for high-frequency trading**
