1. **Modify `_fetch_all_for_device` in `src/hyxi_cloud_api/api.py`**
   - We will change the check around `ems_task` creation to ensure we only call `query_ems_basic_details` when the device is an EMS/ESS device.
   - We will introduce `is_ems_device = dev_type in ("EMS", "ENERGY_STORAGE_BATTERY", "MICRO_STORAGE_ALL_IN_ONE", "15", "16")` before creating the task.
   - We will append the `ems_task` to `tasks` only if `is_ems_device` is true.

2. **Update Tests in `tests/test_api.py` and `tests/test_metrics_errors.py`**
   - Many tests use `INVERTER` as `dev_type` and assert that `query_ems_basic_details` was called. These will need to be updated to use `"EMS"` as `dev_type` to pass after the optimization.
   - Example: `test_fetch_ems_basic_data_success`, `test_fetch_ems_basic_data_no_data`, `test_fetch_all_for_device_non_collector`, `test_query_ems_basic_details_error`, etc.
   - Check all tests that mock or assert on `query_ems_basic_details` and ensure they are updated to use an EMS dev type when testing the call. Add assertions for non-EMS devices to explicitly ensure `query_ems_basic_details` is *not* called.

3. **Verify Optimization & Tests**
   - Use `sed` to verify the modified codebase.
   - Use `pytest` to run tests.

4. **Complete pre-commit steps**
   - We will complete the pre-commit steps by ensuring testing, verifications, reviews and reflections are done.
