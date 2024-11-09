# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

from typing import Any, Dict, List, Optional

from llama_models.llama3.api.datatypes import *  # noqa: F403

from llama_stack.apis.models import *  # noqa: F403
from llama_stack.apis.shields import *  # noqa: F403
from llama_stack.apis.memory_banks import *  # noqa: F403
from llama_stack.apis.datasets import *  # noqa: F403
from llama_stack.apis.eval_tasks import *  # noqa: F403


from llama_stack.distribution.store import DistributionRegistry
from llama_stack.distribution.datatypes import *  # noqa: F403
from llama_stack.distribution.utils.memory_bank_utils import build_memory_bank


def get_impl_api(p: Any) -> Api:
    return p.__provider_spec__.api


async def register_object_with_provider(obj: RoutableObject, p: Any) -> None:
    api = get_impl_api(p)

    if obj.provider_id == "remote":
        # if this is just a passthrough, we want to let the remote
        # end actually do the registration with the correct provider
        obj = obj.model_copy(deep=True)
        obj.provider_id = ""

    if api == Api.inference:
        await p.register_model(obj)
    elif api == Api.safety:
        await p.register_shield(obj)
    elif api == Api.memory:
        await p.register_memory_bank(obj)
    elif api == Api.datasetio:
        await p.register_dataset(obj)
    elif api == Api.scoring:
        await p.register_scoring_function(obj)
    elif api == Api.eval:
        await p.register_eval_task(obj)
    else:
        raise ValueError(f"Unknown API {api} for registering object with provider")


Registry = Dict[str, List[RoutableObjectWithProvider]]


class CommonRoutingTableImpl(RoutingTable):
    def __init__(
        self,
        impls_by_provider_id: Dict[str, RoutedProtocol],
        dist_registry: DistributionRegistry,
    ) -> None:
        self.impls_by_provider_id = impls_by_provider_id
        self.dist_registry = dist_registry

    async def initialize(self) -> None:
        # Initialize the registry if not already done
        await self.dist_registry.initialize()

        async def add_objects(
            objs: List[RoutableObjectWithProvider], provider_id: str, cls
        ) -> None:
            for obj in objs:
                if cls is None:
                    obj.provider_id = provider_id
                else:
                    if provider_id == "remote":
                        # if this is just a passthrough, we got the *WithProvider object
                        # so we should just override the provider in-place
                        obj.provider_id = provider_id
                    else:
                        obj = cls(**obj.model_dump(), provider_id=provider_id)
                await self.dist_registry.register(obj)

        # Register all objects from providers
        for pid, p in self.impls_by_provider_id.items():
            api = get_impl_api(p)
            if api == Api.inference:
                p.model_store = self
            elif api == Api.safety:
                p.shield_store = self

            elif api == Api.memory:
                p.memory_bank_store = self
                memory_banks = await p.list_memory_banks()
                await add_objects(memory_banks, pid, None)

            elif api == Api.datasetio:
                p.dataset_store = self
                datasets = await p.list_datasets()
                await add_objects(datasets, pid, DatasetDefWithProvider)

            elif api == Api.scoring:
                p.scoring_function_store = self
                scoring_functions = await p.list_scoring_functions()
                await add_objects(scoring_functions, pid, ScoringFnDefWithProvider)

            elif api == Api.eval:
                p.eval_task_store = self
                eval_tasks = await p.list_eval_tasks()
                await add_objects(eval_tasks, pid, EvalTaskDefWithProvider)

    async def shutdown(self) -> None:
        for p in self.impls_by_provider_id.values():
            await p.shutdown()

    def get_provider_impl(
        self, routing_key: str, provider_id: Optional[str] = None
    ) -> Any:
        def apiname_object():
            if isinstance(self, ModelsRoutingTable):
                return ("Inference", "model")
            elif isinstance(self, ShieldsRoutingTable):
                return ("Safety", "shield")
            elif isinstance(self, MemoryBanksRoutingTable):
                return ("Memory", "memory_bank")
            elif isinstance(self, DatasetsRoutingTable):
                return ("DatasetIO", "dataset")
            elif isinstance(self, ScoringFunctionsRoutingTable):
                return ("Scoring", "scoring_function")
            elif isinstance(self, EvalTasksRoutingTable):
                return ("Eval", "eval_task")
            else:
                raise ValueError("Unknown routing table type")

        # Get objects from disk registry
        objects = self.dist_registry.get_cached(routing_key)
        if not objects:
            apiname, objname = apiname_object()
            provider_ids = list(self.impls_by_provider_id.keys())
            if len(provider_ids) > 1:
                provider_ids_str = f"any of the providers: {', '.join(provider_ids)}"
            else:
                provider_ids_str = f"provider: `{provider_ids[0]}`"
            raise ValueError(
                f"{objname.capitalize()} `{routing_key}` not served by {provider_ids_str}. Make sure there is an {apiname} provider serving this {objname}."
            )

        for obj in objects:
            if not provider_id or provider_id == obj.provider_id:
                return self.impls_by_provider_id[obj.provider_id]

        raise ValueError(f"Provider not found for `{routing_key}`")

    async def get_object_by_identifier(
        self, identifier: str
    ) -> Optional[RoutableObjectWithProvider]:
        # Get from disk registry
        objects = await self.dist_registry.get(identifier)
        if not objects:
            return None

        # kind of ill-defined behavior here, but we'll just return the first one
        return objects[0]

    async def register_object(self, obj: RoutableObjectWithProvider):
        # Get existing objects from registry
        existing_objects = await self.dist_registry.get(obj.identifier)

        # Check for existing registration
        for existing_obj in existing_objects:
            if existing_obj.provider_id == obj.provider_id or not obj.provider_id:
                print(
                    f"`{obj.identifier}` already registered with `{existing_obj.provider_id}`"
                )
                return

        # if provider_id is not specified, pick an arbitrary one from existing entries
        if not obj.provider_id and len(self.impls_by_provider_id) > 0:
            obj.provider_id = list(self.impls_by_provider_id.keys())[0]

        if obj.provider_id not in self.impls_by_provider_id:
            raise ValueError(f"Provider `{obj.provider_id}` not found")

        p = self.impls_by_provider_id[obj.provider_id]

        await register_object_with_provider(obj, p)
        await self.dist_registry.register(obj)

    async def get_all_with_type(self, type: str) -> List[RoutableObjectWithProvider]:
        objs = await self.dist_registry.get_all()
        return [obj for obj in objs if obj.type == type]


