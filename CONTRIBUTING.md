# Contributing to Research-Agent

Thank you for your interest in contributing to Research-Agent! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Git
- Docker (optional but recommended)

### Development Setup
```bash
# Clone the repository
git clone <repository-url>
cd research-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-mock pytest-asyncio black flake8 mypy

# Set up environment
cp env.example .env
# Edit .env with your configuration
```

## 🧪 Testing

### Running Tests
```bash
# Run all tests
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
pytest tests/ -v

# Run specific test file
pytest tests/test_research_tools.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Writing Tests
- Place tests in the `tests/` directory
- Use descriptive test names: `test_function_name_scenario`
- Mock external dependencies
- Aim for 100% test coverage

Example test:
```python
def test_search_web_node_returns_structure(mock_agent_state):
    """Test that web search returns expected structure."""
    result = search_web_node(mock_agent_state)
    assert "web_research" in result
    assert isinstance(result["web_research"], list)
```

## 📝 Code Style

### Python Style Guide
- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 88 characters
- Use descriptive variable names

### Code Formatting
```bash
# Format code with black
black src/ tests/

# Check with flake8
flake8 src/ tests/

# Type checking with mypy
mypy src/
```

### Documentation
- Add docstrings to all functions and classes
- Use Google-style docstrings
- Update README.md for new features
- Include examples in docstrings

Example docstring:
```python
def search_web_node(state: AgentState) -> dict:
    """Search the web using Tavily or DuckDuckGo fallback.
    
    Args:
        state: The current agent state containing the research topic.
        
    Returns:
        Dictionary containing web research results.
        
    Example:
        >>> state = {"topic": "AI research"}
        >>> result = search_web_node(state)
        >>> assert "web_research" in result
    """
```

## 🏗️ Architecture Guidelines

### Code Organization
```
src/
├── config.py          # Configuration management
├── state.py           # Shared state definitions
├── utils.py           # Utility functions
├── cache.py           # Caching system
├── metrics.py         # Performance monitoring
├── progress.py        # Progress tracking
├── validators.py      # Input validation
├── health.py          # Health checks
├── quality.py         # Content quality scoring
├── async_research.py  # Async operations
├── agent.py           # Main agent workflow
├── main.py            # CLI entry point
├── app.py             # Web dashboard
└── tools/             # Research tools
    ├── research_tools.py
    ├── synthesis_tools.py
    ├── reporting_tools.py
    └── youtube_tools.py
```

### Design Principles
1. **Separation of Concerns**: Each module has a single responsibility
2. **Dependency Injection**: Use configuration and dependency injection
3. **Error Handling**: Comprehensive error handling with logging
4. **Performance**: Async operations where possible
5. **Testing**: All code must be testable with mocks

### Adding New Features

#### 1. Research Sources
To add a new research source:

```python
# In src/tools/research_tools.py
def search_new_source_node(state: AgentState) -> dict:
    """Search new research source."""
    from progress import update_progress
    from metrics import metrics
    
    update_progress("New Source Search")
    
    @metrics.time_operation("new_source_search")
    def _search():
        # Implementation here
        return results
    
    results = _search()
    return {"new_source_research": results}
```

#### 2. Configuration Options
Add new settings to `src/config.py`:

```python
class Settings(BaseSettings):
    # Existing settings...
    new_setting: str = "default_value"
    new_optional_setting: Optional[int] = None
```

#### 3. Validation Rules
Add validation to `src/validators.py`:

```python
def validate_new_input(input_data: str) -> str:
    """Validate new input type."""
    if not input_data:
        raise ValueError("Input cannot be empty")
    return input_data.strip()
```

## 🔄 Pull Request Process

### Before Submitting
1. **Run Tests**: Ensure all tests pass
2. **Code Quality**: Run linting and formatting
3. **Documentation**: Update relevant documentation
4. **Type Hints**: Add type hints to new code

### PR Guidelines
1. **Clear Title**: Descriptive title explaining the change
2. **Description**: Explain what and why, not just how
3. **Small Changes**: Keep PRs focused and small
4. **Tests**: Include tests for new functionality
5. **Documentation**: Update docs for user-facing changes

### PR Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
```

## 🐛 Bug Reports

### Before Reporting
1. Check existing issues
2. Try latest version
3. Reproduce the issue
4. Gather relevant information

### Bug Report Template
```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., Ubuntu 20.04]
- Python version: [e.g., 3.10.5]
- Research-Agent version: [e.g., v2.0]

## Additional Context
Any other relevant information
```

## 💡 Feature Requests

### Feature Request Template
```markdown
## Feature Description
Clear description of the proposed feature

## Use Case
Why is this feature needed?

## Proposed Solution
How should this feature work?

## Alternatives Considered
Other approaches you've considered

## Additional Context
Any other relevant information
```

## 📋 Development Workflow

### Git Workflow
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and commit: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

### Commit Messages
Use conventional commit format:
```
type(scope): description

feat(search): add new research source
fix(cache): resolve cache expiration issue
docs(readme): update installation instructions
test(tools): add tests for research tools
```

## 🏷️ Release Process

### Version Numbering
- Major: Breaking changes (v2.0.0)
- Minor: New features (v2.1.0)
- Patch: Bug fixes (v2.1.1)

### Release Checklist
1. Update version numbers
2. Update CHANGELOG.md
3. Run full test suite
4. Update documentation
5. Create release tag
6. Deploy to production

## 🤝 Community

### Code of Conduct
- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow the golden rule

### Getting Help
- Check documentation first
- Search existing issues
- Ask questions in discussions
- Be specific and provide context

## 📚 Resources

### Documentation
- [README.md](README.md) - Main documentation
- [API.md](API.md) - API reference
- [CHANGELOG.md](CHANGELOG.md) - Version history

### Tools
- [Black](https://black.readthedocs.io/) - Code formatting
- [Flake8](https://flake8.pycqa.org/) - Linting
- [MyPy](https://mypy.readthedocs.io/) - Type checking
- [Pytest](https://pytest.org/) - Testing framework

Thank you for contributing to Research-Agent! 🎉
