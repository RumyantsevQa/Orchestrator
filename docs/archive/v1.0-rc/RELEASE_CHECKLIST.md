# QASkills v1.0 RC Release Checklist

Date: 2026-07-23  
Release state: QASkills v1.0 Release Candidate (`1.0 RC`)  
Repository: QASkills product repository

Status legend:

- `[PASS]` verified by command output or direct inspection;
- `[DONE]` artifact exists and matches the current release scope;
- `[MANUAL]` requires human confirmation;
- `[ACTION REQUIRED]` blocks public GitHub Release publication.

## Release Gates

| Gate | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Technical interview demonstration | `[PASS]` | `./qaskills doctor`, `./qaskills ask ...`, `./qaskills demo`, `28 tests OK` | Ready to demonstrate with known limitations. |
| Public GitHub Release publication | `[ACTION REQUIRED]` | `git status --short` shows dirty working tree | Requires owner review, commit, and tag before publication. |

## Documentation

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| README | `[DONE]` | `README.md` reviewed | Describes current source-first product scope. |
| Demo script | `[DONE]` | `demo.md` exists | Provides a five-minute employer demo script. |
| Test Report | `[DONE]` | `TEST_REPORT.md` created | Includes QA scope, defects, retests, regression, and release recommendation. |
| Known Limitations | `[DONE]` | `KNOWN_LIMITATIONS.md` created | Documents current limitations and practical impact. |
| Release Checklist | `[DONE]` | `RELEASE_CHECKLIST.md` created | Tracks demo and publication gates separately. |
| Release Notes | `[DONE]` | `RELEASE_NOTES_v1.0.md` created | Prepared for v1.0 RC release communication. |

## Testing

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Full regression | `[PASS]` | `python3 -m unittest` -> `28 tests OK` | Automated regression passed. |
| CLI tests | `[PASS]` | Included in `python3 -m unittest` | Covers Source Pack behavior and no-match behavior. |
| Application pipeline tests | `[PASS]` | Included in `python3 -m unittest` | Covers local memory flows without LLM. |
| IndexManager tests | `[PASS]` | Included in `python3 -m unittest` | Covers metadata index persistence and filters. |
| MemoryService tests | `[PASS]` | Included in `python3 -m unittest` | Covers document listing, reading, recent documents, and structure. |
| QAS-CLI-001 retest | `[PASS]` | CLI no-match checks and CLI regression tests | Duplicate no-match header fixed and verified. |
| QAS-CLI-002 retest | `[PASS]` | Natural-language structure command and pipeline tests | Noisy Vault structure output fixed and verified. |

## Compilation

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Python compile check | `[PASS]` | `python3 -m py_compile main.py qaskills app/index/manager.py app/index/models.py app/services/memory.py app/response/composer.py tests/test_cli.py tests/test_application_pipeline.py` | Key entrypoints, implementation files, and tests compile. |

## CLI

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Start screen | `[PASS]` | `./qaskills` | Displays product header and local readiness summary. |
| Help | `[PASS]` | `./qaskills help` | Commands are grouped by product area. |
| Status | `[PASS]` | `./qaskills status` | Shows Vault, Index, document count, Search, and Answer Mode. |
| Doctor | `[PASS]` | `./qaskills doctor` | Ends with `Everything is ready`. |
| Search | `[PASS]` | `./qaskills find architecture` | Returns ranked metadata results. |
| Ask / Source Pack | `[PASS]` | `./qaskills ask Что мы решили про архитектуру` | Returns overview, key sources, grouped sources, and reading order. |
| Demo | `[PASS]` | `./qaskills demo` | Completes successfully. |
| No-match handling | `[PASS]` | `find` and `ask` no-match checks | Controlled messages and suggestions are shown. |
| Open negative path | `[PASS]` | `./qaskills open`, `./qaskills open zzz-no-such-document-123` | Safe negative behavior verified. |
| Open positive GUI path | `[MANUAL]` | Not automated | Check manually before showing `open` live. |
| Sample Vault fallback | `[PASS]` | `./qaskills doctor`, `./qaskills demo` without Vault env | Public clone can run immediately with repository sample knowledge. |
| Real Vault mode | `[PASS]` | `QASKILLS_MEMORY_VAULT_PATH=... ./qaskills demo` | Configured Obsidian Vault demo passed with `478` indexed documents. |

## README

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Product positioning | `[DONE]` | README review | Local-first, source-first product scope is documented. |
| Capabilities | `[DONE]` | README review | Current commands and metadata index behavior are documented. |
| Out-of-scope promises | `[PASS]` | Release-contract scan | No outdated AI/RAG/Jira/Browser/Calendar promises found in user-facing files. |
| Demo reference | `[DONE]` | README links to `demo.md` | Demo script is discoverable. |

## Demo

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Automatic demo | `[PASS]` | `./qaskills demo` | Demo-critical command passes. |
| Five-minute script | `[DONE]` | `demo.md` | Ready for interview preparation. |
| Presenter rehearsal | `[MANUAL]` | Human action | Rehearse once in the target terminal window before the interview. |

## Version

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| CLI version | `[PASS]` | CLI header displays `1.0 RC` | Runtime version label is consistent. |
| Documentation version | `[DONE]` | Release docs use v1.0 RC wording | Current state is Release Candidate. |
| Public tag name | `[MANUAL]` | Owner decision required | Decide whether final publication uses `v1.0`, `v1.0-rc1`, or another convention. |

## Git

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Branch | `[PASS]` | `git branch --show-current` -> `main` | Current branch observed. |
| HEAD | `[PASS]` | `git rev-parse --short HEAD` -> `21c5aa5` | Current committed base observed before documentation. |
| Working tree | `[ACTION REQUIRED]` | `git status --short` shows modified and untracked files | Must be reviewed before public release. |
| Commit | `[ACTION REQUIRED]` | No release commit created in this pass | Required for GitHub Release publication. |
| Tag | `[ACTION REQUIRED]` | No v1.0 tag created in this pass | Required for GitHub Release publication. |
| Staged diff review | `[MANUAL]` | Human action | Stage only intended files and inspect `git diff --staged`. |
| Secret / personal data review | `[MANUAL]` | Human action | Confirm no sensitive content is staged before commit. |

## Release Notes

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Release Notes artifact | `[DONE]` | `RELEASE_NOTES_v1.0.md` | Prepared for v1.0 RC communication. |
| Owner review | `[MANUAL]` | Human action | Review before GitHub publication. |

## Known Limitations

| Section | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Limitations artifact | `[DONE]` | `KNOWN_LIMITATIONS.md` | Current limitations and practical impacts are documented. |
| Interview disclosure | `[MANUAL]` | Human action | Decide which limitations to mention verbally during the demo. |

## Final Gate

| Decision | Status | Confirmation | Comment |
| --- | --- | --- | --- |
| Use for technical interviews | `[PASS]` | QA evidence and demo-critical checks | Ready with documented limitations. |
| Publish GitHub Release | `[ACTION REQUIRED]` | Dirty working tree, no release commit, no tag | Complete Git review, commit, and tag first. |
