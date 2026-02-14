# Product Roadmap & Improvements 🚀

This document outlines the planned improvements, technical debt repayment, and feature roadmap for the Research-Agent.

## 📋 Short Term (This Month)

These items are high-priority/low-effort improvements focusing on stability and code quality.

- [x] **Improve Thread Safety**: Fixed race conditions by replacing `nonlocal` with thread-safe mutable container pattern across 4 files.
- [ ] **Add Type Hints**: Complete type coverage in `utils.py` and other modules to reach 100% typing.
- [x] **Strengthen Security Tests**: Added dedicated tests for XSS, injection, and malicious file uploads (7 security tests).
- [ ] **Implement Rate Limiting**: Protect the API against abuse using `slowapi`.
- [x] **Enhanced Logging**: Implemented structured logging with `structlog`. JSON output in production, console in dev. All `print()` calls replaced with structured `logger.*` calls.

## 🔮 Medium Term (This Quarter)

Strategic improvements to architecture and scalability.

- [x] **Parallel Source Execution**: Implemented `parallel_search_node` using `ThreadPoolExecutor` for concurrent source execution. All planned sources run in parallel.
- [ ] **Redis Caching**: Implement a distributed caching layer (Redis) to replace/augment the file-based cache for better performance in scale-out scenarios.
- [x] **Health Check Endpoint**: Added `HEALTHCHECK` in Dockerfile using Streamlit's `/_stcore/health` endpoint.
- [ ] **Monitoring Dashboard**: Integrate open-source monitoring (Grafana/Prometheus) to track agent performance, success rates, and latency.
- [ ] **API Authentication**: Implement JWT or API Key authentication for the backend API.

## 🔭 Extended Roadmap (Vision)

- **Cloud Native Support**: Full Kubernetes deployment manifests (Helm Charts).
- **Multi-Agent Collaboration**: Enable multiple specialized agents to collaborate on a single complex topic in real-time.
- **Custom Model Fine-Tuning**: Pipeline to fine-tune local LLMs (like Qwen or Llama) on the user's specific research patterns.
