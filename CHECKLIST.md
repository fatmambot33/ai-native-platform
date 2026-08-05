# First-Class AI-Native Platform Checklist

A repository is compliant only when declarations are backed by repository evidence. Items marked **conditional** are required when the product exposes that surface or when the capability is justified by its use cases.

## Vision & Product

- [ ] Clear AI-first product vision
- [ ] API-first architecture
- [ ] Human + agent workflows
- [ ] Stable public contracts
- [ ] Semantic versioning
- [ ] Backward compatibility policy

## AI Contracts

- [ ] Canonical capability registry
- [ ] Stable capability names
- [ ] Versioned capabilities
- [ ] JSON Schema inputs
- [ ] JSON Schema outputs
- [ ] Structured result envelopes
- [ ] Structured error envelopes
- [ ] Machine-readable metadata
- [ ] Deterministic outputs

## Plugin Surface

- [ ] Public, versioned plugin contract
- [ ] Typed plugin protocol or abstract base
- [ ] Deterministic plugin registration and discovery
- [ ] Capability metadata
- [ ] Plugin lifecycle and compatibility policy
- [ ] Codex plugin manifest
- [ ] Git-backed Codex marketplace catalog
- [ ] Plugin contract and discovery tests

## Agent Readiness

- [ ] MCP server
- [ ] Codex integration
- [ ] OpenAI Agents SDK integration
- [ ] Function/tool calling
- [ ] Capability discovery
- [ ] Permission-aware tools
- [ ] Safety classifications
- [ ] Tool versioning
- [ ] Agent playbooks

## SDKs

- [ ] Python SDK
- [ ] TypeScript SDK — **conditional when justified**
- [ ] Async support
- [ ] Streaming support — **conditional when applicable**
- [ ] Typed models
- [ ] Pagination helpers — **conditional for collection APIs**
- [ ] Retry helpers — **conditional for networked products**
- [ ] Authentication helpers — **conditional for credentialed products**

## APIs

- [ ] REST/OpenAPI — **conditional when a network API is exposed**
- [ ] Stable endpoints
- [ ] Idempotent operations
- [ ] Filtering
- [ ] Search
- [ ] Batch operations
- [ ] Cursor pagination

## Typing & Schemas

- [ ] Public API is fully typed
- [ ] `py.typed` is packaged, or an equivalent explicit typing contract exists
- [ ] Strict Pyright or MyPy runs in CI
- [ ] Tool inputs and outputs use machine-readable schemas
- [ ] Structured outputs are deterministic
- [ ] Schema compatibility is tested

## Installation & Configuration

- [ ] PyPI installation documented and smoke-tested
- [ ] Git installation documented and smoke-tested
- [ ] Editable development installation documented
- [ ] Quick Start completes in under five minutes
- [ ] Credentialed products provide `.env.example`
- [ ] Credentials remain local and are ignored by Git
- [ ] Credentialed products provide guided `configure` and `doctor` commands
- [ ] Secret values are never echoed, logged, committed, or remotely stored

## Documentation

- [ ] Excellent README
- [ ] Quick Start (<5 min)
- [ ] Tutorials
- [ ] Cookbook
- [ ] API Reference
- [ ] SDK Reference
- [ ] Architecture docs
- [ ] Agent docs
- [ ] Prompt examples
- [ ] `llms.txt`
- [ ] Machine-readable docs
- [ ] Plugin installation and usage guide
- [ ] `AGENTS.md`

## Developer Experience

- [ ] Copy/paste examples
- [ ] CLI
- [ ] Notebooks — **conditional when useful**
- [ ] Example applications
- [ ] Docker Compose — **conditional for services**
- [ ] Migration guides
- [ ] FAQ
- [ ] Troubleshooting

## Reliability

- [ ] Retry policy
- [ ] Timeouts
- [ ] Cancellation
- [ ] Circuit breakers — **conditional for networked services**
- [ ] Rate limiting
- [ ] Quota handling
- [ ] Graceful degradation

## Observability

