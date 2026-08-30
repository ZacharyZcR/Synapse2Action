from __future__ import annotations

import unittest

from synapse2action.contracts import RESULT_SCHEMA_VERSION, SCHEMA_VERSION
from synapse2action.schemas import CONTRACT_SCHEMAS, contract_catalog


class ContractSchemaTests(unittest.TestCase):
    def test_catalog_contains_all_pre_simulation_boundaries(self) -> None:
        self.assertEqual(
            set(CONTRACT_SCHEMAS),
            {"intent", "world_state", "plan", "skill", "action", "result"},
        )
        for name, schema in CONTRACT_SCHEMAS.items():
            self.assertFalse(schema["additionalProperties"])
            expected_version = RESULT_SCHEMA_VERSION if name == "result" else SCHEMA_VERSION
            self.assertEqual(schema["properties"]["schema_version"]["const"], expected_version)

    def test_catalog_returns_an_isolated_copy(self) -> None:
        first = contract_catalog()
        first["schemas"]["intent"]["required"].clear()

        second = contract_catalog()

        self.assertTrue(second["schemas"]["intent"]["required"])
        self.assertEqual(second["format"], "synapse2action.contract_catalog")

    def test_result_schema_separates_outcome_process_and_safety(self) -> None:
        result = CONTRACT_SCHEMAS["result"]

        self.assertTrue(
            {"outcome_success", "process_compliance", "safety_passed"}
            <= set(result["required"])
        )


if __name__ == "__main__":
    unittest.main()
