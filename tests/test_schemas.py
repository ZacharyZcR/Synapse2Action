from __future__ import annotations

import unittest

from synapse2action.contracts import SCHEMA_VERSION
from synapse2action.schemas import CONTRACT_SCHEMAS, contract_catalog


class ContractSchemaTests(unittest.TestCase):
    def test_catalog_contains_all_pre_simulation_boundaries(self) -> None:
        self.assertEqual(
            set(CONTRACT_SCHEMAS),
            {"intent", "world_state", "plan", "skill", "action", "result"},
        )
        for schema in CONTRACT_SCHEMAS.values():
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(schema["properties"]["schema_version"]["const"], SCHEMA_VERSION)

    def test_catalog_returns_an_isolated_copy(self) -> None:
        first = contract_catalog()
        first["schemas"]["intent"]["required"].clear()

        second = contract_catalog()

        self.assertTrue(second["schemas"]["intent"]["required"])
        self.assertEqual(second["format"], "synapse2action.contract_catalog")


if __name__ == "__main__":
    unittest.main()
