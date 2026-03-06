# API Package Docs Policy

This folder is for package-local operational documentation only.

## Source of Truth

Normative architecture and contract docs live at repository root under `/docs`.

Use these as canonical references:

- `/docs/PLATFORM_VISION_v0.2.md`
- `/docs/DEPLOYMENT_MODEL_v0.1.md`
- `/docs/EVENT_MODEL_v0.2.md`
- `/docs/API_CONTRACT_v0.1.md`
- `/docs/WEB_ARCHITECTURE_v0.1.md`
- `/docs/DEVELOPMENT.md`

## Allowed Content in This Folder

- Local runbooks (container build/run, K8s apply/checks)
- Package-specific operational notes
- Troubleshooting procedures tied to this package

## Not Allowed in This Folder

- Parallel API contracts
- Alternative event model definitions
- Duplicate platform architecture/requirements documents
- Competing "current state" specifications

If behavior or contracts change, update root `/docs` first.
