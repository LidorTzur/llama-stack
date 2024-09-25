# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

from typing import List

from llama_stack.distribution.datatypes import (
    AdapterSpec,
    Api,
    InlineProviderSpec,
    ProviderSpec,
    remote_provider_spec,
)


def available_providers() -> List[ProviderSpec]:
    return [
        InlineProviderSpec(
            api=Api.safety,
            provider_id="meta-reference",
            pip_packages=[
                "codeshield",
                "transformers",
                "torch --index-url https://download.pytorch.org/whl/cpu",
            ],
            module="llama_stack.providers.impls.meta_reference.safety",
            config_class="llama_stack.providers.impls.meta_reference.safety.SafetyConfig",
            api_dependencies=[
                Api.inference,
            ],
        ),
        remote_provider_spec(
            api=Api.safety,
            adapter=AdapterSpec(
                adapter_id="sample",
                pip_packages=[],
                module="llama_stack.providers.adapters.safety.sample",
                config_class="llama_stack.providers.adapters.safety.sample.SampleConfig",
            ),
        ),
        remote_provider_spec(
            api=Api.safety,
            adapter=AdapterSpec(
                adapter_id="bedrock_guardrails",
                pip_packages=['boto3',],
                module="llama_stack.providers.adapters.safety.bedrock",
                config_class="llama_stack.providers.adapters.safety.bedrock.config.BedrockShieldConfig",
            ),
        ),
        remote_provider_spec(
            api=Api.safety,
            adapter=AdapterSpec(
                adapter_id="together",
                pip_packages=[
                    "together",
                ],
                module="llama_stack.providers.adapters.safety.together",
                config_class="llama_stack.providers.adapters.safety.together.TogetherSafetyConfig",
                provider_data_validator="llama_stack.providers.adapters.safety.together.TogetherProviderDataValidator",
            ),
        ),
    ]
