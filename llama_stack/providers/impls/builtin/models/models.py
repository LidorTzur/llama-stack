# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.
import asyncio

from typing import AsyncIterator, Union

from llama_models.llama3.api.datatypes import StopReason
from llama_models.sku_list import resolve_model

from llama_stack.apis.models import *  # noqa: F403
from llama_models.llama3.api.datatypes import *  # noqa: F403
from llama_models.datatypes import CoreModelId, Model
from llama_models.sku_list import resolve_model
from termcolor import cprint

from .config import BuiltinImplConfig

DUMMY_MODELS_SPEC_1 = ModelSpec(
    llama_model_metadata=resolve_model("Llama-Guard-3-8B"),
    providers_spec={"safety": {"provider_type": "meta-reference"}},
)

DUMMY_MODELS_SPEC_2 = ModelSpec(
    llama_model_metadata=resolve_model("Meta-Llama3.1-8B-Instruct"),
    providers_spec={"inference": {"provider_type": "meta-reference"}},
)


class BuiltinModelsImpl(Models):
    def __init__(
        self,
        config: BuiltinImplConfig,
    ) -> None:
        self.config = config

        self.models = {
            x.llama_model_metadata.core_model_id.value: x
            for x in [DUMMY_MODELS_SPEC_1, DUMMY_MODELS_SPEC_2]
        }

        cprint(self.config, "red")

    async def initialize(self) -> None:
        pass

    async def list_models(self) -> ModelsListResponse:
        print(self.config, "hihihi")
        return ModelsListResponse(models_list=list(self.models.values()))

    async def get_model(self, core_model_id: str) -> ModelsGetResponse:
        if core_model_id in self.models:
            return ModelsGetResponse(core_model_spec=self.models[core_model_id])
        raise RuntimeError(f"Cannot find {core_model_id} in model registry")

    async def register_model(
        self, model_id: str, api: str, provider_spec: Dict[str, str]
    ) -> ModelsRegisterResponse:
        return ModelsRegisterResponse()
