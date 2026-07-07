1. **Analyze the Issue:**
   - The issue highlights a security vulnerability in `_mask_id` located at `src/hyxi_cloud_api/api.py:913`.
   - The current implementation uses an unsalted SHA-256 hash to mask identifiers (like serial numbers).
   - This makes it susceptible to dictionary and brute-force attacks if log files are exposed.
   - The goal is to replace the unsalted hash with a salted hash using a session-specific salt.

2. **Propose the Fix:**
   - Import `secrets` in `src/hyxi_cloud_api/api.py` if not already imported.
   - Generate a session-specific salt (e.g., `_LOG_SALT = secrets.token_bytes(16)`) at the module level.
   - Update `_mask_id` to prepend this salt to the input string before hashing.
   - Since the salt is generated once per session (when the module is loaded), deterministic masking during a single run will be preserved, fulfilling the cross-device log correlation requirement.
   - Tests in `tests/test_mask_id.py` and `tests/test_sanitize_dict.py` may need updating if they hardcode expected hash outputs (which they do, currently, e.g., `expected = hashlib.sha256(sn.encode("utf-8")).hexdigest()[:8]`). We should update `test_normal_sn_is_masked_with_hash` to compute the expected hash using the dynamically generated `_LOG_SALT`.

3. **Verify the Fix:**
   - Run tests to ensure no regressions occur.
   - Confirm that `test_same_id_always_produces_same_output` still passes because `_LOG_SALT` is stable for the session.

4. **Complete Pre-commit Steps:**
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.

5. **Submit:**
   - Commit and submit with proper PR description.
