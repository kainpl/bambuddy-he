# AutoQueue routing acceptance tests

The accepted design defines A1–A57. These are executable test selectors in this branch. A Python selector without a parameter suffix runs every parameter case; a frontend selector is its file and exact test title (`vitest run FILE -t TITLE`). Device transport and acknowledgements are mocked. This matrix does not claim hardware verification or establish the historical row contents on the affected farm.

| Criterion | Test selectors |
| --- | --- |
| A1 | `backend/tests/unit/services/test_filament_routing_reader.py::test_single_nozzle_models_use_shared_model_normalization`<br>`backend/tests/integration/test_filament_routing_policy_flows.py::test_auto_rule_survives_deleted_origin_without_relaxing_model` |
| A2 | `backend/tests/integration/test_filament_routing_acceptance.py::test_incompatible_first_printer_is_skipped_for_a_compatible_candidate` |
| A3 | `backend/tests/unit/services/test_filament_routing.py::test_global_strict_without_overrides_and_relaxed_zero_colour_matches`<br>`backend/tests/integration/test_filament_routing_dispatch.py::test_auto_intake_tick_and_publish_sparse_external` |
| A4 | `backend/tests/integration/test_filament_routing_dispatch.py::test_auto_intake_tick_and_publish_sparse_external` |
| A5 | `backend/tests/unit/services/test_filament_routing.py::test_single_external_cannot_satisfy_two_inputs` |
| A6 | `backend/tests/unit/services/test_filament_routing.py::test_flexible_channel_cannot_take_only_source_of_strict_channel` |
| A7 | `backend/tests/unit/services/test_filament_routing.py::test_no_channel_merge_even_for_same_colour` |
| A8 | `backend/tests/integration/test_filament_routing_acceptance.py::test_relaxed_body_with_pinned_support_still_requires_both_materials` |
| A9 | `backend/tests/unit/services/test_filament_routing.py::test_sparse_external_serializes_padding_without_enabling_ams`<br>`backend/tests/integration/test_filament_routing_dispatch.py::test_auto_intake_tick_and_publish_sparse_external` |
| A10 | `backend/tests/unit/services/test_filament_routing.py::test_pinned_sources_are_not_remapped_and_unknown_legacy_colour_needs_review`<br>`backend/tests/unit/services/test_filament_routing.py::test_single_external_cannot_satisfy_two_inputs` |
| A11 | `backend/tests/integration/test_project_filament_routing.py::test_project_ambiguous_source_refuses_all_rows_before_any_writer`<br>`backend/tests/integration/test_filament_routing_acceptance.py::test_unreadable_head_does_not_block_later_valid_auto_job`<br>`backend/tests/integration/test_filament_routing_acceptance.py::test_only_raw_gcode_or_server_calibration_is_exempt_from_normal_preflight` |
| A12 | `backend/tests/integration/test_project_filament_routing.py::test_project_whole_file_retains_actual_plate_and_line`<br>`backend/tests/unit/services/test_filament_routing_reader.py::test_whole_file_resolves_actual_single_plate` |
| A13 | `backend/tests/unit/services/test_filament_routing_reader.py::test_explicit_plate_overrides_hint_and_never_falls_back`<br>`backend/tests/integration/test_filament_routing_preview.py::test_preview_missing_plate_is_unavailable_not_fallback` |
| A14 | `backend/tests/unit/services/test_filament_routing_reader.py::test_zero_tiny_usage_and_unknown_colour_stay_distinct`<br>`backend/tests/unit/services/test_filament_routing_reader.py::test_unknown_or_invalid_usage_refuses_entire_plate` |
| A15 | `backend/tests/unit/services/test_filament_routing.py::test_flexible_channel_cannot_take_only_source_of_strict_channel` |
| A16 | `backend/tests/unit/services/test_filament_routing.py::test_known_variant_mismatch_is_not_relaxed_by_colour_policy` |
| A17 | `backend/tests/integration/test_filament_routing_dispatch.py::test_publish_boundary_catches_change_after_final_preflight`<br>`backend/tests/integration/test_filament_dispatch_lifecycle.py::test_late_refusal_restores_source_and_does_not_count_a_print` |
| A18 | `backend/tests/unit/services/test_printer_feed_snapshot.py::test_partial_update_retains_fields_but_new_generation_does_not`<br>`backend/tests/unit/services/test_printer_feed_snapshot.py::test_real_mqtt_parser_records_top_level_ams_and_ignores_calibration_diameter`<br>`backend/tests/unit/services/test_printer_feed_snapshot.py::test_external_report_alone_cannot_authorize_no_ams_wire_encoding` |
| A19 | `backend/tests/integration/test_filament_routing_dispatch.py::test_dual_topology_and_real_mqtt_wire` |
| A20 | `backend/tests/unit/services/test_filament_routing.py::test_single_nozzle_does_not_mix_ams_and_external` |
| A21 | `backend/tests/integration/test_filament_routing_acceptance.py::test_incompatible_first_printer_is_skipped_for_a_compatible_candidate` |
| A22 | `backend/tests/integration/test_auto_queue_scheduler.py::TestRoutingIsNotDispatching::test_a_gated_printer_still_receives_the_work`<br>`backend/tests/integration/test_auto_queue_scheduler.py::TestAutoQueueDryingPriority::test_idle_printer_preferred_over_drying`<br>`backend/tests/integration/test_filament_routing_preview.py::test_compatible_printer_with_pending_work_is_not_ready` |
| A23 | `backend/tests/integration/test_filament_routing_policy_flows.py::test_pinned_edit_to_another_printer_requires_an_explicit_mapping_answer` |
| A24 | `backend/tests/integration/test_auto_queue_plate_quantities.py::test_each_plate_gets_the_count_it_was_given`<br>`backend/tests/unit/services/test_filament_routing_reader.py::test_dual_bindings_are_plate_scoped_for_every_supported_model` |
| A25 | `backend/tests/integration/test_filament_routing_policy_flows.py::test_auto_intake_refuses_slot_rules_from_a_different_file`<br>`frontend/src/__tests__/components/QueueSequencerCarry.test.tsx::⚠️ a member whose plates can never answer shows itself instead of hanging` |
| A26 | `backend/tests/integration/test_filament_dispatch_lifecycle.py::test_late_refusal_restores_source_and_does_not_count_a_print` |
| A27 | `backend/tests/integration/test_filament_routing_preview.py::test_preview_respects_source_ownership_and_printer_read_permission` |
| A28 | `backend/tests/unit/services/test_filament_routing.py::test_explicit_external_only_works_even_with_ams`<br>`backend/tests/unit/services/test_filament_policy.py::test_legacy_feed_policy` |
| A29 | `backend/tests/unit/services/test_filament_policy.py::test_migration_is_database_only_and_repeatable`<br>`backend/tests/integration/test_filament_routing_virtual_printer.py::test_virtual_printer_intake_and_late_options_preserve_exact_plate_and_feed` |
| A30 | `backend/tests/integration/test_filament_routing_policy_flows.py::test_auto_rule_survives_deleted_origin_without_relaxing_model`<br>`backend/tests/unit/services/test_filament_policy.py::test_unknown_or_malformed_snapshot_is_closed` |
| A31 | `backend/tests/unit/services/test_filament_policy.py::test_auto_global_color_policy_survives_without_overrides`<br>`backend/tests/integration/test_filament_routing_dispatch.py::test_auto_intake_tick_and_publish_sparse_external` |
| A32 | `backend/tests/unit/services/test_filament_policy.py::test_old_pinned_row_without_evidence_requires_review`<br>`backend/tests/integration/test_filament_routing_virtual_printer.py::test_virtual_printer_intake_and_late_options_preserve_exact_plate_and_feed`<br>`frontend/src/__tests__/components/AutoModeRouting.test.tsx::keeps relaxed default and emits an explicit feed policy` |
| A33 | `backend/tests/integration/test_auto_queue_plate_quantities.py::test_each_plate_gets_the_count_it_was_given` |
| A34 | `frontend/src/__tests__/components/QueueSequencerCarry.test.tsx::⚠️ queues every member of the group, with the printer the operator picked`<br>`frontend/src/__tests__/components/AutoModeRouting.test.tsx::keeps relaxed default and emits an explicit feed policy` |
| A35 | `backend/tests/integration/test_filament_routing_acceptance.py::test_body_color_pin_keeps_relaxed_support_material_and_wrong_nozzle_is_refused` |
| A36 | `frontend/src/__tests__/components/QueueSequencerGroups.test.tsx::asks about every file after a file-local color or physical mapping answer` |
| A37 | `backend/tests/integration/test_filament_routing_policy_flows.py::test_api_edit_clone_retry_preserves_auto_and_slot_rules`<br>`backend/tests/integration/test_repeat_print.py::test_repeat_retains_rules_and_original_archive_after_execution_rewrite` |
| A38 | `backend/tests/integration/test_filament_routing_preview.py::test_compatible_printer_with_pending_work_is_not_ready`<br>`frontend/src/__tests__/components/AutoModeRouting.test.tsx::shows separate hardware groups and compatibility versus readiness`<br>`frontend/src/__tests__/components/AutoModeRouting.test.tsx::waits for source requirements and keeps an explicit false when an older preview arrives late` |
| A39 | `backend/tests/integration/test_filament_routing_preview.py::test_preview_monitoring_failure_keeps_valid_source_queueable`<br>`frontend/src/__tests__/components/AutoModeRouting.test.tsx::queues a valid source with unavailable live compatibility and keeps the selected color rule` |
| A40 | `frontend/src/__tests__/components/AutoModeRouting.test.tsx::waits for source requirements and keeps an explicit false when an older preview arrives late` |
| A41 | `backend/tests/integration/test_project_filament_routing.py::test_five_external_p1p_project_jobs_produce_five_safe_commands` |
| A42 | `backend/tests/integration/test_project_filament_routing.py::test_project_whole_file_retains_actual_plate_and_line` |
| A43 | `backend/tests/integration/test_project_filament_routing.py::test_project_ambiguous_source_refuses_all_rows_before_any_writer` |
| A44 | `backend/tests/integration/test_filament_routing_dispatch.py::test_dual_topology_and_real_mqtt_wire`<br>`backend/tests/unit/services/test_filament_routing_reader.py::test_legacy_wrapper_keeps_nozzles_and_tiny_used_channels` |
| A45 | `backend/tests/unit/services/test_filament_routing.py::test_all_dual_models_keep_mixed_bindings`<br>`backend/tests/integration/test_filament_routing_acceptance.py::test_body_color_pin_keeps_relaxed_support_material_and_wrong_nozzle_is_refused` |
| A46 | `backend/tests/unit/services/test_filament_routing_reader.py::test_dual_bindings_are_plate_scoped_for_every_supported_model` |
| A47 | `backend/tests/integration/test_filament_dispatch_lifecycle.py::test_late_refusal_restores_source_and_does_not_count_a_print` |
| A48 | `backend/tests/integration/test_filament_routing_dispatch.py::test_defer_cas_never_revives_another_attempt`<br>`backend/tests/integration/test_filament_dispatch_lifecycle.py::test_late_refusal_restores_source_and_does_not_count_a_print` |
| A49 | `backend/tests/integration/test_filament_dispatch_lifecycle.py::test_late_refusal_restores_source_and_does_not_count_a_print` |
| A50 | `backend/tests/integration/test_filament_dispatch_lifecycle.py::test_late_refusal_restores_source_and_does_not_count_a_print`<br>`backend/tests/unit/services/test_spoolman_runout.py::TestAutoswitchPurgeGramsSpoolman::test_purge_lands_on_the_backup_segment`<br>`backend/tests/unit/services/test_usage_tracker_runout.py::TestAutoswitchPurgeGrams::test_purge_lands_on_the_backup_segment`<br>`backend/tests/unit/services/test_usage_tracker_runout.py::TestRunoutZeroPoint::test_boundary_events_suspend_live_reassignment`<br>`backend/tests/integration/test_filament_routing_acceptance.py::test_preflight_honors_lowest_setting_inventory_priority_and_backup_gate` |
| A51 | `backend/tests/integration/test_filament_routing_acceptance.py::test_only_raw_gcode_or_server_calibration_is_exempt_from_normal_preflight` |
| A52 | `backend/tests/integration/test_filament_requirements_full_slots.py::TestTheModalGetsEverySlot::test_full_slots_returns_one_row_per_project_slot`<br>`backend/tests/integration/test_filament_requirements_full_slots.py::TestThePrintPathKeepsTheNarrowList::test_without_the_flag_only_the_consumed_slot_comes_back` |
| A53 | `backend/tests/unit/services/test_printer_feed_snapshot.py::test_h2c_rack_nozzles_and_fts_use_physical_capabilities`<br>`backend/tests/unit/services/test_filament_routing_reader.py::test_h2c_group_table_returns_physical_extruder_not_rack_wire_id`<br>`backend/tests/unit/services/test_filament_routing_reader.py::test_single_active_nozzle_uses_file_configuration` |
| A54 | `backend/tests/unit/services/test_filament_policy.py::test_manual_mapping_outranks_legacy_boolean_and_captures_selected_color` |
| A55 | `backend/tests/unit/services/test_filament_requirements_cache.py::test_parse_count_scales_with_revision_and_plate_not_printers_or_copies` |
| A56 | `backend/tests/unit/services/test_filament_policy.py::test_migration_is_database_only_and_repeatable`<br>`backend/tests/integration/test_filament_routing_postgres.py::test_routing_migration_postgres_backfill_and_repeat` |
| A57 | `backend/tests/integration/test_project_filament_routing.py::test_project_whole_file_retains_actual_plate_and_line`<br>`backend/tests/integration/test_filament_routing_virtual_printer.py::test_virtual_printer_intake_and_late_options_preserve_exact_plate_and_feed`<br>`backend/tests/integration/test_filament_routing_policy_flows.py::test_api_edit_clone_retry_preserves_auto_and_slot_rules`<br>`backend/tests/unit/services/test_telegram_auto_queue_target.py::test_a_model_target_creates_an_auto_queue_item`<br>`backend/tests/integration/test_print_queue_api.py::TestBulkUpdateEndpoint::test_bulk_update_change_queue`<br>`backend/tests/integration/test_filament_routing_policy_flows.py::test_pinned_queue_intake_refuses_file_local_rules_for_an_unused_slot` |

