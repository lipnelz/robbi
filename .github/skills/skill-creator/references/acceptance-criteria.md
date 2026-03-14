# Skill Creator Acceptance Criteria

**Skill**: `skill-creator`
**Purpose**: Guide for creating effective skills for AI coding agents
**Focus**: SKILL.md format, YAML frontmatter, bundled resources, Azure SDK patterns

---

## 1. SKILL.md Structure

### 1.1 ✅ CORRECT: Complete SKILL.md with Frontmatter

```markdown
---
name: azure-example-py
description: |
  Azure Example SDK for Python. Use for creating and managing examples.
  Triggers: "create example", "list examples", "azure example sdk".
---

## 2. Checklist for New Skills

### Frontmatter
- [ ] Has `name` field with correct format (e.g., `azure-example-py`)
- [ ] Has `description` with what it does AND when to use it
- [ ] Description includes trigger phrases

### Structure
- [ ] SKILL.md under 500 lines
- [ ] Follows section order: Install → Env → Auth → Core → Features → References
- [ ] Large content split into `references/` files

### Authentication
- [ ] Uses `DefaultAzureCredential` (never hardcoded)
- [ ] Shows environment variable configuration
- [ ] Includes cleanup/close in examples

### Quality
- [ ] No README.md, CHANGELOG.md, or meta-docs
- [ ] All code examples are complete and runnable
- [ ] References organized by feature, not by length
- [ ] Instructs to search `microsoft-docs` MCP for current APIs

### Naming
- [ ] Uses lowercase with hyphens
- [ ] Has language suffix (`-py`, `-dotnet`, `-ts`, `-java`) unless cross-language
- [ ] Matches existing naming conventions in repository