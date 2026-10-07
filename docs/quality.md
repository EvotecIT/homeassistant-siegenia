# Integration rule ledger

This is Siegenia's self-assessment against the [Home Assistant rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/),
checked on 2026-10-05. It is an implementation checklist, not an official rating.
The current index contains 54 rules. Every row stays open until the complete
applicable contract has evidence; a source pointer alone is not a pass.

`Partial` identifies existing implementation or focused proof. `Gap` identifies
known missing work. `Review` requires an applicability or contract audit. An
exemption needs the rule's permitted reason and product-specific evidence.

## Bronze

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| action-setup | Implemented | Actions register before device connection and validate targets/parameters. WebSocket tests reject invalid inputs without device writes; a script test exercises the documented single-entity target form. |
| appropriate-polling | Partial | Motion, idle, push, heartbeat, and rediscovery intervals exist; measure request budgets and concurrent-device behaviour. |
| brands | Partial | Local `brand/` assets exist; verify rendered HACS/HA assets and applicable custom-integration requirements. |
| common-modules | Partial | Bundled client and coordinator own shared behaviour; consolidate repeated device metadata only where it serves real platform consumers. |
| config-flow-test-coverage | Implemented | 29 real HA flow tests cover all 149 executable statements and 32 branches in `config_flow.py`: setup, duplicate identity, authentication/connection failures, retry, reauthentication identity, both connection-change routes, legacy host identities, and discovery/options persistence. Unused YAML-import and menu-fallback paths were removed. Installed UI qualification remains separate. |
| config-flow | Partial | Manual setup, options, and reauthentication exist; prove the installed UI path and discovery applicability. |
| dependency-transparency | Review | Document bundled client ownership, transport, and requirements from the shipped manifest. |
| docs-actions | Partial | services.yaml and automation documentation exist; exercise each action and explain failure behaviour. |
| docs-triggers | Partial | State-change trigger regression exists; verify each exposed trigger and duration option. |
| docs-conditions | Partial | State-condition regression evaluates true and false outcomes; verify each exposed condition and documentation. |
| docs-high-level-description | Partial | README describes controller support; reconcile claims with tested models and firmware. |
| docs-installation-instructions | Partial | README installation path exists; install the actual HACS artifact. |
| docs-removal-instructions | Review | Verify entry removal and HACS uninstall guidance, including retained data. |
| entity-event-setup | Partial | Push/motion timers are cancelled during unload; late-update tests run with real HA cleanup verification. |
| entity-unique-id | Partial | Serial-based identities and registry migration exist; verify rename, reconnect, migration, and duplicate-entry stability. |
| has-entity-name | Partial | Platforms declare entity naming; verify translated primary and child names in the actual HA host. |
| runtime-data | Partial | Typed config-entry runtime_data owns the coordinator across platforms and diagnostics; setup/unload tests cover the shared owner. |
| test-before-configure | Partial | Setup flow connects, authenticates, and reads device identity; verify every failure and cleanup path. |
| test-before-setup | Partial | Setup validates connection and identity, with explicit offline-startup behaviour; verify retry/authentication distinctions. |
| unique-config-entry | Partial | Serial/host duplicate checks exist; test changed addresses and cached serial identities. |

## Silver

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| action-exceptions | Partial | Coordinator converts client failures into HA errors. Invalid targets, malformed durations, connection fields, and registry boolean flags have regressions; complete translated-error and offline-device qualification. |
| config-entry-unloading | Partial | Failed unload retains the coordinator; successful unload cancels tasks, timers, and connections. Extend repeated-reload proof. |
| docs-configuration-parameters | Partial | Configuration guide exists; reconcile all options, defaults, ranges, and effects. |
| docs-installation-parameters | Partial | Configuration guide exists; reconcile setup fields, credentials, and network prerequisites. |
| entity-unavailable | Partial | Coordinator drives availability; verify offline startup, disconnect, recovery, and dependent entities. |
| integration-owner | Partial | Manifest names maintainers and issue tracker; confirm support and security-reporting paths. |
| log-when-unavailable | Implemented | The real HA coordinator outage test verifies three failed refreshes emit one fetch error, mark the cover unavailable, and emit one recovery message after successful refresh. Physical connection timing remains part of device qualification. |
| parallel-updates | Implemented | All eight platforms explicitly set `PARALLEL_UPDATES = 0`. The coordinator centralizes state updates; the WebSocket client correlates overlapping action/read responses by request ID. `test_concurrent_requests_receive_their_own_out_of_order_responses` exercises the actual request and receiver paths with reversed replies. Actions remain concurrent so a pending request does not delay a cover stop. Physical-device request budgets remain tracked under appropriate-polling. |
| reauthentication-flow | Partial | Real HA flow tests cover authentication/connection failures, wrong or missing known serials, unchanged saved credentials on failure, cleanup, and successful retry with one reload. Reauthentication shares the reconfiguration host-fallback identity policy. Historical hostname-fallback ambiguity and installed UI/device proof remain open. |
| test-coverage | Gap | The 120-test coverage baseline covers 1,843 of 2,160 production statements (85.3%; 81% combined statement/branch coverage). The subsequent handshake-cancellation regression is validated separately. Config flow and optional buttons have full statement and branch coverage. Services, coordinator recovery/discovery, and client failure paths remain below the above-95% module target. |

