"""Tests for framework.spec.models module."""

import pytest

from framework.spec.models import FieldSpec, ModelSpec, ModelsSpec, VariantSpec


class TestFieldSpec:
    """Tests for FieldSpec."""

    def test_simple_field(self) -> None:
        """Simple field with just type."""
        field = FieldSpec.from_yaml({"type": "int"})
        assert field.readonly is False
        assert field.default is None

    def test_field_with_constraints(self) -> None:
        """Field with numeric constraints."""
        field = FieldSpec.from_yaml({"type": "int", "ge": 0, "le": 100})
        assert field.ge == 0
        assert field.le == 100

    def test_readonly_field(self) -> None:
        """Readonly field."""
        field = FieldSpec.from_yaml({"type": "int", "readonly": True})
        assert field.readonly is True

    def test_field_with_default(self) -> None:
        """Field with default value."""
        field = FieldSpec.from_yaml({"type": "bool", "default": False})
        assert field.default is False

    def test_field_with_string_constraints(self) -> None:
        """Field with string constraints."""
        field = FieldSpec.from_yaml({"type": "string", "min_length": 1, "max_length": 255})
        assert field.min_length == 1
        assert field.max_length == 255

    def test_field_to_json_schema(self) -> None:
        """Field converts to JSON Schema."""
        field = FieldSpec.from_yaml({"type": "int", "ge": 0, "readonly": True})
        schema = field.to_json_schema()
        assert schema["type"] == "integer"
        assert schema["minimum"] == 0
        assert schema["readOnly"] is True

    def test_enum_field(self) -> None:
        """Enum field."""
        field = FieldSpec.from_yaml(
            {
                "type": {"type": "enum", "values": ["pending", "active"]},
            }
        )
        assert field.is_enum is True
        assert field.enum_values == ["pending", "active"]

    def test_list_field(self) -> None:
        """List field."""
        field = FieldSpec.from_yaml(
            {
                "type": {"type": "list", "of": {"type": "string"}},
            }
        )
        schema = field.to_json_schema()
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "string"

    def test_optional_field(self) -> None:
        """Field with optional: true becomes nullable."""
        field = FieldSpec.from_yaml({"type": "int", "optional": True})
        assert field.optional is True

    def test_optional_field_to_json_schema(self) -> None:
        """Optional field adds nullable: true to JSON schema."""
        field = FieldSpec.from_yaml({"type": "int", "optional": True})
        schema = field.to_json_schema()
        assert schema["type"] == "integer"
        assert schema["nullable"] is True

    def test_non_optional_field_no_nullable(self) -> None:
        """Non-optional field does not have nullable in schema."""
        field = FieldSpec.from_yaml({"type": "int"})
        schema = field.to_json_schema()
        assert "nullable" not in schema


class TestVariantSpec:
    """Tests for VariantSpec."""

    def test_empty_variant(self) -> None:
        """Empty variant (all fields included)."""
        variant = VariantSpec()
        assert variant.exclude == []
        assert variant.optional == []

    def test_variant_with_exclude(self) -> None:
        """Variant with excluded fields."""
        variant = VariantSpec(exclude=["id", "created_at"])
        assert "id" in variant.exclude

    def test_variant_with_optional(self) -> None:
        """Variant with optional fields."""
        variant = VariantSpec(optional=["name", "description"])
        assert "name" in variant.optional


class TestModelSpec:
    """Tests for ModelSpec."""

    def test_simple_model(self) -> None:
        """Simple model with fields."""
        model = ModelSpec.from_yaml(
            {
                "fields": {
                    "id": {"type": "int", "readonly": True},
                    "name": {"type": "string"},
                },
            }
        )
        assert "id" in model.fields
        assert "name" in model.fields

    def test_model_with_variants(self) -> None:
        """Model with variants."""
        model = ModelSpec.from_yaml(
            {
                "fields": {
                    "id": {"type": "int", "readonly": True},
                    "name": {"type": "string"},
                },
                "variants": {
                    "Create": {},
                    "Update": {"optional": ["name"]},
                },
            }
        )
        assert "Create" in model.variants
        assert "Update" in model.variants

    def test_variant_references_unknown_field_fails(self) -> None:
        """Variant referencing unknown field should fail."""
        with pytest.raises(ValueError, match="unknown field 'unknown'"):
            ModelSpec.from_yaml(
                {
                    "fields": {
                        "id": {"type": "int"},
                    },
                    "variants": {
                        "Create": {"exclude": ["unknown"]},
                    },
                }
            )

    def test_get_readonly_fields(self) -> None:
        """Get readonly fields."""
        model = ModelSpec.from_yaml(
            {
                "fields": {
                    "id": {"type": "int", "readonly": True},
                    "name": {"type": "string"},
                    "created_at": {"type": "datetime", "readonly": True},
                },
            }
        )
        readonly = model.get_readonly_fields()
        assert readonly == {"id", "created_at"}

    def test_get_variant_fields_excludes_readonly_for_create(self) -> None:
        """Create variant auto-excludes readonly fields."""
        model = ModelSpec.from_yaml(
            {
                "fields": {
                    "id": {"type": "int", "readonly": True},
                    "name": {"type": "string"},
                },
                "variants": {
                    "Create": {},
                },
            }
        )
        fields = model.get_variant_fields("Create")
        assert "id" not in fields
        assert "name" in fields

    def test_model_must_have_fields(self) -> None:
        """Model must have at least one field."""
        with pytest.raises(ValueError, match="at least one field"):
            ModelSpec.from_yaml({"fields": {}})