- [ ] Structured logging
- [ ] Request IDs
- [ ] Tracing
- [ ] Metrics
- [ ] Token usage — **conditional for model calls**
- [ ] Latency metrics
- [ ] Cost metrics — **conditional for metered services**
- [ ] Audit logs

## Security

- [ ] OAuth/API Keys — **conditional for authenticated products**
- [ ] Fine-grained permissions
- [ ] Secret redaction
- [ ] Encryption
- [ ] Least privilege
- [ ] Audit trails
- [ ] Data isolation
- [ ] Human confirmation for writes or destructive actions

## AI Evaluation

- [ ] Golden datasets
- [ ] Tool-calling evaluations
- [ ] Prompt regression tests
- [ ] Schema validation
- [ ] Hallucination tests
- [ ] Prompt-injection tests
- [ ] Latency benchmarks
- [ ] Cost benchmarks
- [ ] Quality scorecards

## Testing

- [ ] Unit tests
- [ ] Integration tests
- [ ] End-to-end tests
- [ ] Contract tests
- [ ] SDK tests
- [ ] Agent tests
- [ ] MCP tests — **conditional when MCP is exposed**
- [ ] Performance tests
- [ ] Fuzz tests
- [ ] Plugin lifecycle and discovery tests
- [ ] Packaging and clean-install smoke tests

## Automation

- [ ] Generate SDKs from contracts — **when generation is appropriate**
- [ ] Generate MCP tools
- [ ] Generate CLI commands
- [ ] Generate OpenAPI
- [ ] Generate JSON Schemas
- [ ] Generate documentation
- [ ] Generate examples
- [ ] Generate changelogs
- [ ] Avoid duplicated capability definitions

## CI/CD

- [ ] Formatting
- [ ] Linting
- [ ] Type checking
- [ ] Documentation validation
- [ ] Example validation
- [ ] Dependency scanning
- [ ] CodeQL
- [ ] Secret scanning
- [ ] SBOM generation
- [ ] Provenance attestations
- [ ] Automated releases
- [ ] AI-native repository evidence validation

## Distribution

- [ ] PyPI
- [ ] npm — **conditional for TypeScript packages**
- [ ] Docker image — **conditional for services**
- [ ] GitHub Releases
- [ ] Homebrew — **conditional for suitable CLIs**
- [ ] Codex plugin marketplace

## Community

- [ ] Contributing guide
- [ ] Code of Conduct
- [ ] Issue templates
- [ ] PR templates
- [ ] Public roadmap
- [ ] Release notes
- [ ] Discussions

## Self-Improvement

- [ ] GitHub Issues are the agent work queue
- [ ] Agent-ready issue templates include evidence and acceptance criteria
- [ ] Scheduled improvement discovery exists
- [ ] Duplicate issues are prevented
- [ ] Agents may prepare branches and pull requests
- [ ] CI is required before merge
- [ ] Roadmap and changelog are updated
- [ ] Breaking, security, credential, public API, permission, and release changes require human approval
- [ ] Safe maintenance may be auto-merged only under explicit policy

## AI-Native Excellence

- [ ] Self-describing platform
- [ ] Schema-first development
- [ ] Single source of truth
- [ ] Generated interfaces
- [ ] Zero duplicated definitions
- [ ] Human- and LLM-friendly documentation
- [ ] Multi-model compatibility
- [ ] Backward-compatible evolution
- [ ] Production-ready defaults
- [ ] Safe-by-default design
- [ ] Minimal configuration
- [ ] First-class agent experience

## Definition of Done

A platform is truly **AI-native** when:

- Every capability is defined once in a typed, versioned contract.
- Humans, SDKs, CLIs, MCP servers, plugins, and AI agents consume that same contract.
- Documentation, schemas, tool definitions, examples, and tests are generated from or validated against a single source of truth.
- AI agents can reliably discover, understand, execute, and recover from every capability without custom prompt engineering.
- The platform is observable, secure, testable, backward compatible, self-improving, and production-ready.
