from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.11.0"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'harmon',
     'default_range': 'string',
     'description': 'LinkML representation of the canonical harmonized dataset '
                    'schema. Every harmonized dataset must conform to this exact '
                    '9-column schema. This is the LinkML equivalent of '
                    '``src/schemas/target_schema.py``: the ``HarmonizedRecord`` '
                    'class describes a single row, with one slot per harmonized '
                    'column. Slot ranges, units, and value constraints mirror the '
                    '``HARMONIZED_COLUMNS``, ``EXPECTED_DTYPES`` and '
                    '``VALID_RANGES`` constants in that module.',
     'id': 'https://w3id.org/bioepic/data-harmonization-eval/target-schema',
     'imports': ['linkml:types'],
     'license': 'MIT',
     'name': 'target_schema',
     'prefixes': {'harmon': {'prefix_prefix': 'harmon',
                             'prefix_reference': 'https://w3id.org/bioepic/data-harmonization-eval/target-schema/'},
                  'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'}},
     'source_file': 'src/schemas/target_schema.yaml',
     'title': 'Harmonized Soil Moisture Target Schema'} )

class QCFlagVocabulary(str, Enum):
    """
    Controlled vocabulary for QC flag values. Equivalent to the ``QCFlagVocabulary`` enum in ``target_schema.py``.
    """
    d1 = "d1"
    """
    Depth approximated from a reported range.
    """
    g1 = "g1"
    """
    Coordinates from Varadharajan et al. (not present in the source dataset).
    """
    g2 = "g2"
    """
    Coordinates not available from any source.
    """



class HarmonizedRecord(ConfiguredBaseModel):
    """
    A single row of a harmonized soil moisture dataset. The ordered list of slots corresponds exactly to ``HARMONIZED_COLUMNS`` (order matters). ``datetime_UTC`` and ``site_id`` are required, and at least one of the three moisture variables must be present.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/bioepic/data-harmonization-eval/target-schema',
         'rules': [{'description': 'At least one moisture variable (volumetric water '
                                   'content, gravimetric water content, or water '
                                   'potential) must be present in a record.',
                    'postconditions': {'any_of': [{'slot_conditions': {'volumetric_water_content_m3_m3': {'name': 'volumetric_water_content_m3_m3',
                                                                                                          'value_presence': 'PRESENT'}}},
                                                  {'slot_conditions': {'gravimetric_water_content_gH2O_gs': {'name': 'gravimetric_water_content_gH2O_gs',
                                                                                                             'value_presence': 'PRESENT'}}},
                                                  {'slot_conditions': {'water_potential_kPa': {'name': 'water_potential_kPa',
                                                                                               'value_presence': 'PRESENT'}}}]},
                    'preconditions': {'slot_conditions': {'datetime_UTC': {'name': 'datetime_UTC',
                                                                           'value_presence': 'PRESENT'}}}}]})

    datetime_UTC: datetime  = Field(default=..., description="""Observation timestamp in UTC. Maps to a pandas ``datetime64[ns, UTC]`` column. Required.""", json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedRecord'], 'rank': 1} })
    site_id: str = Field(default=..., description="""Identifier for the sampling site. Required.""", json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedRecord'], 'rank': 2} })
    depth_m: Optional[float] = Field(default=None, description="""Sampling depth below the surface, in meters.""", ge=0.0, le=100.0, json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedRecord'], 'rank': 3, 'unit': {'ucum_code': 'm'}} })
    replicate: Optional[float] = Field(default=None, description="""Replicate number for the observation. Stored as a float to allow NaN (missing) values. Nullable.""", json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedRecord'], 'rank': 4} })
    is_timeseries: Optional[bool] = Field(default=None, description="""Whether the record belongs to a time series (true) or is a one-off / point measurement (false).""", json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedRecord'], 'rank': 5} })
    interval_min: Optional[float] = Field(default=None, description="""Sampling interval in minutes for time-series records. Stored as a float to allow NaN (missing) values. Nullable.""", ge=0.0, le=1000000.0, json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedRecord'], 'rank': 6, 'unit': {'ucum_code': 'min'}} })
    volumetric_water_content_m3_m3: Optional[float] = Field(default=None, description="""Volumetric water content as a fraction (cubic meters of water per cubic meter of soil).""", ge=0.0, le=1.0, json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedRecord'], 'rank': 7, 'unit': {'ucum_code': 'm3/m3'}} })
    gravimetric_water_content_gH2O_gs: Optional[float] = Field(default=None, description="""Gravimetric water content (grams of water per gram of dry soil). The generous upper bound accommodates organic-rich soils.""", ge=0.0, le=10.0, json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedRecord'], 'rank': 8, 'unit': {'ucum_code': 'g/g'}} })
    water_potential_kPa: Optional[float] = Field(default=None, description="""Soil water potential in kilopascals. Values are non-positive (zero at saturation, increasingly negative as the soil dries).""", ge=-1000000.0, le=0.0, json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedRecord'], 'rank': 9, 'unit': {'ucum_code': 'kPa'}} })


class HarmonizedDataset(ConfiguredBaseModel):
    """
    A harmonized dataset: an ordered collection of ``HarmonizedRecord`` rows conforming to the target schema.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/bioepic/data-harmonization-eval/target-schema'})

    records: Optional[list[HarmonizedRecord]] = Field(default=None, description="""The harmonized rows that make up the dataset.""", json_schema_extra = { "linkml_meta": {'domain_of': ['HarmonizedDataset']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
HarmonizedRecord.model_rebuild()
HarmonizedDataset.model_rebuild()