## Running the checks

From the checkout root, use the project Python environment:

```powershell
python -m ruff check backend/
python -m ruff format --check backend/
python -m pytest backend/tests/ -n 8 --dist loadfile -q
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test:run
npm --prefix frontend run build
git diff --check
```

The routing PostgreSQL test starts bundled PostgreSQL in a new temporary cluster on a random local port, validates backfill and repeated execution, then stops it. It never reads the working farm database credentials. Other existing PostgreSQL tests requiring TEST_POSTGRES_URL remain separate opt-in tests; never point them at a working instance.

The five-printer project regression and public dispatch lifecycle matrix cover the production boundaries with mocked device I/O. The latter includes upload, preheat, calibration, source mutation, cancellation, deletion, competing claims, and success. It checks source restoration, aborted archive accounting, expected-print withdrawal, prevention of repeated upload on unchanged refusal, and repeat after transient-source cleanup.

The shared dual-model registry supplies parser and resolver cases. Real MQTT serialization is checked for every supported dual model/alias, with mixed AMS/external and dual external feeds. Private farm files are not repository fixtures.

## Verification record — 2026-09-10

Branch: `feature/auto-queue-filament-routing`, based on `76360196`; reader milestone `d7552d4f`. This records the final software acceptance before the implementation commit, without merging the operator's concurrent work.