class TestModelsSpec:
    """Tests for ModelsSpec."""

    def test_load_models(self) -> None:
        """Load models from YAML dict."""
        spec = ModelsSpec.from_yaml(
            {
                "models": {
                    "User": {
                        "fields": {
                            "id": {"type": "int"},
                            "name": {"type": "string"},
                        },
                        "variants": {
                            "Create": {},
                            "Read": {},
                        },
                    },
                },
            }
        )
        assert "User" in spec.models
        assert "Create" in spec.models["User"].variants

    def test_get_model_names_includes_variants(self) -> None:
        """Model names include variants."""
        spec = ModelsSpec.from_yaml(
            {
                "models": {
                    "User": {
                        "fields": {"id": {"type": "int"}},
                        "variants": {"Create": {}, "Read": {}},
                    },
                },
            }
        )
        names = spec.get_model_names()
        assert "User" in names
        assert "UserCreate" in names
        assert "UserRead" in names

    def test_to_json_schema(self) -> None:
        """Convert to JSON Schema."""
        spec = ModelsSpec.from_yaml(
            {
                "models": {
                    "User": {
                        "fields": {
                            "id": {"type": "int", "readonly": True},
                            "name": {"type": "string"},
                        },
                        "variants": {
                            "Create": {},
                        },
                    },
                },
            }
        )
        schema = spec.to_json_schema()

        assert "User" in schema["definitions"]
        assert "UserCreate" in schema["definitions"]

        # Base model has both fields
        assert "id" in schema["definitions"]["User"]["properties"]
        assert "name" in schema["definitions"]["User"]["properties"]

        # Create variant excludes readonly
        assert "id" not in schema["definitions"]["UserCreate"]["properties"]
        assert "name" in schema["definitions"]["UserCreate"]["properties"]

    def test_empty_models_fails(self) -> None:
        """Empty models dict should fail."""
        with pytest.raises(ValueError, match="at least one model"):
            ModelsSpec.from_yaml({"models": {}})

    def test_optional_field_propagates_to_all_variants(self) -> None:
        """Field with optional: true is nullable in all variants including Read."""
        spec = ModelsSpec.from_yaml(
            {
                "models": {
                    "Subscription": {
                        "fields": {
                            "id": {"type": "int", "readonly": True},
                            "user_id": {"type": "int"},
                            "telegram_id": {"type": "int", "optional": True},
                        },
                        "variants": {
                            "Create": {},
                            "Read": {},
                        },
                    },
                },
            }
        )
        schema = spec.to_json_schema()

        # Base model: telegram_id is nullable and NOT required
        base = schema["definitions"]["Subscription"]
        assert base["properties"]["telegram_id"]["nullable"] is True
        assert "telegram_id" not in base["required"]

        # Read variant: telegram_id is STILL nullable and NOT required
        read = schema["definitions"]["SubscriptionRead"]
        assert read["properties"]["telegram_id"]["nullable"] is True
        assert "telegram_id" not in read["required"]
        # user_id should still be required
        assert "user_id" in read["required"]

        # Create variant: telegram_id is nullable but not required
        create = schema["definitions"]["SubscriptionCreate"]
        assert create["properties"]["telegram_id"]["nullable"] is True
        assert "telegram_id" not in create["required"]

    def test_optional_field_with_non_none_default_not_nullable(self) -> None:
        """Field with optional: true and non-None default should NOT be nullable."""
        spec = ModelsSpec.from_yaml(
            {
                "models": {
                    "Item": {
                        "fields": {
                            "id": {"type": "int", "readonly": True},
                            "name": {"type": "string"},
                            "is_active": {
                                "type": "bool",
                                "optional": True,
                                "default": False,
                            },
                            "description": {
                                "type": "string",
                                "optional": True,
                                "default": "",
                            },
                        },
                        "variants": {
                            "Create": {},
                            "Read": {},
                        },
                    },
                },
            }
        )
        schema = spec.to_json_schema()

        # is_active: optional + default=false → NOT nullable, has default
        base = schema["definitions"]["Item"]
        assert "nullable" not in base["properties"]["is_active"]
        assert base["properties"]["is_active"]["default"] is False

        # description: optional + default="" → NOT nullable, has default
        assert "nullable" not in base["properties"]["description"]
        assert base["properties"]["description"]["default"] == ""

        # Both fields should NOT be required (they have defaults)
        assert "is_active" not in base["required"]
        assert "description" not in base["required"]
