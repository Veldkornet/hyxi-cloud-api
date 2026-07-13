1. **Centralize EMS device types and avoid duplicate inline strings**
   - Add a constant `_EMS_DEVICE_TYPES = ("EMS", "ENERGY_STORAGE_BATTERY", "MICRO_STORAGE_ALL_IN_ONE", "15", "16")` near `_battery_device_types`.

2. **Fix `_fetch_all_for_device` to use `entry.get("device_type_code", dev_type)`**
   - Update `_fetch_all_for_device` to use `entry.get("device_type_code", dev_type)` for checking `is_ems_device` so it uses the authoritative source.
   - Example: `is_ems = entry.get("device_type_code", dev_type) in _EMS_DEVICE_TYPES`

3. **Update tests in `tests/test_api.py`**
   - Address "Comment 1": Add a test scenario (or extend `test_fetch_all_for_device_non_collector`) that explicitly tests when `dev_type` (and `entry['device_type_code']`) is an EMS type, checking that `api.query_ems_basic_details.assert_called_once_with(ems_sn)` is executed successfully.

4. **Run format, lint and tests**
5. **Complete pre-commit steps**
