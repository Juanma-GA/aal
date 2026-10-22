# PROJECT_CONTEXT.md

## Organization
Atexis — IT department managing AI-assisted development platform.

## Platform Overview
The AI Management Platform (IdAI) provides centralized governance, deployment, and monitoring for all AI-assisted development initiatives within the organization.

## Key Systems
- **Admin Console**: Central management UI (React + FastAPI)
- **IdAI App**: Initiative governance frontend (React + shadcn/ui)
- **MCP Platform**: Model Context Protocol servers for tool integration
- **ToolHive**: Tool gateway with Cedar policy engine
- **Keycloak**: Identity and access management
- **Inference Stack**: Local LLM inference (Ollama + vLLM on RTX 4090)

## Tier System
- **T1 (Self-Service)**: IDE coding assistants, no sensitive data
- **T2 (IS-Approved)**: Internal tools, shared infrastructure
- **T3 (IS + Data)**: Data warehouse access, dedicated VMs
- **T4 (IS + IT + Production)**: Production systems, joint deployment

## Data Classification
- **Public**: No restrictions
- **Internal**: Organization-internal only
- **Confidential**: Need-to-know basis, encrypted
- **Strictly Confidential**: Maximum controls, isolated processing

## Infrastructure
- **APP024**: Primary AI inference server (RTX 4090, 60GB RAM, Ubuntu 24.04)
- **Docker**: All services containerized
- **Networking**: Internal network only, HTTPS/TLS everywhere
- **Auth**: Keycloak OIDC with role-based access

## Teams
- **IS (Information Security)**: Policy, compliance, reviews
- **IT Infrastructure**: Provisioning, networking, monitoring
- **Development**: Building and deploying AI tools
- **Business Units**: Consumers of AI capabilities
