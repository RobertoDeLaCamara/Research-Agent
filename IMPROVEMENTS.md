# Product Roadmap & Improvements 🚀

This document outlines the planned improvements, technical debt repayment, and feature roadmap for the Research-Agent.

## 📋 Short Term (This Month)

These items are high-priority/low-effort improvements focusing on stability and code quality.

- [ ] **Improve Thread Safety**: Fix potential race conditions in `research_tools.py` (specifically `nonlocal` usage).
- [ ] **Add Type Hints**: Complete type coverage in `utils.py` and other modules to reach 100% typing.
- [ ] **Strengthen Security Tests**: Add dedicated tests for XSS, injection, and malicious file uploads.
- [ ] **Implement Rate Limiting**: Protect the API against abuse using `slowapi`.
- [ ] **Enhanced Logging**: Implement structured logging (e.g., using `structlog`) for better observability in production.

## 🔮 Medium Term (This Quarter)

Strategic improvements to architecture and scalability.

- [ ] **Parallel Source Execution**: Refactor `research_tools.py` to use `asyncio` for running independent research nodes (Web, Wiki, ArXiv) in parallel, reducing overall latency.
- [ ] **Redis Caching**: Implement a distributed caching layer (Redis) to replace/augment the file-based cache for better performance in scale-out scenarios.
- [ ] **Health Check Endpoint**: Add a standardized `/health` endpoint for load balancers and k8s probes.
- [ ] **Monitoring Dashboard**: Integrate open-source monitoring (Grafana/Prometheus) to track agent performance, success rates, and latency.
- [ ] **API Authentication**: Implement JWT or API Key authentication for the backend API.

## 🔭 Extended Roadmap (Vision)

- **Cloud Native Support**: Full Kubernetes deployment manifests (Helm Charts).
- **Multi-Agent Collaboration**: Enable multiple specialized agents to collaborate on a single complex topic in real-time.
- **Custom Model Fine-Tuning**: Pipeline to fine-tune local LLMs (like Qwen or Llama) on the user's specific research patterns.