class ModelsRoutingTable(CommonRoutingTableImpl, Models):
    async def list_models(self) -> List[Model]:
        return await self.get_all_with_type("model")

    async def get_model(self, identifier: str) -> Optional[Model]:
        return await self.get_object_by_identifier(identifier)

    async def register_model(
        self,
        model_id: str,
        provider_model_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Model:
        if provider_model_id is None:
            provider_model_id = model_id
        if provider_id is None:
            # If provider_id not specified, use the only provider if it supports this model
            if len(self.impls_by_provider_id) == 1:
                provider_id = list(self.impls_by_provider_id.keys())[0]
            else:
                raise ValueError(
                    "No provider specified and multiple providers available. Please specify a provider_id. Available providers: {self.impls_by_provider_id.keys()}"
                )
        if metadata is None:
            metadata = {}
        model = Model(
            identifier=model_id,
            provider_resource_id=provider_model_id,
            provider_id=provider_id,
            metadata=metadata,
        )
        await self.register_object(model)
        return model


class ShieldsRoutingTable(CommonRoutingTableImpl, Shields):
    async def list_shields(self) -> List[Shield]:
        return await self.get_all_with_type(ResourceType.shield.value)

    async def get_shield(self, identifier: str) -> Optional[Shield]:
        return await self.get_object_by_identifier(identifier)

    async def register_shield(
        self,
        shield_id: str,
        shield_type: ShieldType,
        provider_shield_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Shield:
        if provider_shield_id is None:
            provider_shield_id = shield_id
        if provider_id is None:
            # If provider_id not specified, use the only provider if it supports this shield type
            if len(self.impls_by_provider_id) == 1:
                provider_id = list(self.impls_by_provider_id.keys())[0]
            else:
                raise ValueError(
                    "No provider specified and multiple providers available. Please specify a provider_id."
                )
        if params is None:
            params = {}
        shield = Shield(
            identifier=shield_id,
            shield_type=shield_type,
            provider_resource_id=provider_shield_id,
            provider_id=provider_id,
            params=params,
        )
        await self.register_object(shield)
        return shield


class MemoryBanksRoutingTable(CommonRoutingTableImpl, MemoryBanks):
    async def list_memory_banks(self) -> List[MemoryBank]:
        return await self.get_all_with_type(ResourceType.memory_bank.value)

    async def get_memory_bank(self, memory_bank_id: str) -> Optional[MemoryBank]:
        return await self.get_object_by_identifier(memory_bank_id)

    async def register_memory_bank(
        self,
        memory_bank_id: str,
        provider_id: str,
        provider_memorybank_id: str,
        params: BankParams,
    ) -> MemoryBank:
        if provider_memorybank_id is None:
            provider_memorybank_id = memory_bank_id
        if provider_id is None:
            # If provider_id not specified, use the only provider if it supports this shield type
            if len(self.impls_by_provider_id) == 1:
                provider_id = list(self.impls_by_provider_id.keys())[0]
            else:
                raise ValueError(
                    "No provider specified and multiple providers available. Please specify a provider_id."
                )
        memory_bank = build_memory_bank(
            memory_bank_id, params.type, provider_id, provider_memorybank_id, params
        )
        await self.register_object(memory_bank)
        return memory_bank


class DatasetsRoutingTable(CommonRoutingTableImpl, Datasets):
    async def list_datasets(self) -> List[DatasetDefWithProvider]:
        return await self.get_all_with_type("dataset")

    async def get_dataset(
        self, dataset_identifier: str
    ) -> Optional[DatasetDefWithProvider]:
        return await self.get_object_by_identifier(dataset_identifier)

    async def register_dataset(self, dataset_def: DatasetDefWithProvider) -> None:
        await self.register_object(dataset_def)


class ScoringFunctionsRoutingTable(CommonRoutingTableImpl, ScoringFunctions):
    async def list_scoring_functions(self) -> List[ScoringFnDefWithProvider]:
        return await self.get_all_with_type("scoring_fn")

    async def get_scoring_function(
        self, name: str
    ) -> Optional[ScoringFnDefWithProvider]:
        return await self.get_object_by_identifier(name)

    async def register_scoring_function(
        self, function_def: ScoringFnDefWithProvider
    ) -> None:
        await self.register_object(function_def)


class EvalTasksRoutingTable(CommonRoutingTableImpl, EvalTasks):
    async def list_eval_tasks(self) -> List[ScoringFnDefWithProvider]:
        return await self.get_all_with_type("eval_task")

    async def get_eval_task(self, name: str) -> Optional[EvalTaskDefWithProvider]:
        return await self.get_object_by_identifier(name)

    async def register_eval_task(self, eval_task_def: EvalTaskDefWithProvider) -> None:
        await self.register_object(eval_task_def)
