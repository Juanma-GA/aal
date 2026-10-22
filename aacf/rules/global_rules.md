# Global Rules

These rules apply to ALL AI-assisted code generation regardless of language, framework, or tier.

## Rule 1: Security First
Never generate code that introduces security vulnerabilities. Apply OWASP Top 10 awareness at all times. Validate inputs, escape outputs, use parameterized queries.

## Rule 2: No Hardcoded Secrets
Never hardcode passwords, API keys, tokens, or connection strings. Always use environment variables or a secrets manager.

## Rule 3: Data Classification Awareness
All code that handles data must respect the organization's data classification levels (Public, Internal, Confidential, Strictly Confidential). Never process or output data above the project's classification ceiling.

## Rule 4: Audit Trail
All significant operations must be logged with sufficient context for audit (who, what, when, where). Never log sensitive data (passwords, tokens, PII).

## Rule 5: Error Handling
Handle errors gracefully. Never expose stack traces or internal system details to end users. Log full details server-side, return sanitized messages to clients.

## Rule 6: Dependency Security
Only use dependencies from approved sources. Check for known vulnerabilities before adding new packages. Pin versions in production.

## Rule 7: Code Reviews Required
All T2+ code changes require peer review before deployment. AI-generated code is subject to the same review standards as human-written code.

## Rule 8: Testing Required
All production code must have tests. Minimum: unit tests for business logic, integration tests for API endpoints. Coverage target: 80% for new code.

## Rule 9: Documentation
All public APIs must have documentation (OpenAPI/Swagger). Complex business logic must have inline comments explaining WHY, not WHAT.

## Rule 10: Performance Awareness
Consider performance implications of generated code. Avoid N+1 queries, unbounded loops, and excessive memory allocation. Use pagination for list endpoints.