| Check | Result |
| --- | --- |
| Full backend, `pytest backend/tests/ -n 8 --dist loadfile -q --tb=short` | 12877 passed, 141 skipped, 1 warning in 513.48s (0:08:33) |
| Full frontend, `npm run test:run` | 301 files passed; 3240 tests passed, 1 skipped |
| Real PostgreSQL scenarios, `test_postgres_scenarios.py` | 15 passed on a verified disposable cluster; cluster stopped afterward |
| Routing migration on PostgreSQL | Backfill and repeated migration covered by `test_routing_migration_postgres_backfill_and_repeat` in the full suite |
| Ruff lint and format check | Passed; 1526 Python files formatted |
| Frontend lint | Passed, zero errors; two existing hook-dependency warnings in GcodeViewer and ModelViewer |
| Frontend typecheck and en/uk parity | Passed |
| Production build | Passed; generated `static/` included; existing large-chunk warning remains |
| Acceptance map | A1–A57, 100 validated executable selectors |
| Graph and diff | `graphify update .` and `git diff --check` passed |

The normal backend run keeps environment-specific tests skipped; the 15 PostgreSQL scenarios above were then executed separately with `TEST_POSTGRES_URL` pointing only at a newly created temporary cluster. Its actual `SHOW data_directory` was checked against that temporary directory before running the scenarios. The working PostgreSQL database was never a write target.

A suite-order failure in the existing importability smoke test was reproduced before the fix: restoring `sys.modules` alone left the parent package pointing at a different module, so later string-based mocks patched the wrong database session factory. The test now restores both bindings. Importability followed by the four reprint regressions passes in the same order; the full run above includes the fix.

Raw logs and the disposable-cluster launcher remain local under `temp/routing-validation/`. Hardware smoke was **not run**: no operator-agreed print was started. Offline transport tests prove the command construction and lifecycle boundaries, not firmware behavior or the exact historical contents of the affected farm's queue. Merge, push and deployment are separate operations.
