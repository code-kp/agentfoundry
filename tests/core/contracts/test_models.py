import unittest

import core.contracts.models as contract_models


class ModelContractsTest(unittest.TestCase):
    def test_serialized_model_catalog_hides_raw_model_names(self) -> None:
        payload = contract_models.serialize_available_models()

        self.assertTrue(payload)
        self.assertTrue(all(item["id"].startswith("mdl_") for item in payload))
        self.assertTrue(all("model_name" not in item for item in payload))

    def test_resolve_model_selection_maps_model_id_to_runtime_name(self) -> None:
        selected = contract_models.available_models()[0]

        resolved = contract_models.resolve_model_selection(model_id=selected.id)

        self.assertEqual(resolved, selected.model_name)

    def test_public_model_label_maps_known_model_aliases(self) -> None:
        label = contract_models.public_model_label("openai/gpt-4o-mini")

        self.assertEqual(label, "GPT-4o Mini")

    def test_resolve_model_selection_rejects_unknown_model_id(self) -> None:
        with self.assertRaises(ValueError):
            contract_models.resolve_model_selection(model_id="mdl_missing")


if __name__ == "__main__":
    unittest.main()