## Gold

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| devices | Partial | Typed metadata and supported registry helpers group entities; verify model variants and migration on installed artifacts. |
| diagnostics | Partial | Privacy and nonmutation tests pass; inspect the downloaded artifact and all supported model payloads. |
| discovery-update-info | Partial | Opt-in network rediscovery updates the host while preserving serial identity. Probe tests cover matching, wrong/missing serial, and offline candidates: shared-session injection, disconnect, and preservation of saved configuration/rejected device metadata. Shutdown cancellation has separate tests; scan budgets and physical-network discovery remain open. |
| discovery | Review | Assess applicability of protocol-native discovery versus the opt-in subnet rediscovery path. |
| docs-data-update | Review | Document polling, push updates, motion/idle changes, heartbeat, and rediscovery delays. |
| docs-examples | Partial | Automation guide exists; validate examples against current entities/actions. |
| docs-known-limitations | Review | Document firmware/model restrictions, TLS settings, offline startup, and maintenance-action limits. |
| docs-supported-devices | Partial | Device support guide exists; distinguish tested hardware from protocol-based expectations. |
| docs-supported-functions | Partial | Feature checklist exists; reconcile platforms and per-model capability gating. |
| docs-troubleshooting | Review | Cover connection, authentication, discovery, diagnostics, and recovery with actionable steps. |
| docs-use-cases | Partial | Automation examples exist; verify complete user workflows. |
| dynamic-devices | Review | Verify applicability for one local device/system per entry and document any permitted exemption. |
| entity-category | Partial | Entity metadata exists; audit configuration and diagnostic categories across platforms. |
| entity-device-class | Partial | Sensor metadata exists; audit classes, units, and state classes across models. |
| entity-disabled-by-default | Partial | Real HA button-service tests verify controls are absent by default, opt-in exposes all six commands, and the opening lock blocks opening while preserving stop. Diagnostic sensor defaults and installed UI qualification remain open. |
| entity-translations | Partial | Platform translation keys and four locale files exist; audit completeness and rendered fallback behaviour. |
| exception-translations | Implemented | All 11 integration-owned action exceptions carry HA translation metadata, with English, Polish, German, and French messages. Real HA translation-loader tests cover every key; WebSocket action tests verify invalid-mode placeholders and duration error metadata before device writes. Installed frontend rendering remains part of runtime qualification. |
| icon-translations | Review | Audit state-aware icons and current HA translation metadata. |
| reconfiguration-flow | Partial | Dedicated Reconfigure and Connection options share connection/authentication and known-serial validation. Failure/retry tests preserve data and reload once; repeated edits preserve host-fallback identity. Historical hostname-fallback entries moved before identity metadata existed remain ambiguous. Installed UI and physical-device proof remain open. |
| repair-issues | Partial | Coordinator uses HA repair issues; verify create, recover, dismiss, and user guidance. |
| stale-devices | Partial | Device migration and cleanup services exist; verify scope, entity preservation, and removal rules. |

## Platinum

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| async-dependency | Partial | Bundled WebSocket client is async; inspect connection, heartbeat, cancellation, and reconnect ownership. |
| inject-websession | Partial | Coordinator and flow inject HA sessions. Six real local WebSocket tests in `tests/test_client_transport.py` verify pending-request failure on disconnect and session ownership after disconnect, a rejected handshake, or handshake cancellation: owned sessions close, borrowed sessions remain open. The same client completes a device read after a rejected handshake and after disconnecting a pending request, reusing borrowed sessions and replacing closed owned sessions. Coordinator retry tests verify failed or cancelled login closes the partial connection before a fresh login and heartbeat. Automatic scheduling and discovery lifetime qualification remain open. |
| strict-typing | Partial | Strict mypy 2.4.0 covers all 21 production modules and bundled client. A documented exception covers the HA StaticPathConfig typed re-export only. PEP 561 markers and thin type re-exports expose the standalone client to installed consumers. Strict consumer checks and HA-free runtime imports pass on Python 3.12/3.14; CI checks the installed contract in every lane. Published-release qualification remains open. |

## Qualification beyond the rule ledger

- [x] 123 tests pass on HA 2024.8.0/Python 3.12 and HA 2026.9.4/Python 3.14.
- [ ] Install the published artifact and upgrade from the previous stable release.
- [x] Bundle all eight dashboard icons inside the HACS component and Python wheel; HTTP tests verify byte-identical SVG delivery on minimum and current HA without a configured device. Published HACS installation remains unverified.
- [ ] Verify real model/firmware behaviour, resource use, reconnection, and supported actions.
- [ ] Record release version, commit, artifact identity, environment, and evidence date.

The [development guide](development.md) describes the current focused proof. A completed
row must link the relevant test, artifact, or runtime evidence and state its limits.
